"""Abstract SqlAlchemy storage class

Any database with an active SQLAlchemy engine should be able to pull resources from this
class with minimal additional implementation to achieve a fully functional AnyVar storage class
"""

import base64
import json
import logging
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Iterable

from ga4gh.vrs import models as vrs_models
from sqlalchemy import ColumnElement, and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from anyvar.core import metadata
from anyvar.core import objects as anyvar_objects
from anyvar.core.categorical_variants import CanonicalAllele, ProteinSequenceConsequence
from anyvar.storage import orm
from anyvar.storage.base import (
    AlleleSearchPage,
    DataIntegrityError,
    IncompleteVrsObjectError,
    InvalidSearchParamsError,
    Storage,
)
from anyvar.storage.mapper_registry import mapper_registry

_logger = logging.getLogger(__name__)


class SqlAlchemyStorage(Storage):
    """Abstract base class for interacting with storage backends."""

    MAX_ROWS = 100

    session_factory: sessionmaker[Session]

    _VRS_OBJECT_INSERT_ORDER: list[str] = [  # noqa: RUF012
        orm.SequenceReference.__name__,
        orm.Location.__name__,
        orm.Allele.__name__,
    ]

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""
        with self.session_factory() as session, session.begin():
            session.execute(delete(orm.VariationMapping))
            session.execute(delete(orm.Allele))
            session.execute(delete(orm.Location))
            session.execute(delete(orm.SequenceReference))

            # Delete other tables
            session.execute(delete(orm.VrsObject))
            session.execute(delete(orm.Extension))

    @abstractmethod
    def _insert_ignore_conflict(
        self, session: Session, orm_model: type[orm.Base], values: list[dict]
    ) -> None:
        """Perform an insert of the given values sets, ignoring ID conflicts

        Should be implemented using specific engines/dialects of subclasses

        :param session:
        :param orm_model:
        :param values:
        """

    def add_objects(self, objects: Iterable[anyvar_objects.SupportedVrsObject]) -> None:
        """Add multiple VRS objects to storage.

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
        objects_list: list[anyvar_objects.SupportedVrsObject] = list(objects)
        if not objects_list:
            return

        # Collect unique entities by ID to avoid duplicates
        vrs_objects = defaultdict(dict[str, orm.Base])

        # Process all objects and extract their components
        for vrs_object in objects_list:
            try:
                db_entity = mapper_registry.to_db_entity(vrs_object)
            except AttributeError as e:
                raise IncompleteVrsObjectError from e

            object_parts = db_entity.disassemble()
            for entity_type, entity in object_parts.items():
                vrs_objects[entity_type][entity.id] = entity  # type: ignore (all children of orm.Base have an `id`)

        with self.session_factory() as session, session.begin():
            # Use ON CONFLICT DO NOTHING to handle duplicates gracefully
            # We should have already de-duplicated by ID above, but duplicates
            # may already exist in the database.

            for vrs_object_type in self._VRS_OBJECT_INSERT_ORDER:
                objects_by_id = vrs_objects[vrs_object_type]
                if objects_by_id:
                    dicts = [entity.to_dict() for entity in objects_by_id.values()]
                    orm_model = getattr(orm, vrs_object_type)
                    self._insert_ignore_conflict(session, orm_model, dicts)

    def get_objects(
        self,
        object_type: type[anyvar_objects.SupportedVrsObject],
        object_ids: Iterable[str],
    ) -> Iterable[anyvar_objects.SupportedVrsObject]:
        """Retrieve multiple VRS objects from storage by their IDs.

        If no object matches a given ID, that ID is skipped

        :param object_type: type of object to get
        :param object_ids: IDs of objects to fetch
        :return: iterable collection of VRS objects matching given IDs
        """
        object_ids_list = list(object_ids)
        if not object_ids_list:
            return []

        results = []
        with self.session_factory() as session:
            if object_type is vrs_models.Allele:
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
            elif object_type is vrs_models.SequenceLocation:
                # Get locations with eager loading
                stmt = (
                    select(orm.Location)
                    .options(joinedload(orm.Location.sequence_reference))
                    .where(orm.Location.id.in_(object_ids_list))
                )
                db_objects = session.scalars(stmt).all()
            elif object_type is vrs_models.SequenceReference:
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

    def delete_objects(
        self,
        object_type: type[anyvar_objects.SupportedVrsObject],
        object_ids: Iterable[str],
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
            if object_type is vrs_models.Allele:
                stmt = delete(orm.Allele).where(orm.Allele.id.in_(object_ids_list))
            elif object_type is vrs_models.SequenceLocation:
                stmt = delete(orm.Location).where(orm.Location.id.in_(object_ids_list))
            elif object_type is vrs_models.SequenceReference:
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

    def add_mapping(self, mapping: metadata.VariationMapping) -> None:
        """Add a mapping between two objects.

        If the mapping instance already exists, do nothing.

        Todo:
        * Implement insert constraint/MissingVariationReferenceError in #286

        :param mapping: mapping object
        :raises ValueError: If source_id equals dest_id
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB

        """
        if mapping.source_id == mapping.dest_id:
            msg = f"source_id cannot equal dest_id: {mapping.source_id}"
            raise ValueError(msg)

        values = [
            {
                "source_id": mapping.source_id,
                "dest_id": mapping.dest_id,
                "mapping_type": mapping.mapping_type,
            }
        ]
        try:
            with self.session_factory() as session, session.begin():
                self._insert_ignore_conflict(session, orm.VariationMapping, values)
        except IntegrityError as e:
            raise KeyError from e

    def delete_mapping(self, mapping: metadata.VariationMapping) -> None:
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
        object_id: str,
        as_source: bool,
        mapping_type: metadata.VariationMappingType | None = None,
    ) -> Iterable[metadata.VariationMapping]:
        """Return an iterable of mappings

        Optionally provide a type to filter results.

        :param object_id: ID of object to get mappings for
        :param as_source: If ``True``, object_id is treated as the source. If ``False``,
            ``object_id`` is treated as the destination.
        :param mapping_type: The type of mapping to retrieve (defaults to `None` to
            retrieve all mappings for the source ID)
        :return: iterable collection of mapping descriptors (empty if no matching mappings exist)
        """
        stmt = select(orm.VariationMapping).limit(self.MAX_ROWS)
        if as_source:
            stmt = stmt.where(orm.VariationMapping.source_id == object_id)
        else:
            stmt = stmt.where(orm.VariationMapping.dest_id == object_id)
        if mapping_type:
            stmt = stmt.where(orm.VariationMapping.mapping_type == mapping_type)
        with self.session_factory() as session, session.begin():
            mappings = session.scalars(stmt).all()
            return [mapper_registry.from_db_entity(mapping) for mapping in mappings]

    def add_extension(self, extension: metadata.Extension) -> None:
        """Add an extension to the database.

        Adding the same extension repeatedly creates redundant records.

        Todo:
        * Implement insert constraint/MissingVariationReferenceError in #286

        :param extension: The extension to add
        :raise MissingVariationReferenceError: if no object corresponding to the extension's object ID is present in DB

        """
        db_entity: orm.Extension = mapper_registry.to_db_entity(extension)
        with self.session_factory() as session, session.begin():
            self._insert_ignore_conflict(session, orm.Extension, [db_entity.to_dict()])

    def get_extensions(
        self, object_id: str, extension_name: str | None = None
    ) -> list[metadata.Extension]:
        """Get all extensions for the specified object, optionally filtered by type.

        :param object_id: The ID of the object to retrieve extensions for
        :param extension_type: The type of extension to retrieve (defaults to `None` to retrieve all extensions for the object)
        :return: A list of extensions
        """
        stmt = select(orm.Extension).where(orm.Extension.object_id == object_id)

        if extension_name:
            stmt = stmt.where(orm.Extension.name == extension_name)

        stmt = stmt.limit(self.MAX_ROWS)

        with self.session_factory() as session, session.begin():
            db_extensions = session.execute(stmt).scalars().all()

            return [
                mapper_registry.from_db_entity(db_extension)
                for db_extension in db_extensions
            ]

    @staticmethod
    def _encode_search_cursor(start: int, allele_id: str) -> str:
        """Create cursor for search

        :param start: start value for next row
        :param allele_id: ID for next row
        :return: cursor to use to fetch next page
        """
        raw = json.dumps(
            {"start": start, "id": allele_id}, separators=(",", ":")
        ).encode()
        return base64.urlsafe_b64encode(raw).decode()

    @staticmethod
    def _decode_search_cursor(cursor: str) -> tuple[int, str]:
        """Decode cursor for getting next page during search

        :param cursor: opaque key included with previous result
        :return: start and ID values indicating the first row of the next page
        """
        raw = base64.urlsafe_b64decode(cursor.encode())
        obj = json.loads(raw)
        return int(obj["start"]), str(obj["id"])

    def _overlaps_interval_predicate(
        self, start: int, stop: int
    ) -> ColumnElement[bool]:
        """Return a SQL predicate selecting locations that overlap an interval

        This helper encapsulates the interval-overlap logic used by allele search
        queries. The default implementation uses a portable comparison-based
        predicate that works across SQL backends:

            location.start <= query_stop
            AND
            location.end >= query_start

        Subclasses may override this method to take advantage of backend-specific
        features. For example, PostgreSQL can use native range types and GiST
        indexes to accelerate overlap searches.

        :param start: Inclusive, inter-residue start position of the query interval
        :param stop: Inclusive, inter-residue end position of the query interval
        :return: SQLAlchemy boolean expression selecting overlapping locations
        """
        return and_(
            orm.Location.start <= stop,
            orm.Location.end >= start,
        )

    def search_alleles(
        self,
        refget_accession: str,
        start: int,
        stop: int,
        page_size: int = 1000,
        cursor: str | None = None,
    ) -> AlleleSearchPage:
        """Find all Alleles that are located within the specified interval.

        The interval is the closed range [start, stop] on the sequence identified by
        the RefGet SequenceReference accession (`SQ.*`). Both `start` and `stop` are
        inclusive and represent inter-residue positions.

        Uses keyset pagination, meaning that altering the page size while looping through
        successive cursors will effectively nullify the search loop.

        Currently, any variation which overlaps the queried region is returned.

        Raises an error if
        * `start` or `end` are negative
        * `end` > `start`

        Todo (see Issue #338):
        * define alternate match modes (partial/full overlap/contained/etc)
        * define behavior for LSE indels and for alternative types of state (RLEs)

        :param refget_accession: refget accession (e.g. `"SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"`)
        :param start: Inclusive, inter-residue start position of the interval
        :param stop: Inclusive, inter-residue end position of the interval
        :param page_size: Max # of results to return
        :param cursor: Opaque key indicating start location for query in pagination
        :return: Results page including variants and a cursor for next result page, if available
        :raise InvalidSearchParamsError: if above search param requirements are violated
        """
        if start < 0 or stop < 0 or start > stop:
            raise InvalidSearchParamsError
        seek_start: int | None = None
        seek_id: str | None = None
        if cursor:
            seek_start, seek_id = self._decode_search_cursor(cursor)

        with self.session_factory() as session:
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
                    self._overlaps_interval_predicate(start, stop),
                )
                .order_by(orm.Location.start, orm.Allele.id)
                .limit(page_size)
            )

            # seek predicate -- assumes ORDER BY location.start ASC, allele.id ASC
            if seek_start is not None and seek_id is not None:
                stmt = stmt.where(
                    or_(
                        orm.Location.start > seek_start,
                        and_(orm.Location.start == seek_start, orm.Allele.id > seek_id),
                    )
                )

            page_db = session.scalars(stmt).all()
            items = [mapper_registry.from_db_entity(a) for a in page_db]
            if not page_db:
                return AlleleSearchPage(items=[], next_cursor=None)
            last = page_db[-1]
            next_cursor = self._encode_search_cursor(last.location.start, last.id)
            return AlleleSearchPage(items=items, next_cursor=next_cursor)

    def add_ca_catvar(self, ca: CanonicalAllele) -> None:
        """Add a Canonical Allele Categorical Variant

        This method **is not** responsible for validating that the provided catvar meets
        data requirements to be considered a Canonical Allele instance;
        passing an object without prior validation may raise unexpected errors

        :param ca: canonical allele catvar
        """
        db_entity: orm.CanonicalAllele = mapper_registry.to_db_entity(ca)
        with self.session_factory() as session, session.begin():
            session.merge(db_entity.allele)
            session.flush()
            session.merge(db_entity)

    def get_ca_catvar(self, ca_id: str) -> CanonicalAllele | None:
        """Fetch a Canonical Allele categorical variant by ID

        Performs exact match -- case sensitive

        :param ca_id: requested object ID
        :return: matching canonical allele, if found
        """
        with self.session_factory() as session, session.begin():
            ca = session.get(orm.CanonicalAllele, ca_id)
            if ca:
                return mapper_registry.from_db_entity(ca)
        return None

    def add_psq_catvar(self, psq: ProteinSequenceConsequence) -> None:
        """Add a Protein Sequence Consequence Categorical Variant

        This method **is not** responsible for validating that the provided catvar meets
        data requirements to be considered a Protein Sequence Consequence instance;
        passing an object without prior validation may raise unexpected errors

        :param psq: protein sequence consequence catvar
        """
        db_entity: orm.ProteinSequenceConsequence = mapper_registry.to_db_entity(psq)
        with self.session_factory() as session, session.begin():
            session.merge(db_entity.allele)
            session.flush()
            session.merge(db_entity)

    def get_psq_catvar(self, psq_id: str) -> ProteinSequenceConsequence | None:
        """Fetch a Protein Sequence Consequence categorical variant by ID

        Performs exact match -- case sensitive

        :param psq_id: requested object ID
        :return: matching canonical allele, if found
        """
        with self.session_factory() as session, session.begin():
            ca = session.get(orm.ProteinSequenceConsequence, psq_id)
            if ca:
                return mapper_registry.from_db_entity(ca)
        return None
