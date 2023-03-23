import json
from typing import Any, Optional

import psycopg
from ga4gh.core import is_pjs_instance
from ga4gh.vrs import models
from ga4gh.vrsatile.pydantic.vrs_models import VRSTypes

from anyvar.restapi.schema import VariationStatisticType

from . import _Storage

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class PostgresObjectStore(_Storage):
    """PostgreSQL storage backend. Currently, this is our recommended storage
    approach.
    """

    def __init__(self, db_url: str):
        """Initialize PostgreSQL DB handler.

        :param db_url: libpq connection info URL
        """
        self.conn = psycopg.connect(db_url, autocommit=True)
        self.ensure_schema_exists()

    def _create_schema(self):
        """Add DB schema."""
        create_statement = """
        CREATE TABLE vrs_objects (
            id BIGSERIAL PRIMARY KEY,
            vrs_id TEXT,
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
        assert is_pjs_instance(value), "ga4gh.vrs object value required"
        name = str(name)  # in case str-like
        value_json = json.dumps(value.as_dict())
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vrs_objects (vrs_id, vrs_object) VALUES (%s, %s);",
                [name, value_json]
            )


    def __getitem__(self, name: str) -> Optional[Any]:
        """Fetch item from DB given key.

        TODO
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
            print(object_type)
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
            return cur.stream(
                "SELECT * FROM vrs_objects;"
            )

    def keys(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT vrs_id FROM vrs_objects;")
            result = cur.fetchall()
        return result

    def search_variations(self, ga4gh_accession_id, start, stop):
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
            )
            """
        )
        with self.conn.cursor() as cur:
            cur.execute(query_str, [start, stop, ga4gh_accession_id])
            results = cur.fetchall()
        return [vrs_object[0] for vrs_object in results if vrs_object]
