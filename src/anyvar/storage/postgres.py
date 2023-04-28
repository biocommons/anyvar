import json
import logging
from typing import Any, Optional

import psycopg
from ga4gh.core import is_pjs_instance
from ga4gh.vrs import models
from ga4gh.vrsatile.pydantic.vrs_models import VRSTypes

from anyvar.restapi.schema import VariationStatisticType

from . import _BatchManager, _Storage

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


_logger = logging.getLogger(__name__)


class PostgresObjectStore(_Storage):
    """PostgreSQL storage backend. Currently, this is our recommended storage
    approach.
    """

    def __init__(self, db_url: str, batch_limit: int = 65536):
        """Initialize PostgreSQL DB handler.

        :param db_url: libpq connection info URL
        :param batch_limit: max size of batch insert queue
        """
        self.conn = psycopg.connect(db_url, autocommit=True)
        self.ensure_schema_exists()

        self.batch_manager = PostgresBatchManager
        self.batch_mode = False
        self.batch_insert_values = []
        self.batch_limit = batch_limit

    def _create_schema(self):
        """Add DB schema."""
        create_statement = """
        CREATE TABLE vrs_objects (
            vrs_id TEXT PRIMARY KEY,
            vrs_object JSONB
        );
        """
        with self.conn.cursor() as cur:
            cur.execute(create_statement)

    def ensure_schema_exists(self):
        """Check that DB schema is in place."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')")  # noqa: E501
            result = cur.fetchone()
        if result and result[0]:
            return
        self._create_schema()

    def __repr__(self):
        return str(self.conn)

    def __setitem__(self, name: str, value: Any):
        """Add item to database. If batch mode is on, add item to queue and write only
        if queue size is exceeded.

        :name: value for `vrs_id` field
        :value: value for `vrs_object` field
        """
        assert is_pjs_instance(value), "ga4gh.vrs object value required"
        name = str(name)  # in case str-like
        value_json = json.dumps(value.as_dict())
        if self.batch_mode:
            self.batch_insert_values.append((name, value_json))
            if len(self.batch_insert_values) > self.batch_limit:
                self.copy_insert()
        else:
            insert_query = "INSERT INTO vrs_objects (vrs_id, vrs_object) VALUES (%s, %s) ON CONFLICT DO NOTHING;"  # noqa: E501
            with self.conn.cursor() as cur:
                cur.execute(insert_query, [name, value_json])

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
                "SELECT vrs_object FROM vrs_objects WHERE vrs_id = %s;",
                [name]
            )
            result = cur.fetchone()
        if result:
            result = result[0]
            object_type = result["type"]
            if object_type == VRSTypes.ALLELE:
                return models.Allele(**result)
            elif object_type == VRSTypes.TEXT:
                return models.Allele(**result)
            elif object_type == VRSTypes.SEQUENCE_LOCATION:
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
                "SELECT EXISTS (SELECT 1 FROM vrs_objects WHERE vrs_id = %s);",
                [name]
            )
            result = cur.fetchone()
        return result[0] if result else False

    def __delitem__(self, name: str) -> None:
        """Delete item (not cascading -- doesn't delete referenced items)

        :param name: key to delete object for
        """
        name = str(name)  # in case str-like
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM vrs_objects WHERE vrs_id = %s;",
                [name]
            )
        self.conn.commit()

    def close(self):
        """Terminate connection if necessary."""
        if self.conn is not None:
            self.conn.close()

    def __del__(self):
        """Tear down DB instance."""
        self.close()

    def __len__(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS c FROM vrs_objects
                WHERE vrs_object ->> 'type' = 'Allele';
            """)
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
        if variation_type == VariationStatisticType.TEXT:
            return self._text_count()
        if variation_type == VariationStatisticType.SUBSTITUTION:
            return self._substitution_count()
        elif variation_type == VariationStatisticType.INSERTION:
            return self._insertion_count()
        elif variation_type == VariationStatisticType.DELETION:
            return self._deletion_count()
        else:
            return self._substitution_count() + self._deletion_count() + \
                self._insertion_count()

    def _text_count(self) -> int:
        """Get total # of registered text variations.

        :return: total count
        """
        with self.conn.cursor() as cur:
            query = """
            SELECT COUNT(1) AS c FROM vrs_objects
            WHERE vrs_object ->> 'type' = 'Text'
            """
            cur.execute(query)
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def _deletion_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("""
                select count(*) as c from vrs_objects
                where length(vrs_object -> 'state' ->> 'sequence') = 0;
            """)
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def _substitution_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("""
                select count(*) as c from vrs_objects
                where length(vrs_object -> 'state' ->> 'sequence') = 1;
            """)
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def _insertion_count(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                select count(*) as c from vrs_objects
                where length(vrs_object -> 'state' ->> 'sequence') > 1
            """)
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return 0

    def __iter__(self):
        with self.conn.cursor() as cur:
            return cur.stream("SELECT * FROM vrs_objects;")

    def keys(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT vrs_id FROM vrs_objects;")
            result = cur.fetchall()
        return result

    def search_variations(self, ga4gh_accession_id: str, start: int, stop: int):
        """Find all alleles that were registered that are in 1 genomic region

        Args:
            ga4gh_accession_id (str): ga4gh accession for sequence identifier
            start (int): Start genomic region to query
            stop (iint): Stop genomic region to query

        Returns:
            A list of VRS Alleles that have locations referenced as identifiers
        """
        query_str = (
            """
            SELECT vrs_object FROM vrs_objects
            WHERE vrs_object->>'location' IN (
                SELECT vrs_id FROM vrs_objects
                WHERE CAST (vrs_object->'interval'->'start'->>'value' as INTEGER) >= %s
                AND CAST (vrs_object->'interval'->'end'->>'value' as INTEGER) <= %s
                AND vrs_object->>'sequence_id' = %s
            );
            """
        )
        with self.conn.cursor() as cur:
            cur.execute(query_str, [start, stop, ga4gh_accession_id])
            results = cur.fetchall()
        return [vrs_object[0] for vrs_object in results if vrs_object]

    def wipe_db(self):
        """Remove all stored records from vrs_objects table."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM vrs_objects;")

    def copy_insert(self):
        """Perform copy-based insert, enabling much faster writes for large, repeated
        insert statements, using insert parameters stored in `self.batch_insert_values`.

        Because we may be writing repeated records, we need to handle conflicts, which
        isn't available for COPY. The workaround (https://stackoverflow.com/a/49836011)
        is to make a temporary table for each COPY statement, and then handle
        conflicts when moving data over from that table to vrs_objects.
        """
        tmp_statement = "CREATE TEMP TABLE tmp_table (LIKE vrs_objects INCLUDING DEFAULTS);"  # noqa: E501
        copy_statement = "COPY tmp_table (vrs_id, vrs_object) FROM STDIN;"
        insert_statement = "INSERT INTO vrs_objects SELECT * FROM tmp_table ON CONFLICT DO NOTHING;"  # noqa: E501
        drop_statement = "DROP TABLE tmp_table;"
        from timeit import default_timer as timer
        start = timer()
        with self.conn.cursor() as cur:
            cur.execute(tmp_statement)
            with cur.copy(copy_statement) as copy:
                for row in self.batch_insert_values:
                    copy.write_row(row)
            cur.execute(insert_statement)
            cur.execute(drop_statement)
        self.conn.commit()
        self.batch_insert_values = []
        end = timer()
        print(end - start)


class PostgresBatchManager(_BatchManager):
    """Context manager enabling batch insertion statements via Postgres COPY command.

    Use in cases like VCF ingest when intaking large amounts of data at once.
    """

    def __init__(self, storage: PostgresObjectStore):
        """Initialize context manager.

        :param storage: Postgres instance to manage. Should be taken from the active
        AnyVar instance -- otherwise it won't be able to delay insertions.
        """
        if not isinstance(storage, PostgresObjectStore):
            raise ValueError(
                "PostgresBatchManager requires a PostgresObjectStore instance"
            )
        self._storage = storage

    def __enter__(self):
        """Enter managed context."""
        self._storage.batch_insert_values = []
        self._storage.batch_mode = True

    def __exit__(
        self, exc_type: Optional[type], exc_value: Optional[BaseException],
        traceback: Optional[Any]
    ) -> bool:
        """Handle exit from context management. This method is responsible for
        committing or rolling back any staged inserts.

        :param exc_type: type of exception encountered, if any
        :param exc_value: exception value
        :param traceback: traceback for context of exception
        :return: True if no exceptions encountered, False otherwise
        """
        if exc_type is not None:
            self._storage.conn.rollback()
            self._storage.batch_insert_values = []
            self._storage.batch_mode = False
            _logger.error(
                f"Postgres batch manager encountered exception {exc_type}: {exc_value}"
            )
            return False
        self._storage.copy_insert()
        self._storage.batch_mode = False
        return True
