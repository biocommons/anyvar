"""full-service interface to converting, validating, and registering
biological sequence variation

"""

from collections.abc import MutableMapping
import logging

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, vrs_deref, vrs_enref
from ga4gh.vrs.extras.translator import Translator


_logger = logging.getLogger(__name__)


class AnyVar:
    def __init__(self, /, translator: Translator, object_store: MutableMapping):
        if not isinstance(object_store, MutableMapping):
            _logger.warning("AnyVar(object_store=) should be a mutable mapping; you're on your own")

        self.object_store = object_store
        self.translator = translator

    def put_object(self, vo):
        v = vrs_enref(vo, self.object_store)
        _id = ga4gh_identify(v)
        return _id

    def get_object(self, id, deref=False):
        v = self.object_store[id]
        return vrs_deref(v, self.object_store) if deref else v


    def create_text(self, defn):
        vo = models.Text(definition=defn)
        vo._id = ga4gh_identify(vo)
        return vo
