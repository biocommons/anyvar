import collections
import datetime
import functools
import logging
import os
import shelve
import json
import zlib

import ga4gh.vrs
from ga4gh.core import is_pjs_instance
from .pg_utility import PostgresClient

_logger = logging.getLogger(__name__)

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class PostgresObjectStore:
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
        self.conn._insert_one(f"insert into vrs_objects (vrs_id, vrs_object) values (%s,%s)", [name, j])

    def __getitem__(self, name):
        name = str(name)  # in case str-like
        data = self.conn._fetchone(f"select vrs_object from vrs_objects where vrs_id = %s", [name])
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
        return self._db.__len__()

    def __iter__(self):
        return self._db.__iter__()

    def keys(self):
        return self._db.keys()

    def find_alleles(self, ga4gh_accession_id, start, stop):
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


