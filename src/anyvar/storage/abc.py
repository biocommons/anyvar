"""Provide PostgreSQL-based storage implementation."""

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.utils.types import Annotation


class StoredVrsObjectType(enum.StrEnum):
    """Supported VRS object types for AnyVar storage."""

    ALLELE = "Allele"
    LOCATION = "Location"
    COPY_NUMBER_COUNT = "CopyNumberCount"
    COPY_NUMBER_CHANGE = "CopyNumberChange"
    SEQUENCE_LOCATION = "SequenceLocation"
    SEQUENCE_REFERENCE = "SequenceReference"


class VariationMappingType(enum.StrEnum):
    """Supported mapping types between VRS Variations."""

    LIFTOVER = "liftover"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"


class _Storage(ABC):
    """Abstract base class for interacting with storage backends."""

    @abstractmethod
    def setup(self) -> None:
        """Set up the storage backend."""

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
    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage."""

    @abstractmethod
    def get_objects(
        self, object_type: StoredVrsObjectType, object_ids: Iterable[str]
    ) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""

    @abstractmethod
    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""

    @abstractmethod
    def get_object_count(self, object_type: StoredVrsObjectType) -> int:
        """Get count of objects of a specific type in storage."""

    @abstractmethod
    def delete_objects(
        self, object_type: StoredVrsObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

    @abstractmethod
    def add_mapping(
        self,
        source_object_id: str,
        destination_object_id: str,
        mapping_type: VariationMappingType,
    ) -> None:
        """Add a mapping between two objects.

        :param source_object_id: ID of the source object
        :param destination_object_id: ID of the destination object
        :param mapping_type: Type of VariationMappingType
        """

    @abstractmethod
    def delete_mapping(
        self,
        source_object_id: str,
        destination_object_id: str,
        mapping_type: VariationMappingType,
    ) -> None:
        """Delete a mapping between two objects.

        :param source_object_id: ID of the source object
        :param destination_object_id: ID of the destination object
        :param mapping_type: Type of VariationMappingType
        """

    @abstractmethod
    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: VariationMappingType,
    ) -> list[str]:
        """Return a list of ids of destination objects mapped from the source object.

        :param source_object_id: ID of the source object
        :param mapping_type: Type of VariationMappingType
        """

    @abstractmethod
    def add_annotation(self, annotation: Annotation) -> None:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        """

    @abstractmethod
    def get_annotation_by_object_and_type(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[Annotation]:
        """Retrieves all annotations for the given object, optionally filtered to only annotations of the specified type from the database

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve
        :return: A list of annotations
        """

    @abstractmethod
    def delete_annotation(self, annotation_id: int) -> None:
        """Deletes an annotation from the database

        :param annotation_id: The ID of the annotation to delete
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


# Alias for backward compatibility and cleaner naming
Storage = _Storage
