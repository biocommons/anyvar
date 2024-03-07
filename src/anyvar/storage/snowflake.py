import json
import logging
from typing import Any, List, Optional
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from .sql_storage import SqlStorage

_logger = logging.getLogger(__name__)


class SnowflakeObjectStore(SqlStorage):
    """Snowflake storage backend. Requires existing Snowflake database."""

    def __init__(
        self,
        db_url: str,
        batch_limit: Optional[int] = None,
        table_name: Optional[str] = None,
        max_pending_batches: Optional[int] = None,
    ):
        SqlStorage.__init__(
            self,
            db_url.replace(".snowflakecomputing.com", ""),
            batch_limit,
            table_name,
            max_pending_batches,
        )

    def create_schema(self, db_conn: Connection):
        check_statement = f"""
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
               AND UPPER(table_name) = UPPER('{self.table_name}')
        """  # nosec B608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                vrs_id VARCHAR(500) PRIMARY KEY,
                vrs_object VARIANT
            )
        """  # nosec B608
        result = db_conn.execute(sql_text(check_statement))
        if result.scalar() < 1:
            db_conn.execute(sql_text(create_statement))

    def add_one_item(self, db_conn: Connection, name: str, value: Any):
        insert_query = f"""
            MERGE INTO {self.table_name} t USING (SELECT :vrs_id AS vrs_id, :vrs_object AS vrs_object) s ON t.vrs_id = s.vrs_id
            WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
            """  # nosec B608
        value_json = json.dumps(value.model_dump(exclude_none=True))
        db_conn.execute(insert_query, {"vrs_id": name, "vrs_object": value_json})
        _logger.debug("Inserted item %s to %s", name, self.table_name)

    def add_many_items(self, db_conn: Connection, items: list):
        """Bulk inserts the batch values into a TEMP table, then merges into the main {self.table_name} table"""
        tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500), vrs_object VARCHAR)"
        insert_statement = (
            "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object)"
        )
        merge_statement = f"""
            MERGE INTO {self.table_name} v USING tmp_vrs_objects s ON v.vrs_id = s.vrs_id 
             WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
            """  # nosec B608
        drop_statement = "DROP TABLE tmp_vrs_objects"

        row_data = [
            ({"vrs_id": name, "vrs_object": json.dumps(value.model_dump(exclude_none=True))})
            for name, value in items
        ]
        _logger.info("Created row data for insert, first item is %s", row_data[0])

        db_conn.execute(sql_text(tmp_statement))
        db_conn.execute(sql_text(insert_statement), row_data)
        db_conn.execute(sql_text(merge_statement))
        db_conn.execute(sql_text(drop_statement))

    def deletion_count(self, db_conn: Connection) -> int:
        result = db_conn.execute(
            f"""
            SELECT COUNT(*) 
              FROM {self.table_name}
             WHERE LENGTH(vrs_object:state:sequence) = 0
            """  # nosec B608
        )
        return result.scalar()

    def substitution_count(self, db_conn: Connection) -> int:
        result = db_conn.execute(
            f"""
            SELECT COUNT(*) 
              FROM {self.table_name}
             WHERE LENGTH(vrs_object:state:sequence) = 1
            """  # nosec B608
        )
        return result.scalar()

    def insertion_count(self, db_conn: Connection) -> int:
        result = db_conn.execute(
            f"""
            SELECT COUNT(*) 
              FROM {self.table_name}
             WHERE LENGTH(vrs_object:state:sequence) > 1
            """  # nosec B608
        )
        return result.scalar()

    def search_vrs_objects(
        self, db_conn: Connection, type: str, refget_accession: str, start: int, stop: int
    ) -> List[Any]:
        query_str = f"""
            SELECT vrs_object 
              FROM {self.table_name}
             WHERE vrs_object:type = :type 
               AND vrs_object:location IN (
                SELECT vrs_id FROM {self.table_name}
                 WHERE vrs_object:start::INTEGER >= :start
                   AND vrs_object:end::INTEGER <= :end
                   AND vrs_object:sequenceReference:refgetAccession = :refgetAccession)
            """  # nosec B608
        results = db_conn.execute(
            query_str,
            {"type": type, "start": start, "end": stop, "refgetAccession": refget_accession},
        )
        return [json.loads(row[0]) for row in results if row]
