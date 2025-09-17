"""Provide PostgreSQL-based storage implementation."""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import create_engine, func
from sqlalchemy.orm import joinedload, sessionmaker

from anyvar.storage.db import Allele, Location, SequenceReference, create_tables

from .abc import Storage, StoredObjectType
from .mapper_registry import mapper_registry


class PostgresObjectStore(Storage):
    """PostgreSQL storage backend using dedicated ORM tables.

    This implementation uses the new Allele, Location, and SequenceReference tables
    with object mapping to convert between VRS models and database entities.
    """

    def __init__(self, db_url: str) -> None:
        """Initialize PostgreSQL storage.

        :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
        """
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.session_factory = sessionmaker(bind=self.engine)

    def setup(self) -> None:
        """Set up the storage backend by creating tables."""
        create_tables(self.db_url)

    def close(self) -> None:
        """Close the storage backend."""
        # TODO unclear if engine.dispose is desirable.
        # It does not wait for active connections.
        # https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine.dispose
        # self.engine.dispose()

    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage using mappers."""
        with self.session_factory() as session, session.begin():
            for vrs_object in objects:
                # Convert to DB entity and merge - mappers handle dependencies
                db_entity = mapper_registry.to_db_entity(vrs_object)
                session.merge(db_entity)

    def get_objects(self, object_ids: Iterable[str]) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""
        object_ids_list = list(object_ids)
        results = []

        with self.session_factory() as session:
            # Get alleles with eager loading
            db_alleles = (
                session.query(Allele)
                .options(
                    joinedload(Allele.location).joinedload(Location.sequence_reference)
                )
                .filter(Allele.id.in_(object_ids_list))
                .all()
            )

            for db_allele in db_alleles:
                vrs_allele = mapper_registry.to_vrs_model(db_allele)
                results.append(vrs_allele)

        return results

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""
        with self.session_factory() as session:
            # Get all allele IDs for now
            allele_ids = session.query(Allele.id).all()
            return [allele_id[0] for allele_id in allele_ids]

    def get_object_count(self, object_type: StoredObjectType) -> int:
        """Get count of objects of a specific type in storage."""
        with self.session_factory() as session:
            if object_type == StoredObjectType.ALLELE:
                return session.query(func.count(Allele.id)).scalar()
            if object_type == StoredObjectType.SEQUENCE_LOCATION:
                return session.query(func.count(Location.id)).scalar()
            if object_type == StoredObjectType.SEQUENCE_REFERENCE:
                return session.query(func.count(SequenceReference.id)).scalar()
            return 0

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""
        object_ids_list = list(object_ids)

        with self.session_factory() as session, session.begin():
            if object_type == StoredObjectType.ALLELE:
                session.query(Allele).filter(Allele.id.in_(object_ids_list)).delete()
            elif object_type == StoredObjectType.SEQUENCE_LOCATION:
                session.query(Location).filter(
                    Location.id.in_(object_ids_list)
                ).delete()
            elif object_type == StoredObjectType.SEQUENCE_REFERENCE:
                session.query(SequenceReference).filter(
                    SequenceReference.id.in_(object_ids_list)
                ).delete()

    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list[vrs_models.Allele]:
        """Find all Alleles in the particular region.

        :param refget_accession: refget accession (SQ. identifier)
        :param start: Start genomic region to query
        :param stop: Stop genomic region to query

        :return: a list of Alleles
        """
        with self.session_factory() as session:
            # Query alleles with overlapping locations
            db_alleles = (
                session.query(Allele)
                .options(
                    joinedload(Allele.location).joinedload(Location.sequence_reference)
                )
                .join(Location)
                .join(SequenceReference)
                .filter(
                    SequenceReference.refseq_id == refget_accession,
                    Location.start < stop,
                    Location.end > start,
                )
                .all()
            )

            return [mapper_registry.to_vrs_model(db_allele) for db_allele in db_alleles]

    def get_allele(self, allele_id: str) -> vrs_models.Allele | None:
        """Retrieve and reconstitute Allele from database."""
        with self.session_factory() as session:
            db_allele = (
                session.query(Allele)
                .options(
                    joinedload(Allele.location).joinedload(Location.sequence_reference)
                )
                .filter(Allele.id == allele_id)
                .first()
            )

            if db_allele is None:
                return None

            return mapper_registry.to_vrs_model(db_allele)

    def get_alleles(self, allele_ids: list[str]) -> list[vrs_models.Allele]:
        """Retrieve and reconstitute multiple Alleles from database."""
        with self.session_factory() as session:
            db_alleles = (
                session.query(Allele)
                .options(
                    joinedload(Allele.location).joinedload(Location.sequence_reference)
                )
                .filter(Allele.id.in_(allele_ids))
                .all()
            )

            return [mapper_registry.to_vrs_model(db_allele) for db_allele in db_alleles]

    def add_allele(self, vrs_allele: vrs_models.Allele) -> None:
        """Store VRS Allele in database."""
        with self.session_factory() as session, session.begin():
            # Convert VRS models to DB entities using mappers
            db_seq_ref = mapper_registry.to_db_entity(
                vrs_allele.location.sequenceReference
            )
            db_location = mapper_registry.to_db_entity(vrs_allele.location)
            db_allele = mapper_registry.to_db_entity(vrs_allele)

            # Use merge for upsert behavior (handles existing records)
            session.merge(db_seq_ref)
            session.merge(db_location)
            session.merge(db_allele)
