from abc import abstractmethod
import json
import logging
import os
from threading import Condition, Thread
from typing import Any, Generator, List, Optional, Tuple

import ga4gh.core
from ga4gh.vrs import models
from sqlalchemy import text as sql_text, create_engine
from sqlalchemy.engine import Connection

from anyvar.restapi.schema import VariationStatisticType

from . import _BatchManager, _Storage

_logger = logging.getLogger(__name__)

class SqlStorage(_Storage):
    """Relational database storage backend.  Uses SQLAlchemy as a DB abstraction layer and pool.
    Methods that utilize straightforward SQL are implemented in this class.  Methods that require
    specialized SQL statements must be implemented in a database specific subclass.
    """

    def __init__(
        self,
        db_url: str,
        batch_limit: Optional[int] = None,
        table_name: Optional[str] = None,
        max_pending_batches: Optional[int] = None,
        flush_on_batchctx_exit: Optional[bool] = None,
    ):
        """Initialize DB handler.

        :param db_url: db connection info URL, snowflake://[account_identifier]/?[param=value]&[param=value]...
        :param batch_limit: max size of batch insert queue, defaults to 100000; can be set with
            ANYVAR_SQL_STORE_BATCH_LIMIT environment variable
        :param table_name: table name for storing VRS objects, defaults to `vrs_objects`; can be set with
            ANYVAR_SQL_STORE_TABLE_NAME environment variable
        :param max_pending_batches: maximum number of pending batches allowed before batch queueing blocks; can
            be set with ANYVAR_SQL_STORE_MAX_PENDING_BATCHES environment variable
        :param flush_on_batchctx_exit: whether to call `wait_for_writes()` when exiting the batch manager context;
            defaults to True; can be set with the ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT environment variable

        See https://docs.sqlalchemy.org/en/20/core/connections.html for connection URL info
        """

        # get table name override from environment
        self.table_name = table_name or os.environ.get("ANYVAR_SQL_STORE_TABLE_NAME", "vrs_objects")

        # create the database connection engine
        self.conn_pool = create_engine(db_url, pool_size=1, max_overflow=1, pool_recycle=3600)

        # create the schema objects if necessary
        with self._get_connection() as conn:
            self.create_schema(conn)

        # setup batch handling
        self.batch_manager = SqlStorageBatchManager
        self.batch_mode = False
        self.batch_insert_values = []
        self.batch_limit = batch_limit or int(
            os.environ.get("ANYVAR_SQL_STORE_BATCH_LIMIT", "100000")
        )
        self.flush_on_batchctx_exit = (
            bool(
                os.environ.get(
                    "ANYVAR_SQL_STORE_FLUSH_ON_BATCHCTX_EXIT", "True"
                )
            )
            if flush_on_batchctx_exit is None
            else flush_on_batchctx_exit
        )
        max_pending_batches = max_pending_batches or int(
            os.environ.get("ANYVAR_SQL_STORE_MAX_PENDING_BATCHES", "50")
        )
        self.batch_thread = SqlStorageBatchThread(self, max_pending_batches)
        self.batch_thread.start()

    def _get_connection(self) -> Connection:
        """Returns a database connection"""
        return self.conn_pool.connect()

    @abstractmethod
    def create_schema(self, db_conn: Connection):
        """Add the VRS object table if it does not exist

        :param db_conn: a database connection
        """

    def __repr__(self):
        return str(self.conn_pool)

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
            _logger.debug("Appended item %s to batch queue", name)
            if len(self.batch_insert_values) >= self.batch_limit:
                self.batch_thread.queue_batch(self.batch_insert_values)
                _logger.info(
                    "Queued batch of %s VRS objects for write", len(self.batch_insert_values)
                )
                self.batch_insert_values = []
        else:
            with self._get_connection() as db_conn:
                with db_conn.begin():
                    self.add_one_item(db_conn, name, value)
            _logger.debug("Inserted item %s to %s", name, self.table_name)

    @abstractmethod
    def add_one_item(self, db_conn: Connection, name: str, value: Any):
        """Adds/merges a single item to the database

        :param db_conn: a database connection
        :param name: value for `vrs_id` field
        :param value: value for `vrs_object` field
        """

    @abstractmethod
    def add_many_items(self, db_conn: Connection, items: list):
        """Adds/merges many items to the database

        :param db_conn: a database connection
        :param items: a list of (vrs_id, vrs_object) tuples
        """

    def __getitem__(self, name: str) -> Optional[Any]:
        """Fetch item from DB given key.

        Future issues:
         * Remove reliance on VRS-Python models (requires rewriting the enderef module)

        :param name: key to retrieve VRS object for
        :return: VRS object if available
        :raise NotImplementedError: if unsupported VRS object type (this is WIP)
        """
        with self._get_connection() as conn:
            result = self.fetch_vrs_object(conn, name)
            if result:
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

    def fetch_vrs_object(self, db_conn: Connection, vrs_id: str) -> Optional[Any]:
        """Fetches a single VRS object from the database, return the value as a JSON object

        :param db_conn: a database connection
        :param vrs_id: the VRS ID
        :return: VRS object if available
        """
        result = db_conn.execute(
            sql_text(f"SELECT vrs_object FROM {self.table_name} WHERE vrs_id = :vrs_id"),
            {"vrs_id": vrs_id},
        )
        if result:
            value = result.scalar()
            return json.loads(value) if value and isinstance(value, str) else value
        else:
            return None

    def __contains__(self, name: str) -> bool:
        """Check whether VRS objects table contains ID.

        :param name: VRS ID to look up
        :return: True if ID is contained in vrs objects table
        """
        with self._get_connection() as conn:
            return self.fetch_vrs_object(conn, name) is not None

    def __delitem__(self, name: str) -> None:
        """Delete item (not cascading -- doesn't delete referenced items)

        :param name: key to delete object for
        """
        name = str(name)  # in case str-like
        with self._get_connection() as conn:
            with conn.begin():
                self.delete_vrs_object(conn, name)

    def delete_vrs_object(self, db_conn: Connection, vrs_id: str):
        """Delete a single VRS object

        :param db_conn: a database connection
        :param vrs_id: the VRS ID
        """
        db_conn.execute(
            sql_text(f"DELETE FROM {self.table_name} WHERE vrs_id = :vrs_id"), {"vrs_id": vrs_id}
        )

    def wait_for_writes(self):
        """Returns once any currently pending database modifications have been completed."""
        if hasattr(self, "batch_thread") and self.batch_thread is not None:
            # short circuit if the queue is empty
            with self.batch_thread.cond:
                if not self.batch_thread.pending_batch_list:
                    return

            # queue an empty batch
            batch = []
            self.batch_thread.queue_batch(batch)
            # wait for the batch to be removed from the pending queue
            while True:
                with self.batch_thread.cond:
                    if list(filter(lambda x: x is batch, self.batch_thread.pending_batch_list)):
                        self.batch_thread.cond.wait()
                    else:
                        break

    def close(self):
        """Stop the batch thread and wait for it to complete"""
        if hasattr(self, "batch_thread") and self.batch_thread is not None:
            self.batch_thread.stop()
            self.batch_thread.join()
            self.batch_thread = None
        # Terminate connection if necessary.
        if hasattr(self, "conn_pool") and self.conn_pool is not None:
            self.conn_pool.dispose()
            self.conn_pool = None

    def __del__(self):
        """Tear down DB instance."""
        self.close()

    def __len__(self) -> int:
        """Returns the total number of VRS objects"""
        with self._get_connection() as conn:
            return self.get_vrs_object_count(conn)

    def get_vrs_object_count(self, db_conn: Connection) -> int:
        """Returns the total number of objects

        :param db_conn: a database connection
        """
        result = db_conn.execute(sql_text(f"SELECT COUNT(*) FROM {self.table_name}"))
        return result.scalar()

    def get_variation_count(self, variation_type: VariationStatisticType) -> int:
        """Get total # of registered variations of requested type.

        :param variation_type: variation type to check
        :return: total count
        """
        with self._get_connection() as conn:
            if variation_type == VariationStatisticType.SUBSTITUTION:
                return self.substitution_count(conn)
            elif variation_type == VariationStatisticType.INSERTION:
                return self.insertion_count(conn)
            elif variation_type == VariationStatisticType.DELETION:
                return self.deletion_count(conn)
            else:
                return (
                    self.substitution_count(conn)
                    + self.deletion_count(conn)
                    + self.insertion_count(conn)
                )

    @abstractmethod
    def deletion_count(self, db_conn: Connection) -> int:
        """Returns the total number of deletions

        :param db_conn: a database connection
        """

    @abstractmethod
    def substitution_count(self, db_conn: Connection) -> int:
        """Returns the total number of substitutions

        :param db_conn: a database connection
        """

    @abstractmethod
    def insertion_count(self, db_conn: Connection):
        """Returns the total number of insertions

        :param db_conn: a database connection
        """

    def __iter__(self):
        """Iterates over all VRS objects in the database"""
        with self._get_connection() as conn:
            iter = self.fetch_all_vrs_objects(conn)
            for obj in iter:
                yield obj

    def fetch_all_vrs_objects(self, db_conn: Connection) -> Generator[Any, Any, Any]:
        """Returns a generator that iterates over all VRS objects in the database
        in no specific order

        :param db_conn: a database connection
        """
        result = db_conn.execute(sql_text(f"SELECT vrs_object FROM {self.table_name}"))
        for row in result:
            if row:
                value = row["vrs_object"]
                yield json.loads(value) if value and isinstance(value, str) else value
            else:
                yield None

    def keys(self):
        """Returns a list of all VRS IDs in the database"""
        with self._get_connection() as conn:
            return self.fetch_all_vrs_ids(conn)

    def fetch_all_vrs_ids(self, db_conn: Connection) -> List:
        """Returns a list of all VRS IDs in the database

        :param db_conn: a database connection
        """
        result = db_conn.execute(sql_text(f"SELECT vrs_id FROM {self.table_name}"))
        return [row[0] for row in result]

    def search_variations(self, refget_accession: str, start: int, stop: int):
        """Find all alleles that were registered that are in 1 genomic region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of VRS Alleles that have locations referenced as identifiers
        """
        with self._get_connection() as conn:
            return self.search_vrs_objects(conn, "Allele", refget_accession, start, stop)

    @abstractmethod
    def search_vrs_objects(
        self, db_conn: Connection, type: str, refget_accession: str, start: int, stop: int
    ) -> List[Any]:
        """Find all VRS objects of the particular type and region

        :param type: the type of VRS object to search for
        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of VRS objects
        """

    def wipe_db(self):
        """Remove all stored records from the database"""
        with self._get_connection() as conn:
            with conn.begin():
                conn.execute(sql_text(f"DELETE FROM {self.table_name}"))

    def num_pending_batches(self) -> int:
        """Returns the number of pending insert batches"""
        if self.batch_thread:
            return len(self.batch_thread.pending_batch_list)
        else:
            return 0


class SqlStorageBatchManager(_BatchManager):
    """Context manager enabling bulk insertion statements

    Use in cases like VCF ingest when intaking large amounts of data at once.
    Insertion batches are processed by a background thread.
    """

    def __init__(self, storage: SqlStorage):
        """Initialize context manager.

        :param storage: SqlStorage instance to manage. Should be taken from the active
        AnyVar instance -- otherwise it won't be able to delay insertions.
        :raise ValueError: if `storage` param is not a `SqlStorage` instance
        """
        if not isinstance(storage, SqlStorage):
            raise ValueError("SqlStorageBatchManager requires a SqlStorage instance")
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
            _logger.error(
                f"Sql storage batch manager encountered exception {exc_type}: {exc_value}"
            )
            _logger.exception(exc_value)
            return False
        self._storage.batch_thread.queue_batch(self._storage.batch_insert_values)
        self._storage.batch_mode = False
        self._storage.batch_insert_values = None
        if self._storage.flush_on_batchctx_exit:
            self._storage.wait_for_writes()
        return True


class SqlStorageBatchThread(Thread):
    """Background thread that merges VRS objects into the database"""

    def __init__(self, sql_store: SqlStorage, max_pending_batches: int):
        """Constructs a new background thread

        :param conn_pool: SQLAlchemy connection pool
        """
        super().__init__(daemon=True)
        self.sql_store = sql_store
        self.cond = Condition()
        self.run_flag = True
        self.pending_batch_list = []
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
            if batch_insert_values is not None:
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
        try:
            with self.sql_store._get_connection() as conn:
                with conn.begin():
                    self.sql_store.add_many_items(conn, batch_insert_values)
        except Exception:
            _logger.exception("Failed to merge VRS object batch into database")
