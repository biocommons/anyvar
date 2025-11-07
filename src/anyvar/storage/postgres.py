"""Provide PostgreSQL-based storage implementation."""

import json
import logging
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, sessionmaker

from anyvar.storage import orm
from anyvar.storage.base_storage import (
    DataIntegrityError,
    IncompleteVrsObjectError,
    InvalidSearchParamsError,
    Storage,
    StoredObjectType,
)
from anyvar.storage.mapper_registry import mapper_registry
from anyvar.storage.orm import create_tables
from anyvar.utils import types

_logger = logging.getLogger(__name__)


class PostgresObjectStore(Storage):
    """PostgreSQL storage backend using dedicated ORM tables.

    This implementation uses the new Allele, Location, and SequenceReference tables
    with object mapping to convert between VRS models and database entities.
    """

    def __init__(self, db_url: str, *args, **kwargs) -> None:
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
            session.execute(delete(orm.VariationMapping))
            session.execute(delete(orm.Allele))
            session.execute(delete(orm.Location))
            session.execute(delete(orm.SequenceReference))

            # Delete other tables
            session.execute(delete(orm.VrsObject))
            session.execute(delete(orm.Annotation))

    # TODO also store vrs_objects table in addition to
    # the tables per type.
    def add_objects(self, objects: Iterable[types.VrsObject]) -> None:
        """Add multiple VRS objects to storage using bulk inserts.

        If an object ID conflicts with an existing object, skip it.

        This method assumes that for VRS objects (e.g. `Allele`, `SequenceLocation`,
        `SequenceReference`) the `.id` property is present and uses the correct
        GA4GH identifier for that object. It also assumes that contained objects are
        similarly properly identified and materialized in full, not just as an IRI reference.
        An error is raised if these assumptions are violated, rolling back the entire
        transaction.

        :param objects: VRS objects to add to storage
        :raise IncompleteVrsObjectError: if object is missing required properties or if
            required properties aren't fully dereferenced
        """
        objects_list = list(objects)
        if not objects_list:
            return

        # Collect unique entities by ID to avoid duplicates
        sequence_references = {}
        locations = {}
        alleles = {}

        # Process all objects and extract their components
        for vrs_object in objects_list:
            try:
                db_entity = mapper_registry.to_db_entity(vrs_object)
            except AttributeError as e:
                raise IncompleteVrsObjectError from e

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
    ) -> Iterable[types.VrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs.

        If no object matches a given ID, that ID is skipped

        :param object_type: type of object to get
        :param object_ids: IDs of objects to fetch
        :return: iterable collection of VRS objects matching given IDs
        """
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
        """Retrieve all object IDs from storage.

        :return: all stored VRS object IDs
        """
        with self.session_factory() as session:
            # TODO This only handles Alleles for now
            # TODO This seems like it could be a lot of data
            stmt = select(orm.Allele.id)
            allele_ids = session.execute(stmt).scalars().all()
            return allele_ids

    def delete_objects(
        self, object_type: StoredObjectType, object_ids: Iterable[str]
    ) -> None:
        """Delete all objects of a specific type from storage.

        * If no object matching a given ID is found, it's ignored.
        * Deletes do not cascade.

        :param object_type: type of objects to delete
        :param object_ids: IDs of objects to delete
        :raise DataIntegrityError: if attempting to delete an object which is
            depended upon by another object
        """
        object_ids_list = list(object_ids)

        with self.session_factory() as session, session.begin():
            if object_type == StoredObjectType.ALLELE:
                stmt = delete(orm.Allele).where(orm.Allele.id.in_(object_ids_list))
            elif object_type == StoredObjectType.SEQUENCE_LOCATION:
                stmt = delete(orm.Location).where(orm.Location.id.in_(object_ids_list))
            elif object_type == StoredObjectType.SEQUENCE_REFERENCE:
                stmt = delete(orm.SequenceReference).where(
                    orm.SequenceReference.id.in_(object_ids_list)
                )
            else:
                raise ValueError(f"Unsupported object type: {object_type}")
            try:
                session.execute(stmt)
            except IntegrityError as e:
                _logger.exception(
                    "Attempted deletion that violated a foreign key constraint"
                )
                raise DataIntegrityError from e

    def add_mapping(self, mapping: types.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        Todo:
        * Implement insert constraint/MissingVariationReferenceError in #286

        :param mapping: mapping object
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB

        """
        stmt = (
            insert(orm.VariationMapping)
            .values(
                [
                    {
                        "source_id": mapping.source_id,
                        "dest_id": mapping.dest_id,
                        "mapping_type": mapping.mapping_type,
                    }
                ]
            )
            .on_conflict_do_nothing()
        )
        try:
            with self.session_factory() as session, session.begin():
                session.execute(stmt)
        except IntegrityError as e:
            raise KeyError from e

    def delete_mapping(self, mapping: types.VariationMapping) -> None:
        """Delete a mapping between two objects.

        * If no such mapping exists in the DB, does nothing.
        * Deletes do not cascade.

        :param mapping: mapping object
        """
        stmt = (
            delete(orm.VariationMapping)
            .where(orm.VariationMapping.source_id == mapping.source_id)
            .where(orm.VariationMapping.dest_id == mapping.dest_id)
            .where(orm.VariationMapping.mapping_type == mapping.mapping_type)
        )
        with self.session_factory() as session, session.begin():
            session.execute(stmt)

    def get_mappings(
        self,
        source_object_id: str,
        mapping_type: types.VariationMappingType | None = None,
    ) -> Iterable[types.VariationMapping]:
        """Return an iterable of mappings from the source ID

        Optionally provide a type to filter results.

        :param source_object_id: ID of the source object
        :param mapping_type: The type of mapping to retrieve (defaults to `None` to
            retrieve all mappings for the source ID)
        :return: iterable collection of mapping descriptors (empty if no matching mappings exist)
        """
        stmt = select(orm.VariationMapping).where(
            orm.VariationMapping.source_id == source_object_id
        )
        if mapping_type:
            stmt = stmt.where(orm.VariationMapping.mapping_type == mapping_type)
        with self.session_factory() as session, session.begin():
            mappings = session.scalars(stmt).all()
            return [mapper_registry.from_db_entity(mapping) for mapping in mappings]

    def add_annotation(self, annotation: types.Annotation) -> None:
        """Add an annotation to the database.

        Adding the same annotation repeatedly creates redundant records.

        Todo:
        * Implement insert constraint/MissingVariationReferenceError in #286

        :param annotation: The annotation to add
        :raise MissingVariationReferenceError: if no object corresponding to the annotation's object ID is present in DB

        """
        db_entity: orm.Annotation = mapper_registry.to_db_entity(annotation)
        stmt = insert(orm.Annotation).returning(orm.Annotation.id)
        with self.session_factory() as session, session.begin():
            session.execute(stmt, db_entity.to_dict()).scalar_one()

    def get_annotations(
        self, object_id: str, annotation_type: str | None = None
    ) -> list[types.Annotation]:
        """Get all annotations for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve annotations for
        :param annotation_type: The type of annotation to retrieve (defaults to `None` to retrieve all annotations for the object)
        :return: A list of annotations
        """
        stmt = select(orm.Annotation).where(orm.Annotation.object_id == object_id)
        if annotation_type:
            stmt = stmt.where(orm.Annotation.annotation_type == annotation_type)
        with self.session_factory() as session, session.begin():
            db_annotations = session.execute(stmt).scalars().all()

            return [
                mapper_registry.from_db_entity(db_annotation)
                for db_annotation in db_annotations
            ]

    def delete_annotation(self, annotation: types.Annotation) -> None:
        """Deletes an annotation from the database

        * If no such annotation exists, do nothing.
        * Deletes do not cascade.

        :param annotation: The annotation object to delete
        """
        stmt = (
            delete(orm.Annotation)
            .where(orm.Annotation.object_id == annotation.object_id)
            .where(orm.Annotation.annotation_type == annotation.annotation_type)
            .where(
                orm.Annotation.annotation_value
                == json.dumps(annotation.annotation_value)
            )
        )
        with self.session_factory() as session, session.begin():
            session.execute(stmt)

    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
    ) -> list[vrs_models.Allele]:
        """Find all Alleles that are located within the specified interval.

        The interval is the closed range [start, stop] on the sequence identified by
        the RefGet SequenceReference accession (`SQ.*`). Both `start` and `stop` are
        inclusive and represent inter-residue positions.

        Currently, any variation which overlaps the queried region is returned.

        Todo:
        * define alternate match modes (partial/full overlap/contained/etc)
        * define behavior for LSE indels and for alternative types of state (RLEs)

        Raises an error if
        * `start` or `end` are negative
        * `end` > `start`

        :param refget_accession: refget accession (e.g. `"SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"`)
        :param start: Inclusive, inter-residue start position of the interval
        :param stop: Inclusive, inter-residue end position of the interval
        :return: a list of matching VRS alleles
        :raise InvalidSearchParamsError: if above search param requirements are violated

        """
        if start < 0 or stop < 0 or start > stop:
            raise InvalidSearchParamsError
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
