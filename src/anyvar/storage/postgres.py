"""Provide PostgreSQL-based storage implementation."""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload, sessionmaker

from anyvar.storage import orm
from anyvar.storage.base_storage import (
    Storage,
    StoredObjectType,
    VariationMappingType,
)
from anyvar.storage.mapper_registry import mapper_registry
from anyvar.storage.orm import create_tables
from anyvar.utils import types


class PostgresObjectStore(Storage):
    """PostgreSQL storage backend using dedicated ORM tables.

    This implementation uses the new Allele, Location, and SequenceReference tables
    with object mapping to convert between VRS models and database entities.
    """

    def __init__(self, db_url: str | None = None) -> None:
        """Initialize PostgreSQL storage.

        :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
        """
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.session_factory = sessionmaker(bind=self.engine)
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
            session.execute(delete(orm.Allele))
            session.execute(delete(orm.Location))
            session.execute(delete(orm.SequenceReference))

            # Delete other tables
            session.execute(delete(orm.VrsObject))
            session.execute(delete(orm.Annotation))

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

            if isinstance(db_entity, orm.Allele):
                alleles[db_entity.id] = db_entity
                # Also collect the nested location and sequence reference
                if db_entity.location:
                    locations[db_entity.location.id] = db_entity.location
                    if db_entity.location.sequence_reference:
                        sequence_references[
                            db_entity.location.sequence_reference.id
                        ] = db_entity.location.sequence_reference
            elif isinstance(db_entity, orm.Location):
                locations[db_entity.id] = db_entity
                if db_entity.sequence_reference:
                    sequence_references[db_entity.sequence_reference.id] = (
                        db_entity.sequence_reference
                    )
            elif isinstance(db_entity, orm.SequenceReference):
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
                stmt = insert(orm.SequenceReference)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, sequence_reference_dicts)

            if locations:
                location_dicts = [loc.to_dict() for loc in locations.values()]
                stmt = insert(orm.Location)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, location_dicts)

            if alleles:
                allele_dicts = [allele.to_dict() for allele in alleles.values()]
                stmt = insert(orm.Allele)
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
                stmt = (
                    select(orm.Allele)
                    .options(
                        joinedload(orm.Allele.location).joinedload(
                            orm.Location.sequence_reference
                        )
                    )
                    .where(orm.Allele.id.in_(object_ids_list))
                )
                db_objects = session.scalars(stmt).all()
            elif object_type == StoredObjectType.SEQUENCE_LOCATION:
                # Get locations with eager loading
                stmt = (
                    select(orm.Location)
                    .options(joinedload(orm.Location.sequence_reference))
                    .where(orm.Location.id.in_(object_ids_list))
                )
                db_objects = session.scalars(stmt).all()
            elif object_type == StoredObjectType.SEQUENCE_REFERENCE:
                # Get sequence references
                stmt = select(orm.SequenceReference).where(
                    orm.SequenceReference.id.in_(object_ids_list)
                )
                db_objects = session.scalars(stmt).all()
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
            stmt = select(orm.Allele.id)
            allele_ids = session.execute(stmt).scalars().all()
            return allele_ids

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""
        object_ids_list = list(object_ids)

        with self.session_factory() as session, session.begin():
            if object_type == StoredObjectType.ALLELE:
                stmt = delete(orm.Allele).where(orm.Allele.id.in_(object_ids_list))
                session.execute(stmt)
            elif object_type == StoredObjectType.SEQUENCE_LOCATION:
                stmt = delete(orm.Location).where(orm.Location.id.in_(object_ids_list))
                session.execute(stmt)
            elif object_type == StoredObjectType.SEQUENCE_REFERENCE:
                stmt = delete(orm.SequenceReference).where(
                    orm.SequenceReference.id.in_(object_ids_list)
                )
                session.execute(stmt)
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
            stmt = (
                select(orm.Allele)
                .options(
                    joinedload(orm.Allele.location).joinedload(
                        orm.Location.sequence_reference
                    )
                )
                .join(orm.Location)
                .join(orm.SequenceReference)
                .where(
                    orm.SequenceReference.id == refget_accession,
                    orm.Location.start <= stop,
                    orm.Location.end >= start,
                )
            )
            db_alleles = session.scalars(stmt).all()

            return [
                mapper_registry.from_db_entity(db_allele) for db_allele in db_alleles
            ]

    def add_annotation(self, annotation: types.Annotation) -> int:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
        """
        db_entity: orm.Annotation = mapper_registry.to_db_entity(annotation)
        with self.session_factory() as session, session.begin():
            stmt = insert(orm.Annotation).returning(orm.Annotation.id)
            return session.execute(stmt, db_entity.to_dict()).scalar_one()

    def get_annotations_by_object_and_type(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """
        with self.session_factory() as session, session.begin():
            stmt = select(orm.Annotation).where(orm.Annotation.object_id == object_id)
            if annotation_type:
                stmt = stmt.where(orm.Annotation.annotation_type == annotation_type)

            db_annotations = session.execute(stmt).scalars().all()

            return [
                mapper_registry.from_db_entity(db_annotation)
                for db_annotation in db_annotations
            ]

    def delete_annotation(self, annotation_id: int) -> None:
        """Deletes an annotation from the database

        :param annotation_id: The ID of the annotation to delete
        """
        with self.session_factory() as session, session.begin():
            stmt = delete(orm.Annotation).where(orm.Annotation.id == annotation_id)
            session.execute(stmt)
