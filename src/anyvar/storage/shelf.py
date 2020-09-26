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


_logger = logging.getLogger(__name__)

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class ShelfStorage(collections.abc.MutableMapping):
    """Super simple key-value storage for GA4GH VRS objects"""

    def __init__(self, filename):
        _logger.debug(f"Opening {filename}")
        self._fn = filename
        self._db = shelve.open(self._fn)
    
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__qualname__} filename={self._fn}>"

    def __setitem__(self, name, value):
        assert is_pjs_instance(value), "ga4gh.vrs object value required"
        name = str(name)        # in case str-like
        d = value.as_dict()
        j = json.dumps(d)
        e = j.encode("utf-8")
        c = zlib.compress(e)
        self._db[name] = c
        
    def __getitem__(self, name):
        name = str(name)        # in case str-like
        data = json.loads(zlib.decompress(self._db[name]).decode("UTF-8"))
        typ = data["type"]
        vo = ga4gh.vrs.models[typ](**data)
        return vo

    def __contains__(self, name):
        name = str(name)        # in case str-like
        return self._db.__contains__(name)

    def __delitem__(self, name):
        name = str(name)        # in case str-like
        del self._db[name]

    def __del__(self):
        self._db.close()

    def __len__(self):
        return self._db.__len__()

    def __iter__(self):
        return self._db.__iter__()

    def keys(self):
        return self._db.keys()


