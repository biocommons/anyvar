"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import collections.abc
import logging

from ga4gh.core import ga4gh_identify
import ga4gh.vr

from ga4gh.vr.extras.translator import Translator


_logger = logging.getLogger(__name__)


class AnyVar:
    def __init__(self, /, data_proxy, storage):
        if not isinstance(storage, collections.abc.MutableMapping):
            _logger.warning("AnyVar(storage=) should be a mutable mapping; you're on your own")

        self.data_proxy = data_proxy
        self.storage = storage
        self.translator = Translator(data_proxy=data_proxy)

    # TODO: instead of storing in separate "silos" (see storage), just
    # store in one.
    # Also, use vr_enref to do this, which will recurse for us.

    def add_allele(self, allele):
        allele._id = ga4gh_identify(allele)
        self.storage.alleles[allele._id] = allele
        self.add_location(allele.location)
        _logger.info(f"Added Allele {allele._id}")
        return allele

    def add_location(self, location):
        location._id = ga4gh_identify(location)
        self.storage.locations[location._id] = location
        return location

    def add_text(self, text):
        text._id = ga4gh_identify(text)
        self.storage.texts[text._id] = text
        return text


    # TODO: replace getters with direct access
    def get_allele(self, id):
        return self.storage.alleles[id]

    def get_location(self, id):
        return self.storage.location[id]

    def get_text(self, id):
        return self.storage.texts[id]

    

    def translate_allele(self, defn, fmt=None):
        t = self.translator

        if fmt == "ga4gh":
            a = ga4gh.vr.models.Allele(**defn)
        elif fmt == "beacon":
            a = t.from_beacon(defn)
        elif fmt == "hgvs":
            a = t.from_hgvs(defn)
        elif fmt == "gnomad":
            a = t.from_gnomad(defn)
        elif fmt == "spdi":
            a = t.from_spdi(defn)
        else:
            raise ValueError(f"unsupported format ({fmt})")

        return a
    

    def translate_text(self, defn):
        t = ga4gh.vr.models.Text(definition=defn)
        return t


if __name__ == "__main__":
    from ga4gh.vr.dataproxy import 
