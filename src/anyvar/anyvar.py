"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import logging
import os
from collections.abc import MutableMapping
from typing import Optional
from urllib.parse import urlparse

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import vrs_deref, vrs_enref

from anyvar.storage import DEFAULT_STORAGE_URI, _Storage
from anyvar.translate.translate import DEFAULT_TRANSLATE_URI, TranslatorSetupException, _Translator
from anyvar.utils.types import VrsPythonObject

_logger = logging.getLogger(__name__)


def create_storage(uri: Optional[str] = None) -> _Storage:
    """factory to create storage based on `uri` or the ANYVAR_STORAGE_URI environment
    value.

    The URI format is as follows:

    * PostgreSQL
    `postgresql://[username]:[password]@[domain]/[database]`
    """
    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore

        storage = PostgresObjectStore(uri)  # type: ignore

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
        uri = os.environ.get("ANYVAR_VARIATION_NORMALIZER_URI", DEFAULT_TRANSLATE_URI)
        if not uri:
            raise TranslatorSetupException("No Translator URI provided.")

    from anyvar.translate.variation_normalizer import VariationNormalizerRestTranslator

    return VariationNormalizerRestTranslator(uri)


class AnyVar:
    def __init__(self, /, translator: _Translator, object_store: _Storage):
        """Initialize anyvar instance. It's easiest to use factory methods to create
        translator and object_store instances but manual construction works too.

        :param translator: Translator instance
        :param object_store: Object storage instance
        """
        if not isinstance(object_store, MutableMapping):
            _logger.warning("AnyVar(object_store=) should be a mutable mapping; you're on your own")

        self.object_store = object_store
        self.translator = translator

    def put_object(self, variation_object: VrsPythonObject) -> Optional[str]:
        """Attempt to register variation.

        :param variation_object: complete VRS object
        :return: Object digest if successful, None otherwise
        """
        try:
            v = vrs_enref(variation_object, self.object_store)
        except ValueError:
            return None
        _id = ga4gh_identify(v)
        return _id

    def get_object(self, object_id: str, deref: bool = False) -> Optional[VrsPythonObject]:
        """Retrieve registered variation.

        :param object_id: object identifier
        :param deref: if True, dereference all IDs contained by the object
        """
        v = self.object_store[object_id]
        return vrs_deref(v, self.object_store) if deref else v
