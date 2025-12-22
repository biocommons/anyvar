"""full-service interface to converting, validating, and registering
biological sequence variation

"""

import datetime
import importlib.util
import logging
import os
import warnings
from collections.abc import Iterable
from urllib.parse import urlparse

from ga4gh.vrs import models as vrs_models

from anyvar.storage import DEFAULT_STORAGE_URI
from anyvar.storage.base_storage import Storage
from anyvar.translate.translate import Translator
from anyvar.translate.vrs_python import VrsPythonTranslator
from anyvar.utils import types
from anyvar.utils.types import AnnotationType, VrsObject

# Suppress pydantic warnings unless otherwise indicated
if os.environ.get("ANYVAR_SHOW_PYDANTIC_WARNINGS", None) is None:
    warnings.filterwarnings("ignore", module="pydantic")

_logger = logging.getLogger(__name__)


def create_storage(uri: str | None = None) -> Storage:
    """Provide factory to create storage based on `uri` or the ANYVAR_STORAGE_URI
    environment value.

    The URI format is as follows:
        PostgreSQL: `postgresql://[username]:[password]@[domain]/[database]`
        Snowflake: `snowflake://sf_username:@sf_account_identifier/sf_db_name/sf_schema_name?password=sf_password`

    For no database (for testing or non-persistent use cases), use an empty string.

    :param uri: storage URI
    """
    if uri is None:
        uri = os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)
    parsed_uri = urlparse(uri)
    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore  # noqa: PLC0415

        storage = PostgresObjectStore(uri)
    elif parsed_uri.scheme == "snowflake":
        from anyvar.storage.snowflake import SnowflakeObjectStore  # noqa: PLC0415

        storage = SnowflakeObjectStore(uri)
    elif parsed_uri.scheme == "":
        from anyvar.storage.no_db import NoObjectStore  # noqa: PLC0415

        storage = NoObjectStore()
    else:
        msg = f"URI scheme {parsed_uri.scheme} is not implemented"
        raise ValueError(msg)

    _logger.debug("create_storage: %s → %s}", uri, storage)
    return storage


def create_translator() -> Translator:
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


class ObjectNotFoundError(Exception):
    """Raised when a related object is requested for a primary entity that does not exist."""


class AnyVar:
    """Define core AnyVar class."""

    def __init__(
        self,
        /,
        translator: Translator,
        object_store: Storage,
    ) -> None:
        """Initialize anyvar instance. It's easiest to use factory methods to create
        translator and object_store instances but manual construction works too.

        :param translator: Translator instance
        :param object_store: Object storage instance
        """
        self.object_store = object_store
        self.translator = translator

    def put_objects(self, variation_objects: list[VrsObject]) -> None:
        """Attempt to register variation objects

        The provided list may contain any supported variation object -- i.e. not just
        Alleles or molecular variations -- and is not required to contain only one
        kind of object.

        :param variation_objects: list of complete variation objects (i.e. VRS-Python models)
        """
        try:
            self.object_store.add_objects(variation_objects)
        except Exception as e:
            _logger.exception("Failed to add object: %s", variation_objects)
            raise e  # noqa: TRY201

    def get_object(
        self, object_id: str, object_type: type[types.VrsObject] | None = None
    ) -> VrsObject:
        """Retrieve registered VRS Object.

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
            vrs_models.Allele,
            vrs_models.SequenceLocation,
            vrs_models.SequenceReference,
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

    def put_annotation(self, annotation: types.Annotation) -> int | None:
        """Attempt to store an annotation.

        :param annotation: an Annotation object
        :return: annotation ID if successful, None otherwise
        """
        annotation_id: int | None = None
        try:
            annotation_id = self.object_store.add_annotation(annotation)
        except Exception as e:
            _logger.exception("Failed to add object: %s", annotation)
            raise e  # noqa: TRY201
        return annotation_id

    def get_object_annotations(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of Annotations
        :raise ObjectNotFoundError: if ``object_id`` can't be found in DB
        """
        try:
            annotations = self.object_store.get_annotations(object_id, annotation_type)
        except Exception as e:
            _logger.exception(
                "Failed to retrieve annotations for object: %s", object_id
            )
            raise e  # noqa: TRY201
        if not annotations:
            try:
                _ = self.get_object(object_id)
            except KeyError as e:
                raise ObjectNotFoundError(object_id) from e
        return annotations

    def create_timestamp_annotation_if_missing(self, object_id: str) -> int | None:
        """Store a 'creation_timestamp' annotation if missing for an object

        :param object_id: The ID of the object to create a timestamp annotation for
        :return: ID of newly created annotation. If timestamp annotation exists, will
            return None.
        """
        timestamp_annotations: list[types.Annotation] = self.get_object_annotations(
            object_id, AnnotationType.CREATION_TIMESTAMP.value
        )
        if not timestamp_annotations:
            return self.put_annotation(
                types.Annotation(
                    object_id=object_id,
                    annotation_type=AnnotationType.CREATION_TIMESTAMP.value,
                    annotation_value=datetime.datetime.now(tz=datetime.UTC).isoformat(),
                )
            )
        return None

    def put_mapping(self, mapping: types.VariationMapping) -> None:
        """Attempt to store a mapping between two objects

        :param mapping: a Mapping object
        """
        try:
            return self.object_store.add_mapping(mapping)
        except Exception:
            _logger.exception("Failed to add mapping: %s", mapping)
            raise

    def get_object_mappings(
        self, source_object_id: str, mapping_type: types.VariationMappingType
    ) -> Iterable[types.VariationMapping]:
        """Get all variation mappings given source object ID and mapping type

        :param source_object_id: ID of the source object
        :param mapping_type: kind of mapping to retrieve
        :return: iterable collection of mapping objects
        :raise ObjectNotFoundError: if ``source_object_id`` can't be found in DB
        """
        try:
            mappings = self.object_store.get_mappings(source_object_id, mapping_type)
        except Exception:
            _logger.exception(
                "Failed to retrieve mappings for source_object_id: %s and mapping_type: %s",
                source_object_id,
                mapping_type,
            )
            raise
        if not mappings:
            try:
                _ = self.get_object(source_object_id)
            except KeyError as e:
                raise ObjectNotFoundError(source_object_id) from e
        return mappings
