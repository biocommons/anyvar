"""Provide PostgreSQL-based storage implementation."""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload, sessionmaker

from anyvar.storage.db import (
    Allele,
    Annotation,
    Location,
    SequenceReference,
    VrsObject,
    create_tables,
)

from .abc import Storage, StoredObjectType, VariationMappingType
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

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.
        NOTE: This is a no-op for synchronous storage backends.
        """

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""
        with self.session_factory() as session, session.begin():
            # Delete all data from tables in dependency order
            session.query(Allele).delete()
            session.query(Location).delete()
            session.query(SequenceReference).delete()

            # Delete other tables
            session.query(VrsObject).delete()
            session.query(Annotation).delete()

    # TODO also store vrs_objects table in addition to
    # the tables per type.
    def add_objects(self, objects: Iterable[vrs_models.VrsType]) -> None:
        """Add multiple VRS objects to storage using bulk inserts."""
        objects_list = list(objects)
        if not objects_list:
            return

        # Collect unique entities by ID to avoid duplicates
        sequence_references = {}
        locations = {}
        alleles = {}

        # Process all objects and extract their components
        for vrs_object in objects_list:
            db_entity = mapper_registry.to_db_entity(vrs_object)

            if isinstance(db_entity, Allele):
                alleles[db_entity.id] = db_entity
                # Also collect the nested location and sequence reference
                if db_entity.location:
                    locations[db_entity.location.id] = db_entity.location
                    if db_entity.location.sequence_reference:
                        sequence_references[
                            db_entity.location.sequence_reference.id
                        ] = db_entity.location.sequence_reference
            elif isinstance(db_entity, Location):
                locations[db_entity.id] = db_entity
                if db_entity.sequence_reference:
                    sequence_references[db_entity.sequence_reference.id] = (
                        db_entity.sequence_reference
                    )
            elif isinstance(db_entity, SequenceReference):
                sequence_references[db_entity.id] = db_entity
            else:
                raise ValueError(f"Unsupported object type: {type(db_entity)}")  # noqa: TRY004

        with self.session_factory() as session, session.begin():
            # Insert in dependency order: sequence_references -> locations -> alleles
            # Use ON CONFLICT DO NOTHING to handle duplicates gracefully
            # We should have already de-duplicated by ID above, but duplicates
            # may already exist in the database.

            if sequence_references:
                sequence_reference_dicts = [
                    sr.to_dict() for sr in sequence_references.values()
                ]
                stmt = insert(SequenceReference)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, sequence_reference_dicts)

            if locations:
                location_dicts = [loc.to_dict() for loc in locations.values()]
                stmt = insert(Location)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, location_dicts)

            if alleles:
                allele_dicts = [allele.to_dict() for allele in alleles.values()]
                stmt = insert(Allele)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, allele_dicts)

    def get_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""
        object_ids_list = list(object_ids)
        results = []

        with self.session_factory() as session:
            if object_type == StoredObjectType.ALLELE:
                # Get alleles with eager loading
                db_objects = (
                    session.query(Allele)
                    .options(
                        joinedload(Allele.location).joinedload(
                            Location.sequence_reference
                        )
                    )
                    .filter(Allele.id.in_(object_ids_list))
                    .all()
                )
            elif object_type == StoredObjectType.SEQUENCE_LOCATION:
                # Get locations with eager loading
                db_objects = (
                    session.query(Location)
                    .options(joinedload(Location.sequence_reference))
                    .filter(Location.id.in_(object_ids_list))
                    .all()
                )
            elif object_type == StoredObjectType.SEQUENCE_REFERENCE:
                # Get sequence references
                db_objects = (
                    session.query(SequenceReference)
                    .filter(SequenceReference.id.in_(object_ids_list))
                    .all()
                )
            else:
                raise ValueError(f"Unsupported object type: {object_type}")

            for db_object in db_objects:
                vrs_object = mapper_registry.from_db_entity(db_object)
                results.append(vrs_object)

        return results

    def get_all_object_ids(self) -> Iterable[str]:
        """Retrieve all object IDs from storage."""
        with self.session_factory() as session:
            # TODO This only handles Alleles for now
            # TODO This seems like it could be a lot of data
            allele_ids = session.query(Allele.id).all()
            return [allele_id[0] for allele_id in allele_ids]

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
            else:
                raise ValueError(f"Unsupported object type: {object_type}")

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
        raise NotImplementedError

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
        raise NotImplementedError

    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: VariationMappingType,
    ) -> list[str]:
        """Return a list of ids of destination objects mapped from the source object.

        :param source_object_id: ID of the source object
        :param mapping_type: Type of VariationMappingType
        """
        raise NotImplementedError

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
        # TODO may load a lot of data
        with self.session_factory() as session:
            # Query alleles with overlapping locations
            # TODO this is any overlap, not containment.
            db_alleles = (
                session.query(Allele)
                .options(
                    joinedload(Allele.location).joinedload(Location.sequence_reference)
                )
                .join(Location)
                .join(SequenceReference)
                .filter(
                    SequenceReference.refseq_id == refget_accession,
                    Location.start <= stop,
                    Location.end >= start,
                )
                .all()
            )

            return [
                mapper_registry.from_db_entity(db_allele) for db_allele in db_alleles
            ]
