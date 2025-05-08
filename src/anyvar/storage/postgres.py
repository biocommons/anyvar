"""Provide PostgreSQL-based storage implementation."""

import json
import logging
import os
from abc import abstractmethod
from collections.abc import Iterator
from io import StringIO
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from anyvar.utils.types import Annotation, AnnotationKey

from .sql_storage import SqlStorage, VrsSqlStorage

silos = [
    "locations",
    "alleles",
    "haplotypes",
    "genotypes",
    "variationsets",
    "relations",
    "texts",
]

_logger = logging.getLogger(__name__)


# class PostgresCompositeKeyGenericObjectStore(SqlStorage):
#     def __init__(
#         self,
#         db_url: str,
#         key_fields: list[str],
#         batch_limit: int | None = None,
#         table_name: str | None = None,
#         max_pending_batches: int | None = None,
#         flush_on_batchctx_exit: bool | None = None,
#     ) -> None:
#         """Initialize DB handler."""
#         super().__init__(
#             db_url,
#             batch_limit,
#             table_name,
#             max_pending_batches,
#             flush_on_batchctx_exit,
#         )

#         self.key_fields = key_fields

#     def create_schema(self, db_conn: Connection) -> None:
#         check_statement = f"""
#             SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = '{self.table_name}')
#         """  # noqa: S608
#         create_statement = f"""
#             CREATE TABLE {self.table_name} (
#                 {', '.join([f'{field} TEXT' for field in self.key_fields])},
#                 object JSONB
#             )
#         """
#         create_index = f"""
#             CREATE INDEX {self.table_name}_index
#             ON {self.table_name} ({', '.join(self.key_fields)})
#         """
#         # TODO index on each key field?
#         result = db_conn.execute(sql_text(check_statement))
#         if not result or not result.scalar():
#             db_conn.execute(sql_text(create_statement))
#             db_conn.execute(sql_text(create_index))

#     def __getitem__(self, key):
#         # return super().__getitem__(name)
#         pass


class _AnnotationObjectStore(SqlStorage):
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

    @abstractmethod
    def __getitem__(self, key: AnnotationKey) -> Iterator[Annotation]:
        """Retrieve an annotation from the store."""

    @abstractmethod
    def push(self, value: Annotation) -> None:
        """Add a single annotation to the store."""


class PostgresAnnotationObjectStore(SqlStorage):
    """Annotation object store for PostgreSQL backend."""

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
        """Create the table if it does not exist."""
        check_statement = f"""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = '{self.table_name}')
        """  # noqa: S608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                object_id TEXT,
                annotation_type TEXT,
                annotation JSONB
            )
        """
        result = db_conn.execute(sql_text(check_statement))
        if not result or not result.scalar():
            db_conn.execute(sql_text(create_statement))

    def __getitem__(self, key: AnnotationKey) -> Iterator[Annotation]:
        if key.object_id is None:
            raise ValueError("Object ID is required")
        if key.annotation_type is None:
            raise ValueError("Annotation type is required")  # TODO make not required

        query_str = f"""
            SELECT * from {self.table_name}
            WHERE object_id = :object_id
        """  # noqa: S608
        params = {"object_id": key.object_id}
        if key.annotation_type:
            query_str += "AND annotation_type = :annotation_type"
            params["annotation_type"] = key.annotation_type

        # TODO allow null annotation_type
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
        """Add a single annotation to the store."""
        self[value.key()] = value.annotation

    def add_one_item(
        self,
        db_conn: Connection,
        name: AnnotationKey,
        value: dict | str,
    ) -> None:
        insert_query = f"INSERT INTO {self.table_name} (object_id, annotation_type, annotation) VALUES (:object_id, :annotation_type, :annotation) ON CONFLICT DO NOTHING"  # noqa: S608
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
        # TODO implement merge based bulk insert to indexed table
        """Perform copy-based insert, enabling much faster writes for large, repeated
        insert statements, using insert parameters stored in `self.batch_insert_values`.

        Because we may be writing repeated records, we need to handle conflicts, which
        isn't available for COPY. The workaround (https://stackoverflow.com/a/49836011)
        is to make a temporary table for each COPY statement, and then handle
        conflicts when moving data over from that table to vrs_objects.
        """
        # Generate a temporary table name
        tmp_table_name = f"tmp_{self.table_name}_{os.urandom(8).hex()}"
        tmp_statement = f"CREATE TEMP TABLE {tmp_table_name} (LIKE {self.table_name} INCLUDING DEFAULTS)"
        insert_statement = f"INSERT INTO {self.table_name} SELECT * FROM {tmp_table_name} ON CONFLICT DO NOTHING"  # noqa: S608
        drop_statement = f"DROP TABLE {tmp_table_name}"
        db_conn.execute(sql_text(tmp_statement))

        def fmt_row(name: AnnotationKey, value: dict):
            return "\t".join(
                [f"{name.object_id}", f"{name.annotation_type}", f"{json.dumps(value)}"]
            )

        # Get a psycopg2 cursor from the sqlalchemy connection
        with db_conn.connection.cursor() as cur:
            row_data = [fmt_row(name, value) for name, value in items]
            fl = StringIO("\n".join(row_data))
            cur.copy_from(
                fl,
                tmp_table_name,
                columns=["object_id", "annotation_type", "annotation"],
            )
            fl.close()
        db_conn.execute(sql_text(insert_statement))
        db_conn.execute(sql_text(drop_statement))

    def __delitem__(self, key: AnnotationKey) -> None:
        delete_statement = f"DELETE FROM {self.table_name} WHERE object_id = :object_id AND annotation_type = :annotation_type"  # noqa: S608
        with self._get_connection() as conn:
            conn.execute(
                sql_text(delete_statement),
                {"object_id": key.object_id, "annotation_type": key.annotation_type},
            )

    def keys(self) -> list:
        query_statement = f"SELECT object_id FROM {self.table_name}"  # noqa: S608
        with self._get_connection() as conn:
            result = conn.execute(sql_text(query_statement))
            return (row["object_id"] for row in result)


class PostgresObjectStore(VrsSqlStorage):
    """PostgreSQL storage backend. Currently, this is our recommended storage
    approach.
    """

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
        """Add the VRS object table if it does not exist

        :param db_conn: a database connection
        """
        check_statement = f"""
            SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = '{self.table_name}')
        """  # noqa: S608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                vrs_id TEXT PRIMARY KEY,
                vrs_object JSONB
            )
        """
        result = db_conn.execute(sql_text(check_statement))
        if not result or not result.scalar():
            db_conn.execute(sql_text(create_statement))

    def add_one_item(
        self, db_conn: Connection, name: str, value: Any
    ) -> None:  # noqa: ANN401
        """Add/merge a single item to the database

        :param db_conn: a database connection
        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """
        insert_query = f"INSERT INTO {self.table_name} (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object) ON CONFLICT DO NOTHING"  # noqa: S608
        value_json = json.dumps(value.model_dump(exclude_none=True))
        db_conn.execute(
            sql_text(insert_query), {"vrs_id": name, "vrs_object": value_json}
        )

    def add_many_items(self, db_conn: Connection, items: list) -> None:
        """Perform copy-based insert, enabling much faster writes for large, repeated
        insert statements, using insert parameters stored in `self.batch_insert_values`.

        Because we may be writing repeated records, we need to handle conflicts, which
        isn't available for COPY. The workaround (https://stackoverflow.com/a/49836011)
        is to make a temporary table for each COPY statement, and then handle
        conflicts when moving data over from that table to vrs_objects.
        """
        tmp_statement = (
            f"CREATE TEMP TABLE tmp_table (LIKE {self.table_name} INCLUDING DEFAULTS)"
        )
        insert_statement = f"INSERT INTO {self.table_name} SELECT * FROM tmp_table ON CONFLICT DO NOTHING"  # noqa: S608
        drop_statement = "DROP TABLE tmp_table"
        db_conn.execute(sql_text(tmp_statement))
        with db_conn.connection.cursor() as cur:
            row_data = [
                f"{name}\t{json.dumps(value.model_dump(exclude_none=True))}"
                for name, value in items
            ]
            fl = StringIO("\n".join(row_data))
            cur.copy_from(fl, "tmp_table", columns=["vrs_id", "vrs_object"])
            fl.close()
        db_conn.execute(sql_text(insert_statement))
        db_conn.execute(sql_text(drop_statement))

    def deletion_count(self, db_conn: Connection) -> int:
        """Delete a single VRS object

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
        WHERE (vrs_object->>'type' = %s)
            AND (vrs_object->>'location' IN (
                SELECT vrs_id FROM {self.table_name}
                WHERE (CAST (vrs_object->>'start' AS INTEGER) >= %s)
                    AND (CAST (vrs_object->>'end' AS INTEGER) <= %s)
                    AND (vrs_object->'sequenceReference'->>'refgetAccession' = %s)
            ))
        """  # noqa: S608
        with db_conn.connection.cursor() as cur:
            cur.execute(query_str, [type, start, stop, refget_accession])
            results = cur.fetchall()
        return [vrs_object[0] for vrs_object in results if vrs_object]
