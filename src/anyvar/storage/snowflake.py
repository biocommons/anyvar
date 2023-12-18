import json
import logging
import os
from threading import Condition, Thread
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import ga4gh.core
from ga4gh.vrs import models
import snowflake.connector
from snowflake.connector import SnowflakeConnection

from anyvar.restapi.schema import VariationStatisticType

from . import _BatchManager, _Storage

_logger = logging.getLogger(__name__)


class SnowflakeObjectStore(_Storage):
    """Snowflake storage backend. Requires existing Snowflake database."""

    def __init__(
        self,
        db_url: str,
        batch_limit: int = None,
        table_name: str = None,
        max_pending_batches: int = None,
    ):
        """Initialize Snowflake DB handler.

        :param db_url: snowflake connection info URL, snowflake://[account_identifier]/?[param=value]&[param=value]...
        :param batch_limit: max size of batch insert queue, defaults to 100000; can be set with
            ANYVAR_SNOWFLAKE_STORE_BATCH_LIMIT environment variable
        :param table_name: table name for storing VRS objects, defaults to `vrs_objects`; can be set with
            ANYVAR_SNOWFLAKE_STORE_TABLE_NAME environment variable
        :param max_pending_batches: maximum number of pending batches allowed before batch queueing blocks; can
            be set with ANYVAR_SNOWFLAKE_STORE_MAX_PENDING_BATCHES environment variable

        See https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api for full list
            of database connection url parameters
        """
        # specify that bind variables in queries should be indicated with a question mark
        snowflake.connector.paramstyle = "qmark"

        # get table name override from environment
        self.table_name = table_name or str(
            os.environ.get("ANYVAR_SNOWFLAKE_STORE_TABLE_NAME", "vrs_objects")
        )

        # parse the db url and extract the account name and conn params
        parsed_uri = urlparse(db_url)
        account_name = parsed_uri.hostname.replace(".snowflakecomputing.com", "")
        conn_params = {
            key: value[0] if value else None for key, value in parse_qs(parsed_uri.query).items()
        }

        # log sanitized connection parameters
        if _logger.isEnabledFor(logging.DEBUG):
            sanitized_conn_params = conn_params.copy()
            for secret_param in ["password", "private_key"]:
                if secret_param in sanitized_conn_params:
                    sanitized_conn_params[secret_param] = "****sanitized****"

            _logger.debug(
                "Connecting to Snowflake account %s with params %s",
                account_name,
                sanitized_conn_params,
            )
        # log connection attempt
        else:
            _logger.info(
                "Connecting to Snowflake account %s",
                account_name,
            )

        # create the database connection and ensure it is setup
        self.conn = snowflake.connector.connect(account=account_name, **conn_params)
        self.ensure_schema_exists()

        # setup batch handling
        self.batch_manager = SnowflakeBatchManager
        self.batch_mode = False
        self.batch_insert_values = []
        self.batch_limit = batch_limit or int(
            os.environ.get("ANYVAR_SNOWFLAKE_STORE_BATCH_LIMIT", "100000")
        )
        max_pending_batches = max_pending_batches or int(
            os.environ.get("ANYVAR_SNOWFLAKE_STORE_MAX_PENDING_BATCHES", "50")
        )
        self.batch_thread = SnowflakeBatchThread(self.conn, self.table_name, max_pending_batches)
        self.batch_thread.start()

    def _create_schema(self):
        """Add the VRS object table if it does not exist"""
        # self.table_name is only modifiable via environment variable or direct instantiation of the SnowflakeObjectStore
        create_statement = f"""
        CREATE TABLE {self.table_name} (
            vrs_id VARCHAR(500) PRIMARY KEY,
            vrs_object VARIANT
        );
        """  # nosec B608
        _logger.info("Creating VRS object table %s", self.table_name)
        with self.conn.cursor() as cur:
            cur.execute(create_statement)

    def ensure_schema_exists(self):
        """Check that VRS object table exists and create it if it does not"""
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM information_schema.tables 
                 WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
                 AND UPPER(table_name) = UPPER('{self.table_name}');
                """  # nosec B608
            )
            result = cur.fetchone()

        if result is None or result[0] <= 0:
            self._create_schema()

    def __repr__(self):
        return str(self.conn)

    def __setitem__(self, name: str, value: Any):
        """Add item to database. If batch mode is on, add item to batch and submit batch
        for write only if batch size is exceeded.

        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """
        assert ga4gh.core.is_pydantic_instance(value), "ga4gh.vrs object value required"
        name = str(name)  # in case str-like
        if self.batch_mode:
            self.batch_insert_values.append((name, value))
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("Appended item %s to batch queue", name)
            if len(self.batch_insert_values) >= self.batch_limit:
                self.batch_thread.queue_batch(self.batch_insert_values)
                _logger.info(
                    "Queued batch of %s VRS objects for write", len(self.batch_insert_values)
                )
                self.batch_insert_values = []
        else:
            value_json = json.dumps(value.model_dump(exclude_none=True))
            insert_query = f"""
                MERGE INTO {self.table_name} t USING (SELECT ? AS vrs_id, ? AS vrs_object) s ON t.vrs_id = s.vrs_id
                WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object));
                """  # nosec B608
            with self.conn.cursor() as cur:
                cur.execute(insert_query, [name, value_json])
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug("Inserted item %s to %s", name, self.table_name)

    def __getitem__(self, name: str) -> Optional[Any]:
        """Fetch item from DB given key.

        Future issues:
         * Remove reliance on VRS-Python models (requires rewriting the enderef module)

        :param name: key to retrieve VRS object for
        :return: VRS object if available
        :raise NotImplementedError: if unsupported VRS object type (this is WIP)
        """
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT vrs_object FROM {self.table_name} WHERE vrs_id = ?;", [name]  # nosec B608
            )
            result = cur.fetchone()
        if result:
            result = json.loads(result[0])
            object_type = result["type"]
            if object_type == "Allele":
                return models.Allele(**result)
            elif object_type == "CopyNumberCount":
                return models.CopyNumberCount(**result)
            elif object_type == "CopyNumberChange":
                return models.CopyNumberChange(**result)
            elif object_type == "SequenceLocation":
                return models.SequenceLocation(**result)
            else:
                raise NotImplementedError

    def __contains__(self, name: str) -> bool:
        """Check whether VRS objects table contains ID.

        :param name: VRS ID to look up
        :return: True if ID is contained in vrs objects table
        """
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {self.table_name} WHERE vrs_id = ?;", [name]  # nosec B608
            )
            result = cur.fetchone()
        return result[0] > 0 if result else False

    def __delitem__(self, name: str) -> None:
        """Delete item (not cascading -- doesn't delete referenced items)

        :param name: key to delete object for
        """
        name = str(name)  # in case str-like
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table_name} WHERE vrs_id = ?;", [name])  # nosec B608
        self.conn.commit()

    def close(self):
        """Stop the batch thread and wait for it to complete"""
        if self.batch_thread is not None:
            self.batch_thread.stop()
            self.batch_thread.join()
            self.batch_thread = None
        """Terminate connection if necessary."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """Tear down DB instance."""
        self.close()

    def __len__(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS c FROM {self.table_name}
                WHERE vrs_object:type = 'Allele';
                """  # nosec B608
            )
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        """Get total # of registered variations of requested type.

        :param variation_type: variation type to check
        :return: total count
        """
        if variation_type == VariationStatisticType.SUBSTITUTION:
            return self._substitution_count()
        elif variation_type == VariationStatisticType.INSERTION:
            return self._insertion_count()
        elif variation_type == VariationStatisticType.DELETION:
            return self._deletion_count()
        else:
            return self._substitution_count() + self._deletion_count() + self._insertion_count()

    def _deletion_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {self.table_name}
                 WHERE LENGTH(vrs_object:state:sequence) = 0;
                """  # nosec B608
            )
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def _substitution_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {self.table_name}
                 WHERE LENGTH(vrs_object:state:sequence) = 1;
                """  # nosec B608
            )
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def _insertion_count(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {self.table_name}
                 WHERE LENGTH(vrs_object:state:sequence) > 1
                """  # nosec B608
            )
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def __iter__(self):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {self.table_name};")  # nosec B608
            while True:
                _next = cur.fetchone()
                if _next is None:
                    break
                yield _next

    def keys(self):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT vrs_id FROM {self.table_name};")  # nosec B608
            result = [row[0] for row in cur.fetchall()]
        return result

    def search_variations(self, refget_accession: str, start: int, stop: int):
        """Find all alleles that were registered that are in 1 genomic region

        Args:
            refget_accession (str): refget accession (SQ. identifier)
            start (int): Start genomic region to query
            stop (iint): Stop genomic region to query

        Returns:
            A list of VRS Alleles that have locations referenced as identifiers
        """
        query_str = f"""
            SELECT vrs_object FROM {self.table_name}
            WHERE vrs_object:location IN (
                SELECT vrs_id FROM {self.table_name}
                WHERE vrs_object:start::INTEGER >= ?
                AND vrs_object:end::INTEGER <= ?
                AND vrs_object:sequenceReference:refgetAccession = ?
            );
            """  # nosec B608
        with self.conn.cursor() as cur:
            cur.execute(query_str, [start, stop, refget_accession])
            results = cur.fetchall()
        return [json.loads(vrs_object[0]) for vrs_object in results if vrs_object]

    def wipe_db(self):
        """Remove all stored records from {self.table_name} table."""
        with self.conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table_name};")  # nosec B608

    def num_pending_batches(self):
        if self.batch_thread:
            return len(self.batch_thread.pending_batch_list)
        else:
            return 0


class SnowflakeBatchManager(_BatchManager):
    """Context manager enabling bulk insertion statements

    Use in cases like VCF ingest when intaking large amounts of data at once.
    Insertion batches are processed by a background thread.
    """

    def __init__(self, storage: SnowflakeObjectStore):
        """Initialize context manager.

        :param storage: Snowflake instance to manage. Should be taken from the active
        AnyVar instance -- otherwise it won't be able to delay insertions.
        :raise ValueError: if `storage` param is not a `SnowflakeObjectStore` instance
        """
        if not isinstance(storage, SnowflakeObjectStore):
            raise ValueError("SnowflakeBatchManager requires a SnowflakeObjectStore instance")
        self._storage = storage

    def __enter__(self):
        """Enter managed context."""
        self._storage.batch_insert_values = []
        self._storage.batch_mode = True

    def __exit__(
        self, exc_type: Optional[type], exc_value: Optional[BaseException], traceback: Optional[Any]
    ) -> bool:
        """Handle exit from context management.  Hands off final batch to background bulk insert processor.

        :param exc_type: type of exception encountered, if any
        :param exc_value: exception value
        :param traceback: traceback for context of exception
        :return: True if no exceptions encountered, False otherwise
        """
        if exc_type is not None:
            self._storage.batch_insert_values = None
            self._storage.batch_mode = False
            _logger.error(f"Snowflake batch manager encountered exception {exc_type}: {exc_value}")
            _logger.exception(exc_value)
            return False
        self._storage.batch_thread.queue_batch(self._storage.batch_insert_values)
        self._storage.batch_mode = False
        self._storage.batch_insert_values = None
        return True


class SnowflakeBatchThread(Thread):
    """Background thread that merges VRS objects into the database"""

    def __init__(self, conn: SnowflakeConnection, table_name: str, max_pending_batches: int):
        """Constructs a new background thread

        :param conn: Snowflake connection
        """
        super().__init__(daemon=True)
        self.conn = conn
        self.cond = Condition()
        self.run_flag = True
        self.pending_batch_list = []
        self.table_name = table_name
        self.max_pending_batches = max_pending_batches

    def run(self):
        """As long as run_flag is true, waits then processes pending batches"""
        while self.run_flag:
            with self.cond:
                self.cond.wait()
            self.process_pending_batches()

    def stop(self):
        """Sets the run_flag to false and notifies"""
        self.run_flag = False
        with self.cond:
            self.cond.notify()

    def queue_batch(self, batch_insert_values: List[Tuple]):
        """Adds a batch to the pending list.  If the pending batch list is already at its max size, waits until there is room

        :param batch_insert_values: list of tuples where each tuple consists of (vrs_id, vrs_object)
        """
        with self.cond:
            if batch_insert_values:
                _logger.info("Queueing batch of %s items", len(batch_insert_values))
                while len(self.pending_batch_list) >= self.max_pending_batches:
                    _logger.debug("Pending batch queue is full, waiting for space...")
                    self.cond.wait()
                self.pending_batch_list.append(batch_insert_values)
                _logger.info("Queued batch of %s items", len(batch_insert_values))
            self.cond.notify_all()

    def process_pending_batches(self):
        """As long as batches are available for processing, merges them into the database"""
        _logger.info("Processing %s queued batches", len(self.pending_batch_list))
        while True:
            batch_insert_values = None
            with self.cond:
                if len(self.pending_batch_list) > 0:
                    batch_insert_values = self.pending_batch_list[0]
                    del self.pending_batch_list[0]
                    self.cond.notify_all()
                else:
                    self.cond.notify_all()
                    break

            if batch_insert_values:
                self._run_copy_insert(batch_insert_values)
                _logger.info("Processed queued batch of %s items", len(batch_insert_values))

    def _run_copy_insert(self, batch_insert_values):
        """Bulk inserts the batch values into a TEMP table, then merges into the main {self.table_name} table"""

        try:
            tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500), vrs_object VARCHAR);"
            insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (?, ?);"
            merge_statement = f"""
                MERGE INTO {self.table_name} v USING tmp_vrs_objects s ON v.vrs_id = s.vrs_id 
                WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object));
                """  # nosec B608
            drop_statement = "DROP TABLE tmp_vrs_objects;"

            row_data = [
                (name, json.dumps(value.model_dump(exclude_none=True)))
                for name, value in batch_insert_values
            ]
            _logger.info("Created row data for insert, first item is %s", row_data[0])

            with self.conn.cursor() as cur:
                cur.execute(tmp_statement)
                cur.executemany(insert_statement, row_data)
                cur.execute(merge_statement)
                cur.execute(drop_statement)
            self.conn.commit()
        except Exception:
            _logger.exception("Failed to merge VRS object batch into database")
        finally:
            self.conn.rollback()
