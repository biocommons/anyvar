"""manages a GA4GH.VR bundle and provides helpful a helpful interface to
it"""


import logging

import ga4gh.vr
from ga4gh.vr.extras.translator import Translator


_logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, storage):
        self.translator = Translator()
        self.storage = storage


    def add_allele(self, allele):
        allele.id = ga4gh.vr.computed_id(allele)
        self.storage.alleles[allele.id] = allele
        self.add_location(allele.location)
        _logger.warn(f"Added Allele {allele.id}")
        return allele

    def add_location(self, location):
        location.id = ga4gh.vr.computed_id(location)
        self.storage.locations[location.id] = location
        return location

    def add_text(self, text):
        text.id = ga4gh.vr.computed_id(text)
        self.storage.texts[text.id] = text
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
