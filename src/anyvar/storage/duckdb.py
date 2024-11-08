"""Provide PostgreSQL-based storage implementation."""

import json
import random
import string
from io import StringIO
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pydantic
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from anyvar.storage.sql_storage import SqlStorage

from . import _Storage

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class DuckdbObjectStore(SqlStorage):
    """PostgreSQL storage backend. Currently, this is our recommended storage
    approach.
    """

    # def __init__(self, db_file_path: Path) -> None:
    #     """Initialize DB handler."""
    #     self.db_file_path = db_file_path
    #     self.table_name = "vrs_objects"

    #     self.db_conn = self._get_connection()
    #     self.create_schema(self.db_conn)

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
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = '{self.table_name}'
        """  # noqa: S608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                vrs_id TEXT PRIMARY KEY,
                vrs_object JSON
            )
        """
        # Check if table exists
        result = db_conn.execute(check_statement).fetchone()
        table_exists = result[0] > 0

        # If the table does not exist, create it
        if not table_exists:
            db_conn.execute(create_statement)

    def add_one_item(
        self, db_conn: duckdb.DuckDBPyConnection, name: str, value: Any
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
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
        """  # noqa: S608

        # Execute the query with parameterized values
        db_conn.execute(insert_query, (name, value_json))

    def _random_tmp_table_name(self) -> str:
        return "".join(random.choice(string.ascii_uppercase) for i in range(32))

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
        # TODO if application has any concurrency, tmp_table name should be made unique instead
        # Create random name starting with tmp_table
        tmp_table_name = f"tmp_table_{self._random_tmp_table_name()}"
        tmp_statement = f"""
            CREATE TEMPORARY TABLE {tmp_table_name} (vrs_id TEXT, vrs_object JSON)
        """
        insert_statement = f"""
            INSERT INTO {self.table_name}
            SELECT * FROM {tmp_table_name}
            ON CONFLICT (vrs_id) DO NOTHING
        """  # noqa: S608
        drop_statement = f"DROP TABLE {tmp_table_name}"

        # Create the temporary table
        db_conn.execute(tmp_statement)

        # Prepare data for bulk insertion using a Pandas DataFrame
        row_data = [
            (name, json.dumps(value.model_dump(exclude_none=True)))
            for name, value in items
        ]

        # Insert data into the temporary table
        db_conn.execute(
            f"INSERT INTO {tmp_table_name} VALUES (?, ?)", row_data  # noqa: S608
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
             WHERE vrs_object->>'type' = %s
               AND vrs_object->>'location' IN (
                SELECT vrs_id FROM {self.table_name}
                 WHERE CAST (vrs_object->>'start' AS INTEGER) >= %s
                   AND CAST (vrs_object->>'end' AS INTEGER) <= %s
                   AND vrs_object->'sequenceReference'->>'refgetAccession' = %s)
        """  # noqa: S608
        with db_conn.connection.cursor() as cur:
            cur.execute(query_str, [type, start, stop, refget_accession])
            results = cur.fetchall()
        return [vrs_object[0] for vrs_object in results if vrs_object]

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context manager."""
        self.close()
        return True
