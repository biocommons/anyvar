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
        """Add multiple VRS objects to storage."""

    @abstractmethod
    def get_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> Iterable[types.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs."""

    @abstractmethod
    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""

    @abstractmethod
    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

    @abstractmethod
    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """Add a mapping between two objects.

        :param mapping: mapping object
        """

    @abstractmethod
    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        :param mapping: mapping object
        """

    @abstractmethod
    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: types.VariationMappingType,
    ) -> Iterable[types.VariationMapping]:
        """Return a list of variation mappings.

        :param source_object_id: ID of the source object
        :param mapping_type: kind of mapping to retrieve
        :return: iterable collection of mapping objects
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
    def add_annotation(self, annotation: types.Annotation) -> int:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
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
    def delete_annotation(self, annotation_id: int) -> None:
        """Deletes an annotation from the database

        :param annotation_id: The ID of the annotation to delete
        """
