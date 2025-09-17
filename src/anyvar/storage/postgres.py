"""Provide PostgreSQL-based storage implementation."""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models

from anyvar.storage.db import Allele, Location, SequenceReference

from .abc import Storage, StoredObjectType


def store_allele(object_store: Storage, variation_object: vrs_models.Allele) -> None:
    """Map a VRS Allele object to AnyVar db types and store it in the database."""
    # NEW Using new tables
    with object_store.session_factory() as session:
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


class PostgresObjectStore(Storage):
    """PostgreSQL storage backend. Currently, this is our recommended storage
    approach.
    """

    def setup(self) -> None:
        """Set up the storage backend."""

    def close(self) -> None:
        """Close the storage backend."""

    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage."""

    def get_objects(self, object_ids: Iterable[str]) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""

    def get_object_count(self, object_type: StoredObjectType) -> int:
        """Get count of objects of a specific type in storage."""

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""

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
