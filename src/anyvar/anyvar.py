"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import importlib.util
import logging
import os
import warnings
from collections.abc import MutableMapping
from urllib.parse import urlparse

from agct import Converter, Genome

from anyvar.storage import DEFAULT_STORAGE_URI
from anyvar.storage.abc import StoredObjectType, _Storage
from anyvar.storage.db import create_tables
from anyvar.translate.translate import _Translator
from anyvar.translate.vrs_python import VrsPythonTranslator
from anyvar.utils.types import Annotation, AnnotationKey, VrsObject

# Suppress pydantic warnings unless otherwise indicated
if os.environ.get("ANYVAR_SHOW_PYDANTIC_WARNINGS", None) is None:
    warnings.filterwarnings("ignore", module="pydantic")

_logger = logging.getLogger(__name__)


def create_storage(uri: str | None = None) -> _Storage:
    """Provide factory to create storage based on `uri` or the ANYVAR_STORAGE_URI
    environment value.

    The URI format is as follows:

    * PostgreSQL
    `postgresql://[username]:[password]@[domain]/[database]`

    For no database (for testing or non-persistent use cases), use an empty string.

    :param uri: storage URI
    """
    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)
    parsed_uri = urlparse(uri)
    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore  # noqa: PLC0415

        create_tables(uri)
        storage = PostgresObjectStore(uri)
    elif parsed_uri.scheme == "":
        from anyvar.storage.no_db import NoObjectStore  # noqa: PLC0415

        storage = NoObjectStore()
    else:
        msg = f"URI scheme {parsed_uri.scheme} is not implemented"
        raise ValueError(msg)

    _logger.debug("create_storage: %s → %s}", uri, storage)
    return storage


def create_annotation_storage(
    uri: str | None = None,
    table_name: str | None = None,  # noqa: ARG001
) -> _Storage:
    """Provide factory to create annotation storage based on `uri` or the
    ANYVAR_ANNOTATION_STORAGE_URI environment value.

    :param uri: storage URI
    :param table_name: table name to use for storage (if the storage supports it)
    """
    uri = uri or os.environ.get("ANYVAR_ANNOTATION_STORAGE_URI", DEFAULT_STORAGE_URI)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "postgresql":
        raise NotImplementedError("PostgresAnnotationObjectStore has been removed")
    msg = f"URI scheme {parsed_uri.scheme} is not implemented"
    raise ValueError(msg)

    _logger.debug("create_annotation_storage: %s → NotImplementedError", uri)
    # This should never be reached since all paths above raise exceptions
    raise NotImplementedError("No annotation storage implementation available")


def create_translator() -> _Translator:
    """Create variation translator middleware.

    Try to build the VRS-Python wrapper class with default args. In the future, could
    provide assistance constructing other kinds of translators.

    :return: instantiated Translator instance
    """
    return VrsPythonTranslator()


def has_queueing_enabled() -> bool:
    """Determine whether or not asynchronous task queueing is enabled"""
    return (
        importlib.util.find_spec("aiofiles") is not None
        and importlib.util.find_spec("celery") is not None
        and os.environ.get("CELERY_BROKER_URL", "") != ""
        and os.environ.get("ANYVAR_VCF_ASYNC_WORK_DIR", "") != ""
    )


class AnyVar:
    """Define core AnyVar class."""

    def __init__(
        self,
        /,
        translator: _Translator,
        object_store: _Storage,
    ) -> None:
        """Initialize anyvar instance. It's easiest to use factory methods to create
        translator and object_store instances but manual construction works too.

        :param translator: Translator instance
        :param object_store: Object storage instance
        :param annotation_store: (Optional) Annotation storage instance
        """
        if not isinstance(object_store, MutableMapping):
            _logger.warning(
                "AnyVar(object_store=) should be a mutable mapping; you're on your own"
            )

        self.object_store = object_store
        self.translator = translator
        self.liftover_converters = {
            "GRCh37_to_GRCh38": Converter(Genome.HG19, Genome.HG38),
            "GRCh38_to_GRCh37": Converter(Genome.HG38, Genome.HG19),
        }

    def put_object(self, variation_object: VrsObject) -> str | None:
        """Attempt to register variation.

        :param variation_object: complete VRS object
        :return: Object digest if successful, None otherwise
        """
        try:
            self.object_store.add_objects([variation_object])
        except Exception as e:
            _logger.exception("Failed to add object: %s", variation_object)
            raise e  # noqa: TRY201
        return variation_object.id

    def get_object(
        self, object_id: str, object_type: StoredObjectType | None = None
    ) -> VrsObject:
        """Retrieve registered variation.

        :param object_id: object identifier
        :param object_type: specific object type to search (optional - if not provided, searches all types)
        :return: VRS object if found.
        :raises: KeyError if identifier is not found
        """
        if object_type is not None:
            # Search specific object type
            found = self.object_store.get_objects(
                object_type=object_type, object_ids=[object_id]
            )
            if not found:
                raise KeyError(f"Object {object_id} not found")
            if len(found) > 1:
                raise ValueError(f"Multiple objects found for ID {object_id}")
            return found[0]

        # Search all object types
        return self._get_object_polymorphic(object_id)

    def _get_object_polymorphic(self, object_id: str) -> VrsObject:
        """Search all object types for the given object ID.

        :param object_id: VRS object identifier
        :return: VRS object if found
        :raises: KeyError if object is not found in any table
        """
        # Try each object type. Primary key lookups should be fast.
        object_types_to_try = [
            StoredObjectType.ALLELE,
            StoredObjectType.SEQUENCE_LOCATION,
            StoredObjectType.SEQUENCE_REFERENCE,
        ]
        for object_type in object_types_to_try:
            try:
                found = list(
                    self.object_store.get_objects(
                        object_type=object_type, object_ids=[object_id]
                    )
                )
                if found:
                    return found[0]
            except (KeyError, ValueError):
                # Continue to next object type
                continue
        raise KeyError(f"Object {object_id} not found in any table")


class AnyAnnotation:
    """Class for interacting with annotations"""

    def __init__(self, annotation_store: _Storage) -> None:
        """Initialize AnyAnnotation instance.

        :param annotation_store: Annotation storage instance
        """
        self.annotation_store = annotation_store

    def get_annotation(self, object_id: str, annotation_type: str) -> list[Annotation]:
        """Retrieve annotations for object.

        :param object_id: object identifier
        :param annotation_type: type of annotation
        :return: list of annotations
        """
        return self.annotation_store.get(
            AnnotationKey(object_id=object_id, annotation_type=annotation_type), []
        )

    def put_annotation(
        self, object_id: str, annotation_type: str, annotation: dict
    ) -> None:
        """Attach annotation to object.

        :param object_id: object identifier
        :param annotation_type: type of annotation
        :param annotation: annotation dictionary
        """
        self.annotation_store.push(
            Annotation(
                object_id=object_id,
                annotation_type=annotation_type,
                annotation=annotation,
            )
        )
