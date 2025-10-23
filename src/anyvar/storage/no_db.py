"""Stateless storage implementation (no persistence).

Use for processing-only deployments (e.g., variation translation, VCF annotation);
writes are discarded and reads always miss.
"""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.storage.base_storage import Storage, StoredObjectType
from anyvar.utils import types


class NoObjectStore(Storage):
    """Storage backend that does not persistently store any data."""

    def __init__(self, db_url: str | None = None) -> None:
        """Initialize storage instance."""

    def close(self) -> None:
        """Close the storage backend."""

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete."""

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""

    def add_objects(self, objects: Iterable[types.VrsObject]) -> None:
        """Add multiple VRS objects to storage."""

    def get_objects(
        self,
        object_type: StoredObjectType,
        object_ids: Iterable[str],
    ) -> Iterable[types.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs."""
        return []

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""
        return []

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        :param mapping: mapping object
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB
        """

    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        * If no such mapping exists in the DB, does nothing.
        * Deletes do not cascade.

        :param mapping: mapping object
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

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
        return []

    def add_annotation(self, annotation: types.Annotation) -> None:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :raise MissingVariationReferenceError: if no object corresponding to the annotation's
            object ID is present in DB
        """

    def get_annotations(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """
        return []

    def delete_annotation(self, annotation: types.Annotation) -> None:
        """Deletes an annotation from the database

        * If no such annotation exists, do nothing.
        * Deletes do not cascade.

        :param annotation: The annotation object to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """

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
        return []
