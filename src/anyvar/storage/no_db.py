"""Stateless storage implementation (no persistence).

Use for processing-only deployments (e.g., variation translation, VCF annotation);
writes are discarded and reads always miss.
"""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.storage.base_storage import Storage
from anyvar.utils import types


class NoObjectStore(Storage):
    """Storage backend that does not persistently store any data."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize stateless storage instance."""

    def close(self) -> None:
        """(No-op) Close the storage backend."""

    def wait_for_writes(self) -> None:
        """(No-op) Wait for all background writes to complete."""

    def wipe_db(self) -> None:
        """(No-op) Wipe all data from the storage backend."""

    def add_objects(self, objects: Iterable[types.VrsObject]) -> None:
        """(No-op) Add multiple VRS objects to storage."""

    def get_objects(
        self,
        object_type: type[types.VrsObject],
        object_ids: Iterable[str],
    ) -> Iterable[types.VrsObject]:
        """(No-op) Retrieve multiple VRS objects from storage by their IDs."""
        return []

    def delete_objects(
        self, object_type: type[types.VrsObject], object_ids: Iterable[str]
    ) -> None:
        """(No-op) Delete all objects of a specific type from storage."""

    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """(No-op) Add a mapping between two objects."""

    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """(No-op) Delete a mapping between two objects."""

    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: types.VariationMappingType | None = None,
    ) -> Iterable[types.VariationMapping]:
        """(No-op) Return an iterable of mappings from the source ID"""
        return []

    def add_annotation(self, annotation: types.Annotation) -> None:
        """(No-op) Adds an annotation to the database."""

    def get_annotations(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """(No-op) Get all annotations for the specified object, optionally filtered by type."""
        return []

    def delete_annotation(self, annotation: types.Annotation) -> None:
        """(No-op) Deletes an annotation from the database"""

    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list[vrs_models.Allele]:
        """(No-op) Find all Alleles within the specified interval."""
        return []
