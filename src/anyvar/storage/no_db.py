"""Provide minimal class for backend with no persistent storage"""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from .abc import StoredObjectType, VariationMappingType, _Storage


class NoObjectStore(_Storage):
    """Storage backend that does not persistently store any data."""

    def __init__(self) -> None:
        """Initialize DB handler."""

    def setup(self) -> None:
        """Set up the storage backend."""

    def close(self) -> None:
        """Close the storage backend."""

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.
        NOTE: This is a no-op for synchronous storage backends.
        """

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""

    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage."""

    def get_objects(
        self,
        object_type: StoredObjectType,  # noqa: ARG002
        object_ids: Iterable[str],  # noqa: ARG002
    ) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""
        return []

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""
        return []

    def get_object_count(self, object_type: StoredObjectType) -> int:  # noqa: ARG002
        """Get count of objects of a specific type in storage."""
        return 0

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

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

    def get_mappings(
        self,
        source_object_id: str,  # noqa: ARG002
        mapping_type: VariationMappingType,  # noqa: ARG002
    ) -> list[str]:
        """Return a list of ids of destination objects mapped from the source object.

        :param source_object_id: ID of the source object
        :param mapping_type: Type of VariationMappingType
        """
        return []

    def search_alleles(
        self,
        refget_accession: str,  # noqa: ARG002
        start: int,  # noqa: ARG002
        stop: int,  # noqa: ARG002
    ) -> list[vrs_models.Allele]:
        """Find all Alleles in the particular region

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of Alleles
        """
        return []
