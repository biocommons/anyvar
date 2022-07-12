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
        data = self.conn._fetchone(f"select count(*) as c from vrs_objects where vrs_object ->> 'type' = 'Allele'")
        return data[0]

    def deletion_count(self):
        data = self.conn._fetchone(f"select count(*) as c from vrs_objects where length(vrs_object -> 'state' ->> 'sequence') = 0")
        return data[0]

    def substitution_count(self):
        data = self.conn._fetchone(f"select count(*) as c from vrs_objects where length(vrs_object -> 'state' ->> 'sequence') = 1")
        return data[0]

    def insertion_count(self):
        data = self.conn._fetchone(f"select count(*) as c from vrs_objects where length(vrs_object -> 'state' ->> 'sequence') > 1")
        return data[0]

    def __iter__(self):
        return self._db.__iter__()

    def keys(self):
        return self._db.keys()


