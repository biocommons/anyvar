"""Provide PostgreSQL-based storage implementation."""

import json
from io import StringIO
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from .sql_storage import SqlStorage

silos = [
    "locations",
    "alleles",
    "haplotypes",
    "genotypes",
    "variationsets",
    "relations",
    "texts",
]


class PostgresObjectStore(SqlStorage):
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

    def add_one_item(self, db_conn: Connection, name: str, value: Any) -> None:  # noqa: ANN401
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
