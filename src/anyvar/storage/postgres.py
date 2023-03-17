import json
import logging

import ga4gh.vrs
from ga4gh.core import is_pjs_instance

from anyvar.restapi.schema import VariationStatisticType

from . import _Storage
from .pg_utility import PostgresClient

_logger = logging.getLogger(__name__)

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class PostgresObjectStore(_Storage):
    """Super simple key-value storage for GA4GH VRS objects"""

    def __init__(self, db_url):
        self.conn = PostgresClient(db_url=db_url)
        self.conn._connect()

    def __repr__(self):
        return str(self.conn)

    def __setitem__(self, name, value):
        assert is_pjs_instance(value), "ga4gh.vrs object value required"
        name = str(name)  # in case str-like
        d = value.as_dict()
        j = json.dumps(d)
        self.conn._insert_one(
            "insert into vrs_objects (vrs_id, vrs_object) values (%s,%s)", [name, j]
        )

    def __getitem__(self, name):
        name = str(name)  # in case str-like
        data = self.conn._fetchone(
            "select vrs_object from vrs_objects where vrs_id = %s",
            [name]
        )
        if data:
            data = data[0]
            typ = data["type"]
            vo = ga4gh.vrs.models[typ](**data)
            return vo

    def __contains__(self, name):
        name = str(name)  # in case str-like
        return self._db.__contains__(name)

    def __delitem__(self, name):
        name = str(name)  # in case str-like
        del self._db[name]

    def __del__(self):
        self._db.close()

    def __len__(self):
        data = self.conn._fetchone(
            "select count(*) as c from vrs_objects "
            "where vrs_object ->> 'type' = 'Allele'"
        )
        return data[0]

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
            return self._substitution_count() + self._deletion_count() + \
                self._insertion_count()

    def _deletion_count(self):
        data = self.conn._fetchone(
            "select count(*) as c from vrs_objects "
            "where length(vrs_object -> 'state' ->> 'sequence') = 0"
        )
        return data[0]

    def _substitution_count(self):
        data = self.conn._fetchone(
            "select count(*) as c from vrs_objects "
            "where length(vrs_object -> 'state' ->> 'sequence') = 1"
        )
        return data[0]

    def _insertion_count(self):
        data = self.conn._fetchone(
            "select count(*) as c from vrs_objects "
            "where length(vrs_object -> 'state' ->> 'sequence') > 1"
        )
        return data[0]

    def __iter__(self):
        return self._db.__iter__()

    def keys(self):
        return self._db.keys()

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
        data = self.conn._fetchall(query_str, [start, stop, ga4gh_accession_id])
        return [vrs_object[0] for vrs_object in data if vrs_object]
