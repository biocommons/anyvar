"""Provide PostgreSQL-based storage implementation."""

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models


class StoredObjectType(enum.StrEnum):
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
    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage."""

    @abstractmethod
    def get_objects(self, object_ids: Iterable[str]) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""

    @abstractmethod
    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""

    @abstractmethod
    def get_object_count(self, object_type: StoredObjectType) -> int:
        """Get count of objects of a specific type in storage."""

    @abstractmethod
    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
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
    ) -> None:
        """Get mappings of a specific type for a source object.

        :param source_object_id: ID of the source object
        :param mapping_type: Type of VariationMappingType
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
