"""Provide minimal class for backend with no persistent storage"""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.storage.base_storage import Storage, StoredObjectType
from anyvar.utils import types as anyvar_types


class NoObjectStore(Storage):
    """Storage backend that does not persistently store any data."""

    def __init__(self, db_url: str | None = None) -> None:
        """Initialize DB handler."""

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

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

    def add_mapping(self, mapping: anyvar_types.VariationMapping) -> None:
        """Add a mapping between two objects.

        :param mapping: mapping object
        """

    def delete_mapping(self, mapping: anyvar_types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        :param mapping: mapping object
        """

    def get_mappings(
        self,
        source_object_id: str,  # noqa: ARG002
        mapping_type: anyvar_types.VariationMappingType,  # noqa: ARG002
    ) -> Iterable[str]:
        """Return an iterable of ids of destination objects mapped from the source object.

        :param source_object_id: ID of the source object
        :param mapping_type: kind of mapping to retrieve
        :return: iterable collection of mapping descriptors
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

    def add_annotation(self, annotation: anyvar_types.Annotation) -> int:  # noqa: ARG002
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
        """
        raise TypeError("Unsupported operations for this storage type")

    def get_annotations_by_object_and_type(
        self,
        object_id: str,  # noqa: ARG002
        annotation_type: str | None = None,  # noqa: ARG002
    ) -> list[anyvar_types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """
        raise TypeError("Unsupported operations for this storage type")

    def delete_annotation(self, annotation_id: int) -> None:  # noqa: ARG002
        """Deletes an annotation from the database

        :param annotation_id: The ID of the annotation to delete
        """
        raise TypeError("Unsupported operations for this storage type")
