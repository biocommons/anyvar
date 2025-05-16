"""Provide DuckDB-based storage implementation."""

import json
from collections.abc import Iterable
from typing import Any

import duckdb
import pydantic
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from anyvar.storage.sql_storage import SqlStorage, VrsSqlStorage
from anyvar.utils.types import Annotation, AnnotationKey


class DuckdbAnnotationObjectStore(SqlStorage):
    """Annotation object store for DuckDB backend."""

    def __init__(
        self,
        db_url: str,
        batch_limit: int | None = None,
        table_name: str | None = None,
        max_pending_batches: int | None = None,
        flush_on_batchctx_exit: bool | None = None,
    ) -> None:
        """Initialize DB handler."""
        super().__init__(
            db_url,
            batch_limit,
            table_name,
            max_pending_batches,
            flush_on_batchctx_exit,
        )

    def create_schema(self, db_conn: Connection) -> None:
        """Create the table if it does not exist.

        :param db_conn: a SQLAlchemy database connection
        :return: None
        """
        check_statement = f"""
            SELECT EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_name = '{self.table_name}')
        """  # noqa: S608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                object_id TEXT,
                annotation_type TEXT,
                annotation JSON
            )
        """
        # Check if table exists
        result = db_conn.execute(check_statement).fetchone()
        table_exists = result[0] > 0

        # If the table does not exist, create it
        if not table_exists:
            db_conn.execute(create_statement)

    def __getitem__(self, key: AnnotationKey) -> Iterable[Annotation]:
        """Get annotations by key.

        :param key: AnnotationKey object
        :return: iterable of Annotation objects
        """
        if key.object_id is None:
            raise ValueError("Object ID is required")
        if key.annotation_type is None:
            raise ValueError("Annotation type is required")

        query_str = f"""
            SELECT * from {self.table_name}
            WHERE object_id = :object_id
        """  # noqa: S608
        params = {"object_id": key.object_id}
        if key.annotation_type:
            query_str += "AND annotation_type = :annotation_type"
            params["annotation_type"] = key.annotation_type

        with self._get_connection() as conn:
            result = conn.execute(sql_text(query_str), params)
            try:
                first = next(result)
            except StopIteration:
                raise KeyError(f"Key {key} not found")  # noqa: B904
            return [
                Annotation(
                    object_id=first.object_id,
                    annotation_type=first.annotation_type,
                    annotation=first.annotation,
                )
            ] + [
                Annotation(
                    object_id=row.object_id,
                    annotation_type=row.annotation_type,
                    annotation=row.annotation,
                )
                for row in result
            ]

    def push(self, value: Annotation) -> None:
        """Add a single annotation to the store.

        :param value: Annotation object
        :return: None
        """
        self[value.key()] = value.annotation

    def add_one_item(
        self,
        db_conn: Connection,
        name: AnnotationKey,
        value: dict | str,
    ) -> None:
        """Add a single item.

        :param db_conn: a SQLAlchemy database connection
        :param name: AnnotationKey object
        :param value: value to be inserted for that key
        :return: None
        """
        insert_query = f"INSERT INTO {self.table_name} (object_id, annotation_type, annotation) VALUES (:object_id, :annotation_type, :annotation)"  # noqa: S608
        db_conn.execute(
            sql_text(insert_query),
            {
                "object_id": name.object_id,
                "annotation_type": name.annotation_type,
                "annotation": json.dumps(value) if isinstance(value, dict) else value,
            },
        )

    def add_many_items(
        self, db_conn: Connection, items: list[tuple[AnnotationKey, dict]]
    ) -> None:
        """Perform copy-based insert, enabling much faster writes for large, repeated
        insert statements, using insert parameters stored in `self.batch_insert_values`.

        Because we may be writing repeated records, we need to handle conflicts, which
        isn't available for COPY. The workaround (https://stackoverflow.com/a/49836011)
        is to make a temporary table for each COPY statement, and then handle
        conflicts when moving data over from that table to vrs_objects.

        :param db_conn: a SQLAlchemy database connection
        :param items: list of tuples (AnnotationKey, dict) to be inserted
        """
        tmp_table_name = f"tmp_{self.table_name}"
        # https://duckdb.org/docs/stable/sql/statements/create_table.html#copying-the-schema
        tmp_statement = (
            f"CREATE TEMP TABLE {tmp_table_name} AS FROM {self.table_name} LIMIT 0"
        )
        insert_statement = (
            f"INSERT INTO {self.table_name} SELECT * FROM {tmp_table_name}"  # noqa: S608
        )
        drop_statement = f"DROP TABLE {tmp_table_name}"
        db_conn.execute(sql_text(tmp_statement))

        row_data = [
            (name.object_id, name.annotation_type, json.dumps(value))
            for name, value in items
        ]

        # Insert into the temporary table
        db_conn.execute(f"INSERT INTO {tmp_table_name} VALUES (?, ?, ?)", row_data)  # noqa: S608
        # Copy temp table to the main table
        db_conn.execute(sql_text(insert_statement))
        # Drop the temporary table
        db_conn.execute(sql_text(drop_statement))

    def __delitem__(self, key: AnnotationKey) -> None:
        """Delete annotations matching the key.

        :param key: AnnotationKey object. All values for this key will be deleted.
        :return: None
        """
        delete_statement = f"DELETE FROM {self.table_name} WHERE object_id = :object_id AND annotation_type = :annotation_type"  # noqa: S608
        with self._get_connection() as conn:
            conn.execute(
                sql_text(delete_statement),
                {"object_id": key.object_id, "annotation_type": key.annotation_type},
            )

    def keys(self) -> Iterable:
        """Return all annotation keys in the store including duplicates."""
        query_statement = f"SELECT object_id, annotation_type FROM {self.table_name}"  # noqa: S608
        with self._get_connection() as conn:
            result = conn.execute(sql_text(query_statement))
            yield from (
                AnnotationKey(
                    object_id=row["object_id"],
                    annotation_type=row["annotation_type"],
                )
                for row in result
            )


class DuckdbObjectStore(VrsSqlStorage):
    """DuckDB storage backend."""

    def __init__(
        self,
        db_url: str,
        batch_limit: int | None = None,
        table_name: str | None = None,
        max_pending_batches: int | None = None,
        flush_on_batchctx_exit: bool | None = None,
    ) -> None:
        """Initialize DB handler."""
        super().__init__(
            db_url,
            batch_limit,
            table_name,
            max_pending_batches,
            flush_on_batchctx_exit,
        )

    def create_schema(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        """Add the VRS object table if it does not exist

        :param db_conn: a DuckDB database connection
        """
        check_statement = f"""
            SELECT EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_name = '{self.table_name}')
        """  # noqa: S608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                vrs_id TEXT PRIMARY KEY,
                vrs_object JSON
            )
        """
        # Check if table exists
        result: tuple[bool] = db_conn.execute(check_statement).fetchone()
        table_exists = result[0]

        # If the table does not exist, create it
        if not table_exists:
            db_conn.execute(create_statement)

    def add_one_item(
        self,
        db_conn: duckdb.DuckDBPyConnection,
        name: str,
        value: Any,  # noqa: ANN401
    ) -> None:
        """Add/merge a single item to the DuckDB database.

        :param db_conn: a DuckDB database connection
        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """
        # Convert the value to a JSON string
        value_json = json.dumps(value.model_dump(exclude_none=True))

        # Use INSERT with ON CONFLICT DO NOTHING
        insert_query = f"""
            INSERT INTO {self.table_name} (vrs_id, vrs_object)
            VALUES (:vrs_id, :vrs_object)
            ON CONFLICT (vrs_id) DO NOTHING
        """  # noqa: S608

        # Execute the query with parameterized values
        db_conn.execute(
            sql_text(insert_query),
            {"vrs_id": name, "vrs_object": value_json},
            # (name, value_json),
        )

    def add_many_items(
        self,
        db_conn: duckdb.DuckDBPyConnection,
        items: list[tuple[str, pydantic.BaseModel]],
    ) -> None:
        """Perform bulk insert using a temporary table in DuckDB.

        :param db_conn: a DuckDB database connection
        :param items: list of tuples (name, value) to be inserted
        """
        # Create a temporary table with the same schema as the main table
        tmp_table_name = f"tmp_{self.table_name}"
        tmp_statement = f"""
            CREATE TEMP TABLE {tmp_table_name}
            AS FROM {self.table_name} LIMIT 0
        """
        insert_tmp_statement = f"""
            INSERT INTO {tmp_table_name} (vrs_id, vrs_object)
            VALUES (:vrs_id, :vrs_object)
        """  # noqa: S608

        insert_statement = f"""
            INSERT INTO {self.table_name}
            SELECT * FROM {tmp_table_name}
            ON CONFLICT (vrs_id) DO NOTHING
        """  # noqa: S608
        drop_statement = f"DROP TABLE {tmp_table_name}"

        # Create the temporary table
        db_conn.execute(tmp_statement)

        # Prepare data for bulk insertion
        row_data = [
            {
                "vrs_id": name,
                "vrs_object": json.dumps(value.model_dump(exclude_none=True)),
            }
            for name, value in items
        ]
        # Insert data into the temporary table
        db_conn.execute(
            insert_tmp_statement,
            row_data,
        )

        # Move data from the temporary table to the main table with conflict handling
        db_conn.execute(insert_statement)

        # Drop the temporary table
        db_conn.execute(drop_statement)

    def deletion_count(self, db_conn: Connection) -> int:
        """Count the number of VRS objects with no sequence

        :param db_conn: a database connection
        :param vrs_id: the VRS ID
        """
        result = db_conn.execute(
            sql_text(
                f"""
            SELECT COUNT(*) AS c
              FROM {self.table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 0
            """  # noqa: S608
            )
        )
        return result.scalar()

    def substitution_count(self, db_conn: Connection) -> int:
        """Return the total number of substitutions

        :param db_conn: a database connection
        """
        result = db_conn.execute(
            sql_text(
                f"""
            SELECT COUNT(*) AS c
              FROM {self.table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 1
            """  # noqa: S608
            )
        )
        return result.scalar()

    def insertion_count(self, db_conn: Connection) -> int:
        """Return the total number of insertions

        :param db_conn: a database connection
        """
        result = db_conn.execute(
            sql_text(
                f"""
            SELECT COUNT(*) AS c
              FROM {self.table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') > 1
            """  # noqa: S608
            )
        )
        return result.scalar()

    def search_vrs_objects(
        self,
        db_conn: Connection,
        type: str,  # noqa: A002
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list:
        """Find all VRS objects of the particular type and region

        :param type: the type of VRS object to search for
        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of VRS objects
        """
        query_str = f"""
        SELECT vrs_object
        FROM {self.table_name}
        WHERE (vrs_object->>'type' = :type)
            AND (vrs_object->>'location' IN (
                SELECT vrs_id FROM {self.table_name}
                WHERE (CAST (vrs_object->>'start' AS INTEGER) >= :start)
                    AND (CAST (vrs_object->>'end' AS INTEGER) <= :end)
                    AND (vrs_object->'sequenceReference'->>'refgetAccession' = :refgetAccession)
            ))
        """  # noqa: S608
        results = db_conn.execute(
            sql_text(query_str),
            {
                "type": type,
                "start": start,
                "end": stop,
                "refgetAccession": refget_accession,
            },
        ).fetchall()
        return [vrs_object[0] for vrs_object in results if vrs_object]
