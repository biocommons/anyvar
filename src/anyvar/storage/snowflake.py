from enum import auto, StrEnum
import json
import logging
import os
import snowflake.connector
from snowflake.sqlalchemy.snowdialect import SnowflakeDialect
from typing import Any, List, Optional
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection, URL
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from .sql_storage import SqlStorage

_logger = logging.getLogger(__name__)

snowflake.connector.paramstyle = "qmark"

#
# Monkey patch to workaround a bug in the Snowflake SQLAlchemy dialect
#  https://github.com/snowflakedb/snowflake-sqlalchemy/issues/489

# Create a new pointer to the existing create_connect_args method
SnowflakeDialect._orig_create_connect_args = SnowflakeDialect.create_connect_args


# Define a new create_connect_args method that calls the original method
#   and then fixes the result so that the account name is not mangled
#   when using privatelink
def sf_create_connect_args_override(self, url: URL):

    # retval is tuple of empty array and dict ([], {})
    retval = self._orig_create_connect_args(url)

    # the dict has the options including the mangled account name
    opts = retval[1]
    if (
        "host" in opts
        and "account" in opts
        and ".privatelink.snowflakecomputing.com" in opts["host"]
    ):
        opts["account"] = opts["host"].split(".")[0]

    return retval


# Replace the create_connect_args method with the override
SnowflakeDialect.create_connect_args = sf_create_connect_args_override

#
# End monkey patch
#


class SnowflakeBatchAddMode(StrEnum):
    merge = auto()
    insert_notin = auto()
    insert = auto()


class SnowflakeObjectStore(SqlStorage):
    """Snowflake storage backend. Requires existing Snowflake database."""

    def __init__(
        self,
        db_url: str,
        batch_limit: Optional[int] = None,
        table_name: Optional[str] = None,
        max_pending_batches: Optional[int] = None,
        flush_on_batchctx_exit: Optional[bool] = None,
        batch_add_mode: Optional[SnowflakeBatchAddMode] = None,
    ):
        """
        :param batch_add_mode: what type of SQL statement to use when adding many items at one; one of `merge`
            (no duplicates), `insert_notin` (try to avoid duplicates) or `insert` (don't worry about duplicates);
            defaults to `merge`; can be set with the ANYVAR_SNOWFLAKE_BATCH_ADD_MODE
        """
        prepared_db_url = self._preprocess_db_url(db_url)
        super().__init__(
            prepared_db_url,
            batch_limit,
            table_name,
            max_pending_batches,
            flush_on_batchctx_exit,
        )
        self.batch_add_mode = batch_add_mode or os.environ.get(
            "ANYVAR_SNOWFLAKE_BATCH_ADD_MODE", SnowflakeBatchAddMode.merge
        )
        if self.batch_add_mode not in SnowflakeBatchAddMode.__members__:
            raise Exception("batch_add_mode must be one of 'merge', 'insert_notin', or 'insert'")

    def _preprocess_db_url(self, db_url: str) -> str:
        db_url = db_url.replace(".snowflakecomputing.com", "")
        parsed_uri = urlparse(db_url)
        conn_params = {
            key: value[0] if value else None for key, value in parse_qs(parsed_uri.query).items()
        }
        if "private_key" in conn_params:
            self.private_key_param = conn_params["private_key"]
            del conn_params["private_key"]
            parsed_uri = parsed_uri._replace(query=urlencode(conn_params))
        else:
            self.private_key_param = None

        return urlunparse(parsed_uri)

    def _get_connect_args(self, db_url: str) -> dict:
        # if there is a private_key param that is a file, read the contents of file
        if self.private_key_param:
            p_key = None
            pk_passphrase = None
            if "ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE" in os.environ:
                pk_passphrase = os.environ["ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE"].encode()
            if os.path.isfile(self.private_key_param):
                with open(self.private_key_param, "rb") as key:
                    p_key = serialization.load_pem_private_key(
                        key.read(), password=pk_passphrase, backend=default_backend()
                    )
            else:
                p_key = serialization.load_pem_private_key(
                    self.private_key_param.encode(),
                    password=pk_passphrase,
                    backend=default_backend(),
                )

            return {
                "private_key": p_key.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            }
        else:
            return {}

    def create_schema(self, db_conn: Connection):
        check_statement = f"""
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
               AND UPPER(table_name) = UPPER('{self.table_name}')
        """  # nosec B608
        create_statement = f"""
            CREATE TABLE {self.table_name} (
                vrs_id VARCHAR(500) PRIMARY KEY COLLATE 'utf8',
                vrs_object VARIANT
            )
        """  # nosec B608
        result = db_conn.execute(sql_text(check_statement))
        if result.scalar() < 1:
            db_conn.execute(sql_text(create_statement))

    def add_one_item(self, db_conn: Connection, name: str, value: Any):
        insert_query = f"""
            MERGE INTO {self.table_name} t USING (SELECT ? AS vrs_id, ? AS vrs_object) s ON t.vrs_id = s.vrs_id
            WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
            """  # nosec B608
        value_json = json.dumps(value.model_dump(exclude_none=True))
        db_conn.execute(insert_query, (name, value_json))
        _logger.debug("Inserted item %s to %s", name, self.table_name)

    def add_many_items(self, db_conn: Connection, items: list):
        """Bulk inserts the batch values into a TEMP table, then merges into the main {self.table_name} table"""
        tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500) COLLATE 'utf8', vrs_object VARCHAR)"
        insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (?, ?)"
        if self.batch_add_mode == SnowflakeBatchAddMode.insert:
            merge_statement = f"""
                INSERT INTO {self.table_name} (vrs_id, vrs_object)
                SELECT vrs_id, PARSE_JSON(vrs_object) FROM tmp_vrs_objects
            """  # nosec B608
        elif self.batch_add_mode == SnowflakeBatchAddMode.insert_notin:
            merge_statement = f"""
                INSERT INTO {self.table_name} (vrs_id, vrs_object)
                SELECT t.vrs_id, PARSE_JSON(t.vrs_object)
                  FROM tmp_vrs_objects t
                  LEFT OUTER JOIN {self.table_name} v ON v.vrs_id = t.vrs_id
                 WHERE v.vrs_id IS NULL
            """  # nosec B608
        else:
            merge_statement = f"""
                MERGE INTO {self.table_name} v USING tmp_vrs_objects s ON v.vrs_id = s.vrs_id 
                WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
                """  # nosec B608
        drop_statement = "DROP TABLE tmp_vrs_objects"

        # create row data removing duplicates
        #   because if there are duplicates in the source of the merge
        #   Snowflake inserts duplicate rows
        row_data = []
        row_keys = set()
        for name, value in items:
            if name not in row_keys:
                row_keys.add(name)
                row_data.append((name, json.dumps(value.model_dump(exclude_none=True))))
        _logger.info("Created row data for insert, first item is %s", row_data[0])

        db_conn.execute(sql_text(tmp_statement))
        # NB - enclosing the insert statement in sql_text()
        #  causes a "Bind variable ? not set" error from Snowflake
        # It is unclear why this is that case
        db_conn.execute(insert_statement, row_data)
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
             WHERE vrs_object:type = ?
               AND vrs_object:location IN (
                SELECT vrs_id FROM {self.table_name}
                 WHERE vrs_object:start::INTEGER >= ?
                   AND vrs_object:end::INTEGER <= ?
                   AND vrs_object:sequenceReference:refgetAccession = ?)
            """  # nosec B608
        results = db_conn.execute(
            query_str,
            (type, start, stop, refget_accession),
        )
        return [json.loads(row[0]) for row in results if row]
