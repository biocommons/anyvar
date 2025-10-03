"""Provide PostgreSQL-based storage implementation."""

from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload, sessionmaker

from anyvar.storage.base_storage import (
    Storage,
    StoredVrsObjectType,
    VariationMappingType,
)
from anyvar.storage.mapper_registry import mapper_registry
from anyvar.storage.orm import (
    AlleleOrm,
    AnnotationOrm,
    LocationOrm,
    SequenceReferenceOrm,
    VrsObjectOrm,
    create_tables,
)
from anyvar.utils.types import Annotation


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
            session.execute(delete(AlleleOrm))
            session.execute(delete(LocationOrm))
            session.execute(delete(SequenceReferenceOrm))

            # Delete other tables
            session.execute(delete(VrsObjectOrm))
            session.execute(delete(AnnotationOrm))

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

            if isinstance(db_entity, AlleleOrm):
                alleles[db_entity.id] = db_entity
                # Also collect the nested location and sequence reference
                if db_entity.location:
                    locations[db_entity.location.id] = db_entity.location
                    if db_entity.location.sequence_reference:
                        sequence_references[
                            db_entity.location.sequence_reference.id
                        ] = db_entity.location.sequence_reference
            elif isinstance(db_entity, LocationOrm):
                locations[db_entity.id] = db_entity
                if db_entity.sequence_reference:
                    sequence_references[db_entity.sequence_reference.id] = (
                        db_entity.sequence_reference
                    )
            elif isinstance(db_entity, SequenceReferenceOrm):
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
                stmt = insert(SequenceReferenceOrm)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, sequence_reference_dicts)

            if locations:
                location_dicts = [loc.to_dict() for loc in locations.values()]
                stmt = insert(LocationOrm)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, location_dicts)

            if alleles:
                allele_dicts = [allele.to_dict() for allele in alleles.values()]
                stmt = insert(AlleleOrm)
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt, allele_dicts)

    def get_objects(
        self, object_type: StoredVrsObjectType, object_ids: Iterable[str]
    ) -> Iterable[vrs_models.VrsType]:
        """Retrieve multiple VRS objects from storage by their IDs."""
        object_ids_list = list(object_ids)
        results = []

        with self.session_factory() as session:
            if object_type == StoredVrsObjectType.ALLELE:
                # Get alleles with eager loading
                stmt = (
                    select(AlleleOrm)
                    .options(
                        joinedload(AlleleOrm.location).joinedload(
                            LocationOrm.sequence_reference
                        )
                    )
                    .where(AlleleOrm.id.in_(object_ids_list))
                )
                db_objects = session.scalars(stmt).all()
            elif object_type == StoredVrsObjectType.SEQUENCE_LOCATION:
                # Get locations with eager loading
                stmt = (
                    select(LocationOrm)
                    .options(joinedload(LocationOrm.sequence_reference))
                    .where(LocationOrm.id.in_(object_ids_list))
                )
                db_objects = session.scalars(stmt).all()
            elif object_type == StoredVrsObjectType.SEQUENCE_REFERENCE:
                # Get sequence references
                stmt = select(SequenceReferenceOrm).where(
                    SequenceReferenceOrm.id.in_(object_ids_list)
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
            stmt = select(AlleleOrm.id)
            allele_ids = session.execute(stmt).scalars().all()
            return allele_ids

    def delete_objects(
        self, object_type: StoredVrsObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage."""
        object_ids_list = list(object_ids)

        with self.session_factory() as session, session.begin():
            if object_type == StoredVrsObjectType.ALLELE:
                stmt = delete(AlleleOrm).where(AlleleOrm.id.in_(object_ids_list))
                session.execute(stmt)
            elif object_type == StoredVrsObjectType.SEQUENCE_LOCATION:
                stmt = delete(LocationOrm).where(LocationOrm.id.in_(object_ids_list))
                session.execute(stmt)
            elif object_type == StoredVrsObjectType.SEQUENCE_REFERENCE:
                stmt = delete(SequenceReferenceOrm).where(
                    SequenceReferenceOrm.id.in_(object_ids_list)
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
                select(AlleleOrm)
                .options(
                    joinedload(AlleleOrm.location).joinedload(
                        LocationOrm.sequence_reference
                    )
                )
                .join(LocationOrm)
                .join(SequenceReferenceOrm)
                .where(
                    SequenceReferenceOrm.id == refget_accession,
                    LocationOrm.start <= stop,
                    LocationOrm.end >= start,
                )
            )
            db_alleles = session.scalars(stmt).all()

            return [
                mapper_registry.from_db_entity(db_allele) for db_allele in db_alleles
            ]

    def add_annotation(self, annotation: Annotation) -> int:
        """Adds an annotation to the database.

        :param annotation: The annotation to add
        :return: The ID of the newly-added annotation
        """
        db_entity: AnnotationOrm = mapper_registry.to_db_entity(annotation)
        with self.session_factory() as session, session.begin():
            stmt = (
                insert(AnnotationOrm)
                .on_conflict_do_update(
                    index_elements=[AnnotationOrm.id],  # conflict target: primary key
                    set_={
                        "object_id": db_entity.object_id,
                        "annotation_type": db_entity.annotation_type,
                        "annotation_value": db_entity.annotation_value,
                    },
                )
                .returning(AnnotationOrm.id)
            )
            return session.execute(stmt, db_entity.to_dict()).scalar_one()

    def get_annotations_by_object_and_type(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[Annotation]:
        """Retrieves all annotations for the given object, optionally filtered to only annotations of the specified type from the database

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve
        :return: A list of annotations
        """
        with self.session_factory() as session, session.begin():
            stmt = (
                select(AnnotationOrm)
                .where(AnnotationOrm.object_id == object_id)
                .where(AnnotationOrm.annotation_type == annotation_type)
            )
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
            stmt = delete(AnnotationOrm).where(AnnotationOrm.id == annotation_id)
            session.execute(stmt)
