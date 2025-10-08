"""Provide PostgreSQL-based storage implementation."""

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.utils import types as anyvar_types


class StoredObjectType(enum.StrEnum):
    """Supported VRS object types for AnyVar storage."""

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
    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage."""

    @abstractmethod
    def get_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> Iterable[vrs_models.VrsType]:
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
    def add_mapping(self, mapping: anyvar_types.VariationMapping) -> None:
        """Add a mapping between two objects.

        :param mapping: mapping object
        """

    @abstractmethod
    def delete_mapping(self, mapping: anyvar_types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        :param mapping: mapping object
        """

    @abstractmethod
    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: anyvar_types.VariationMappingType,
    ) -> Iterable[anyvar_types.VariationMapping]:
        """Return an iterable of ids of destination objects mapped from the source object.

        :param source_object_id: ID of the source object
        :param mapping_type: kind of mapping to retrieve
        :return: iterable collection of mapping descriptors
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
