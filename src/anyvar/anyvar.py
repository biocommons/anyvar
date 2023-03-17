"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import logging
import os
from collections.abc import MutableMapping
from typing import Optional
from urllib.parse import urlparse

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, vrs_deref, vrs_enref

from anyvar.storage import DEFAULT_STORAGE_URI, _Storage
from anyvar.translate.translate import TranslatorSetupException, _Translator

_logger = logging.getLogger(__name__)


def create_storage(uri=None):
    """factory to create storage based on `uri`, the ANYVAR_STORAGE_URI
    environment value, or in-memory storage.

    The URI format is one of the following:

    * in-memory dictionary:
    `memory:`
    Remaining URI elements ignored, if provided

    * Python shelf (dbm) persistence

    `file:///full/path/to/filename.db`
    `path/to/filename`

    The `file` scheme permits only full paths.  When scheme is not
    provided, the path may be absolute or relative.

    * Redis URI
    `redis://[[username]:[password]]@localhost:6379/0`
    `unix://[[username]:[password]]@/path/to/socket.sock?db=0`

    The URIs are passed as-is to `redis.Redis.from_url()`

    """

    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "memory":
        _logger.warning(
            "Using memory storage; stored data will be discarded when process exits"
        )
        from anyvar.storage.memory import InMemoryStore
        storage = InMemoryStore()
        # storage = dict()

    elif parsed_uri.scheme in ("", "file"):
        from anyvar.storage.shelf import ShelfStorage

        storage = ShelfStorage(parsed_uri.path)

    elif parsed_uri.scheme == "redis" or parsed_uri.scheme == "unix":
        import redis

        from anyvar.storage.redis import RedisObjectStore
        storage = RedisObjectStore(redis.Redis.from_url(uri))

    elif parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore

        storage = PostgresObjectStore(uri)

    else:
        raise ValueError(f"URI scheme {parsed_uri.scheme} is not implemented")

    _logger.debug(f"create_storage: {uri} → {storage}")
    return storage


def create_translator(uri: Optional[str] = None) -> _Translator:
    """Create variation translator middleware.

    Currently accepts REST interface only -- we should at least enable a local
    proxy instance in the future.

    :param uri: location listening for requests
    :return: instantiated Translator instance
    """
    if not uri:
        uri = os.environ.get("ANYVAR_VARIATION_NORMALIZER_URI")
        if not uri:
            raise TranslatorSetupException("No Translator URI provided.")

    from anyvar.translate.variation_normalizer import \
        VariationNormalizerRestTranslator

    return VariationNormalizerRestTranslator(uri)


class AnyVar:
    def __init__(self, /, translator: _Translator, object_store: _Storage):
        if not isinstance(object_store, MutableMapping):
            _logger.warning(
                "AnyVar(object_store=) should be a mutable mapping; you're on your own"
            )

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
