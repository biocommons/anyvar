"""Provide PostgreSQL-based storage implementation."""

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.utils import types


class StoredObjectType(enum.StrEnum):
    """Supported object types for AnyVar storage."""

    ALLELE = "Allele"
    LOCATION = "Location"
    COPY_NUMBER_COUNT = "CopyNumberCount"
    COPY_NUMBER_CHANGE = "CopyNumberChange"
    SEQUENCE_LOCATION = "SequenceLocation"
    SEQUENCE_REFERENCE = "SequenceReference"


class DataIntegrityError(Exception):
    """Raise for attempts to delete objects depended upon by other objects"""


class MissingVariationReferenceError(Exception):
    """Raise for attempts to insert an annotation or mapping that references a non-existent variation"""


class IncompleteVrsObjectError(Exception):
    """Raise if provided VRS object is missing fully-materialized properties required for storage"""


class Storage(ABC):
    """Abstract base class for interacting with storage backends."""

    @abstractmethod
    def __init__(self, db_url: str | None = None) -> None:
        """Initialize the storage backend.

        :param db_url: Database connection URL
        """

    @abstractmethod
    def close(self) -> None:
        """Close the storage backend."""

    @abstractmethod
    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.

        NOTE: This is a no-op for synchronous storage backends.
        """

    @abstractmethod
    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""

    @abstractmethod
    def add_objects(self, objects: Iterable[types.VrsObject]) -> None:
        """Add multiple VRS objects to storage.

        If an object ID conflicts with an existing object, skip it.

        This method assumes that for VRS objects (e.g. `Allele`, `SequenceLocation`,
        `SequenceReference`) the `.id` property is present and uses the correct
        GA4GH identifier for that object. It also assumes that contained objects are
        similarly properly identified and materialized in full, not just as an IRI reference.

        :param objects: VRS objects to add to storage
        :raise IncompleteVrsObjectError: if object is missing required properties or if
            required properties aren't fully dereferenced
        """

    @abstractmethod
    def get_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> Iterable[types.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs.

        If no object matches a given ID, that ID is skipped

        :param object_type: type of object to get
        :param object_ids: IDs of objects to fetch
        :return: iterable collection of VRS objects matching given IDs
        """

    @abstractmethod
    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage.

        :return: all stored VRS object IDs
        """

    @abstractmethod
    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage.

        * If no object matching a given ID is found, it's ignored.
        * Deletes do not cascade.

        :param object_type: type of objects to delete
        :param object_ids: IDs of objects to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    @abstractmethod
    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        :param mapping: mapping object
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB
        """

    @abstractmethod
    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        * If no such mapping exists in the DB, does nothing.
        * Deletes do not cascade.

        :param mapping: mapping object
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

    @abstractmethod
    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: types.VariationMappingType | None,
    ) -> Iterable[types.VariationMapping]:
        """Return an iterable of mappings from the source ID

        Optionally provide a type to filter results.

        :param source_object_id: ID of the source object
        :param mapping_type: The type of mapping to retrieve (defaults to `None` to
            retrieve all mappings for the source ID)
        :return: iterable collection of mapping descriptors (empty if no matching mappings exist)
        """

    @abstractmethod
    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list[vrs_models.Allele]:
        """Find all Alleles in the particular region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query
        :return: a list of Alleles
        """

    @abstractmethod
    def add_annotation(self, annotation: types.Annotation) -> None:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB
        """

    @abstractmethod
    def get_annotations_by_object_and_type(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """

    @abstractmethod
    def delete_annotation(self, annotation: types.Annotation) -> None:
        """Deletes an annotation from the database

        * If no such annotation exists, do nothing.
        * Deletes do not cascade.

        :param annotation: The annotation object to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """
