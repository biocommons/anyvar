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
from ga4gh.vrs import models as vrs_models
from ga4gh.vrs.enderef import vrs_deref, vrs_enref

from anyvar.storage import DEFAULT_STORAGE_URI, _Storage
from anyvar.storage.db import Allele, Location, SequenceReference, create_tables
from anyvar.translate.translate import _Translator
from anyvar.translate.vrs_python import VrsPythonTranslator
from anyvar.utils.types import Annotation, AnnotationKey, VrsObject

# Suppress pydantic warnings unless otherwise indicated
if os.environ.get("ANYVAR_SHOW_PYDANTIC_WARNINGS", None) is None:
    warnings.filterwarnings("ignore", module="pydantic")

_logger = logging.getLogger(__name__)


def create_storage(uri: str | None = None, table_name: str | None = None) -> _Storage:
    """Provide factory to create storage based on `uri` or the ANYVAR_STORAGE_URI
    environment value.

    The URI format is as follows:

    * PostgreSQL
    `postgresql://[username]:[password]@[domain]/[database]`

    For no database (for testing or non-persistent use cases), use an empty string.

    :param uri: storage URI
    :param table_name: table name to use for storage (if the storage supports it)
    """
    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)
    parsed_uri = urlparse(uri)
    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import PostgresObjectStore  # noqa: PLC0415

        create_tables(uri)
        storage = PostgresObjectStore(uri, table_name=table_name)
    elif parsed_uri.scheme == "":
        from anyvar.storage.no_db import NoObjectStore  # noqa: PLC0415

        storage = NoObjectStore()
    else:
        msg = f"URI scheme {parsed_uri.scheme} is not implemented"
        raise ValueError(msg)

    _logger.debug("create_storage: %s → %s}", uri, storage)
    return storage


def create_annotation_storage(
    uri: str | None = None, table_name: str | None = None
) -> _Storage:
    """Provide factory to create annotation storage based on `uri` or the
    ANYVAR_ANNOTATION_STORAGE_URI environment value.

    :param uri: storage URI
    :param table_name: table name to use for storage (if the storage supports it)
    """
    uri = uri or os.environ.get("ANYVAR_ANNOTATION_STORAGE_URI", DEFAULT_STORAGE_URI)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "postgresql":
        from anyvar.storage.postgres import (  # noqa: PLC0415
            PostgresAnnotationObjectStore,
        )

        storage = PostgresAnnotationObjectStore(uri, table_name=table_name)
    else:
        msg = f"URI scheme {parsed_uri.scheme} is not implemented"
        raise ValueError(msg)

    _logger.debug("create_annotation_storage: %s → %s}", uri, storage)
    return storage


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
            id, _ = vrs_enref(variation_object, self.object_store, True)  # noqa: A001

            # NEW Using new tables
            with self.object_store.session_factory() as session:
                al = Allele(
                    id=id,
                    location_id=variation_object.location.id,
                    state=variation_object.state.model_dump_json(exclude_none=True),
                )
                loc = Location(
                    id=variation_object.location.id,
                    start=variation_object.location.start,
                    end=variation_object.location.end,
                    sequence_reference_id=variation_object.location.sequenceReference.refgetAccession,
                )
                if isinstance(variation_object.location.start, vrs_models.Range):
                    loc.start_outer = variation_object.location.start[0]
                    loc.start_inner = variation_object.location.start[1]
                    loc.start = None
                if isinstance(variation_object.location.end, vrs_models.Range):
                    loc.end_inner = variation_object.location.end[0]
                    loc.end_outer = variation_object.location.end[1]
                    loc.end = None
                seq_ref = SequenceReference(
                    id=variation_object.location.sequenceReference.refgetAccession,
                    refseq_id=None,
                    molecule_type=variation_object.location.sequenceReference.moleculeType,
                )
                session.merge(seq_ref)
                session.merge(loc)
                session.merge(al)
                session.commit()

        except ValueError:
            return None
        return id

    def get_object(self, object_id: str, deref: bool = False) -> VrsObject:
        """Retrieve registered variation.

        :param object_id: object identifier
        :param deref: if True, dereference all IDs contained by the object
        :return: VRS object if found.
        :raises: KeyError if identifier is not found, or ValueError if deref = True and
                    the object is either a) not a Pydantic instance, or b) not a ga4gh identifiable object
        """
        v = self.object_store[object_id]
        return vrs_deref(v, self.object_store) if deref else v  # type: ignore (this will always return a VrsObject)


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
