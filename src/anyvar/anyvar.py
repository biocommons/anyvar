"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import logging
import os
from collections.abc import MutableMapping
from urllib.parse import urlparse

from ga4gh.vrs import vrs_deref, vrs_enref

from anyvar.storage import DEFAULT_STORAGE_URI, _Storage
from anyvar.translate.translate import _Translator
from anyvar.translate.vrs_python import VrsPythonTranslator
from anyvar.utils.types import VrsObject

_logger = logging.getLogger(__name__)


def create_storage(uri: str | None = None) -> _Storage:
    """Provide factory to create storage based on `uri` or the ANYVAR_STORAGE_URI
    environment value.

    The URI format is as follows:

    * PostgreSQL
    `postgresql://[username]:[password]@[domain]/[database]`
    * Snowflake
    `snowflake://[user]:@[account]/[database]/[schema]?[param=value]&[param=value]...`
    """
    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore

        storage = PostgresObjectStore(uri)
    elif parsed_uri.scheme == "snowflake":
        from anyvar.storage.snowflake import SnowflakeObjectStore

        storage = SnowflakeObjectStore(uri)
    else:
        msg = f"URI scheme {parsed_uri.scheme} is not implemented"
        raise ValueError(msg)

    _logger.debug("create_storage: %s → %s}", uri, storage)
    return storage


def create_translator() -> _Translator:
    """Create variation translator middleware.

    Try to build the VRS-Python wrapper class with default args. In the future, could
    provide assistance constructing other kinds of translators.

    :return: instantiated Translator instance
    """
    return VrsPythonTranslator()


class AnyVar:
    """Define core AnyVar class."""

    def __init__(self, /, translator: _Translator, object_store: _Storage) -> None:
        """Initialize anyvar instance. It's easiest to use factory methods to create
        translator and object_store instances but manual construction works too.

        :param translator: Translator instance
        :param object_store: Object storage instance
        """
        if not isinstance(object_store, MutableMapping):
            _logger.warning(
                "AnyVar(object_store=) should be a mutable mapping; you're on your own"
            )

        self.object_store = object_store
        self.translator = translator

    def put_object(self, variation_object: VrsObject) -> str | None:
        """Attempt to register variation.

        :param variation_object: complete VRS object
        :return: Object digest if successful, None otherwise
        """
        try:
            id, _ = vrs_enref(variation_object, self.object_store, True)  # noqa: A001
        except ValueError:
            return None
        return id

    def get_object(self, object_id: str, deref: bool = False) -> VrsObject | None:
        """Retrieve registered variation.

        :param object_id: object identifier
        :param deref: if True, dereference all IDs contained by the object
        """
        v = self.object_store[object_id]
        return vrs_deref(v, self.object_store) if deref else v
