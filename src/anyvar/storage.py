import collections
import datetime
import functools
import logging
import os
import shelve
import json
import zlib

import ga4gh.vr
from ga4gh.vr.utils import is_vr_instance


_logger = logging.getLogger(__name__)

silos = "locations alleles haplotypes genotypes variationsets relations texts".split()


class Storage:
    """Super simple key-value storage for GA4GH VR objects"""

    def __init__(self, filename):
        _logger.debug(f"Opening {filename}")
        self._db = shelve.open(filename)
    
    def __setitem__(self, name, value):
        assert is_vr_instance(value), "ga4gh.vr object value required"
        name = str(name)        # in case str-like
        d = value.as_dict()
        j = json.dumps(d)
        e = j.encode("utf-8")
        c = zlib.compress(e)
        self._db[name] = c
        
    def __getitem__(self, name):
        _logger.debug(f"Fetching {name}")
        name = str(name)        # in case str-like
        data = json.loads(zlib.decompress(self._db[name]).decode("UTF-8"))
        typ = data["type"]
        vo = ga4gh.vr.models[typ](**data)
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


class AnyVarStorage:
    def __init__(self, directory):
        def _mk_silo(silo):
            fn = os.path.join(directory, silo)
            return Storage(fn)
            
        os.makedirs(directory, exist_ok=True)

        for silo in silos:
            _logger.info(f"Making silo {silo}")
            self.__setattr__(silo, _mk_silo(silo))
