"""Provide Snowflake-based storage implementation."""

import logging
import os
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from ga4gh.vrs import models as vrs_models
from snowflake.sqlalchemy import MergeInto
from snowflake.sqlalchemy.snowdialect import SnowflakeDialect
from sqlalchemy import String, column, create_engine, delete, insert, select, text
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import joinedload, sessionmaker
from sqlalchemy.sql import Values
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.expression import Insert

from anyvar.storage import orm
from anyvar.storage.base_storage import (
    DataIntegrityError,
    IncompleteVrsObjectError,
    InvalidSearchParamsError,
    Storage,
)
from anyvar.storage.mapper_registry import mapper_registry
from anyvar.utils import types

_logger = logging.getLogger(__name__)

snowflake.connector.paramstyle = "qmark"

#
# Monkey patch to workaround a bug in the Snowflake SQLAlchemy dialect
#  https://github.com/snowflakedb/snowflake-sqlalchemy/issues/489

# Create a new pointer to the existing create_connect_args method
SnowflakeDialect._orig_create_connect_args = SnowflakeDialect.create_connect_args  # noqa: SLF001


# Define a new create_connect_args method that calls the original method
#   and then fixes the result so that the account name is not mangled
#   when using privatelink
def sf_create_connect_args_override(self, url: URL) -> tuple[list, dict]:  # noqa: ANN001 D103
    # retval is tuple of empty array and dict ([], {})
    retval = self._orig_create_connect_args(url)

    # the dict has the options including the mangled account name
    opts = retval[1]
    if (
        "host" in opts
        and "account" in opts
        and opts["host"].endswith(".privatelink.snowflakecomputing.com")
    ):
        opts["account"] = opts["host"].split(".")[0]

    return retval


# Replace the create_connect_args method with the override
SnowflakeDialect.create_connect_args = sf_create_connect_args_override

#
# End monkey patch
#


class SnowflakeObjectStore(Storage):
    """Snowflake storage backend using dedicated ORM tables.

    This implementation uses the new Allele, Location, and SequenceReference tables
    with object mapping to convert between VRS models and database entities.
    """

    # temporary cap on max # of rows that can be returned by a single SQL query
    # issue 295 should convert this to a batch size parameter
    MAX_ROWS = 100

    _VRS_OBJECT_INSERT_ORDER: list[str] = [  # noqa: RUF012
        orm.SequenceReference.__name__,
        orm.Location.__name__,
        orm.Allele.__name__,
    ]

    def __init__(self, db_url: str, *args, **kwargs) -> None:
        """Initialize Snowflake storage.

        :param db_url: Database connection URL (e.g., snowflake://sf_username:@sf_account_identifier/sf_db_name/sf_schema_name?password=sf_password)
        """
        # pre-process to DB URL
        prepared_db_url = self._preprocess_db_url(db_url)

        # create the database connection engine
        self.engine = create_engine(
            prepared_db_url,
            connect_args=self._get_connect_args(prepared_db_url),
        )

        # create ORM session factory
        self.session_factory = sessionmaker(bind=self.engine)

        # determine if we are running with dynamic tables
        #   which only inserts into the main object ref table
        #   and relies on Snowflake dynamic tables to populate
        #   the allele/location/seqref tables
        self.use_dynamic_tables = (
            os.getenv("ANYVAR_SNOWFLAKE_STORE_USE_DYNAMIC_TABLES", "false").lower()
            == "true"
        )

        # create the schema objects if necessary
        if self.use_dynamic_tables:
            _logger.info(
                "SnowflakeObjectStore using dynamic tables for Allele, Location, SequenceReference"
            )
            orm.Base.metadata.create_all(self.engine, tables=[orm.VrsObject.__table__])
            self._create_dyn_tables()

        orm.Base.metadata.create_all(self.engine)

    def _preprocess_db_url(self, db_url: str) -> str:
        """Preprocess Snowflake DB URL to extract private key parameter if specified.

        :param db_url: Original database connection URL
        :return: Preprocessed database connection URL without private key parameter
        """
        db_url = db_url.replace(".snowflakecomputing.com", "")
        parsed_uri = urlparse(db_url)
        if parsed_uri.scheme != "snowflake":
            raise ValueError("DB URL scheme is not 'snowflake'")
        conn_params = {
            key: value[0] if value else None
            for key, value in parse_qs(parsed_uri.query).items()
        }
        if "private_key" in conn_params:
            self.private_key_param = conn_params["private_key"]
            del conn_params["private_key"]
            parsed_uri = parsed_uri._replace(query=urlencode(conn_params))
        else:
            self.private_key_param = None

        return urlunparse(parsed_uri)

    def _get_connect_args(self, db_url: str) -> dict[str, Any]:  # noqa: ARG002
        """Get Snowflake connection args.  Reads private key from file is private key file path
        was specified in the connection URL.

        :param db_url: Database connection URL
        :return: Dictionary of connection arguments
        """
        # if there is a private_key param that is a file, read the contents of file
        if self.private_key_param:
            p_key = None
            pk_passphrase = None
            if "ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE" in os.environ:
                pk_passphrase = os.environ[
                    "ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE"
                ].encode()
            if Path(self.private_key_param).is_file():
                with Path(self.private_key_param).open("rb") as key:
                    p_key = serialization.load_pem_private_key(
                        key.read(), password=pk_passphrase, backend=default_backend()
                    )
            else:
                p_key = serialization.load_pem_private_key(
                    self.private_key_param.encode(),
                    password=pk_passphrase,
                    backend=default_backend(),
                )

            return {
                "private_key": p_key.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            }
        return {}

    def _create_dyn_tables(self) -> None:
        """Create dynamic tables for Allele, Location, and SequenceReference."""
        with self.engine.connect() as conn:
            dyn_table_opts = os.getenv("ANYVAR_SNOWFLAKE_STORE_DYNAMIC_TABLE_OPTS", "")
            if not dyn_table_opts:
                sfwh = conn.scalar(text("SELECT CURRENT_WAREHOUSE()"))
                dyn_table_opts = f"WAREHOUSE = {sfwh} TARGET_LAG = '1 hour'"
            if not self.engine.dialect.has_table(conn, orm.Allele.__tablename__):
                conn.execute(
                    text(
                        f"""
                    CREATE TRANSIENT DYNAMIC TABLE IF NOT EXISTS {orm.Allele.__tablename__}
                    (
                        id VARCHAR(500) COLLATE 'utf8',
                        digest VARCHAR(500) COLLATE 'utf8',
                        location_id VARCHAR(500) COLLATE 'utf8',
                        state VARIANT
                    )
                    {dyn_table_opts}
                    AS SELECT
                        id,
                        COLLATE(vrs_object:digest::VARCHAR, 'utf8') AS digest,
                        COLLATE(vrs_object:location.id::VARCHAR, 'utf8') AS location_id,
                        vrs_object:state AS state
                    FROM {orm.VrsObject.__tablename__}
                    WHERE id LIKE 'ga4gh:VA.%'
                    """  # noqa: S608
                    )
                )
            if not self.engine.dialect.has_table(conn, orm.Location.__tablename__):
                conn.execute(
                    text(
                        f"""
                    CREATE TRANSIENT DYNAMIC TABLE IF NOT EXISTS {orm.Location.__tablename__}
                    (
                        id VARCHAR(500) COLLATE 'utf8',
                        digest VARCHAR(500) COLLATE 'utf8',
                        sequence_reference_id VARCHAR(500) COLLATE 'utf8',
                        start_pos INTEGER,
                        start_outer INTEGER,
                        start_inner INTEGER,
                        end_pos INTEGER,
                        end_outer INTEGER,
                        end_inner INTEGER
                    )
                    {dyn_table_opts}
                    AS SELECT DISTINCT
                        COLLATE(vrs_object:location.id::VARCHAR, 'utf8') AS id,
                        COLLATE(vrs_object:location.digest::VARCHAR, 'utf8') AS digest,
                        COLLATE(vrs_object:location.sequenceReference.refgetAccession::VARCHAR, 'utf8') AS sequence_reference_id,
                        (CASE WHEN IS_INTEGER(vrs_object:location.start) THEN vrs_object:location.start::INTEGER ELSE NULL END) AS start_pos,
                        (CASE WHEN IS_ARRAY(vrs_object:location.start) THEN GET(vrs_object:location.start, 0)::INTEGER ELSE NULL END) AS start_outer,
                        (CASE WHEN IS_ARRAY(vrs_object:location.start) THEN GET(vrs_object:location.start, 1)::INTEGER ELSE NULL END) AS start_inner,
                        (CASE WHEN IS_INTEGER(vrs_object:location.end) THEN vrs_object:location.end::INTEGER ELSE NULL END) AS end_pos,
                        (CASE WHEN IS_ARRAY(vrs_object:location.end) THEN GET(vrs_object:location.end, 0)::INTEGER ELSE NULL END) AS end_outer,
                        (CASE WHEN IS_ARRAY(vrs_object:location.end) THEN GET(vrs_object:location.end, 1)::INTEGER ELSE NULL END) AS end_inner
                    FROM {orm.VrsObject.__tablename__}
                    WHERE id LIKE 'ga4gh:VA.%'
                    """  # noqa: S608
                    )
                )
            if not self.engine.dialect.has_table(
                conn, orm.SequenceReference.__tablename__
            ):
                conn.execute(
                    text(
                        f"""
                    CREATE TRANSIENT DYNAMIC TABLE IF NOT EXISTS {orm.SequenceReference.__tablename__}
                    (
                        id VARCHAR(500) COLLATE 'utf8',
                        molecule_type VARCHAR(100)
                    )
                    {dyn_table_opts}
                    AS SELECT DISTINCT
                        COLLATE(vrs_object:location.sequenceReference.refgetAccession::VARCHAR, 'utf8') AS id,
                        vrs_object:location.sequenceReference.moleculeType::VARCHAR AS molecule_type
                    FROM {orm.VrsObject.__tablename__}
                    WHERE id LIKE 'ga4gh:VA.%'
                    """  # noqa: S608
                    )
                )

    def close(self) -> None:
        """Close the storage backend."""
        self.engine.dispose()

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.
        NOTE: This is a no-op for synchronous storage backends.
        """

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""
        with self.session_factory() as session, session.begin():
            # Delete all data from tables in dependency order
            session.execute(delete(orm.VariationMapping))
            if not self.use_dynamic_tables:
                session.execute(delete(orm.Allele))
                session.execute(delete(orm.Location))
                session.execute(delete(orm.SequenceReference))

            # Delete other tables
            session.execute(delete(orm.VrsObject))
            session.execute(delete(orm.Annotation))

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
        objects_list: list[types.VrsObject] = list(objects)
        if not objects_list:
            return

        # Collect unique entities by ID to avoid duplicates
        if not self.use_dynamic_tables:
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
            if not self.use_dynamic_tables:
                for vrs_object_type in self._VRS_OBJECT_INSERT_ORDER:
                    objects_by_id = vrs_objects[vrs_object_type]
                    if objects_by_id:
                        dicts = [entity.to_dict() for entity in objects_by_id.values()]
                        orm_model = getattr(orm, vrs_object_type)
                        stmt = insert(orm_model)
                        session.execute(stmt, dicts)
            dicts = [
                {
                    "id": obj.id,
                    "vrs_object": obj.model_dump(exclude_none=True),
                }
                for obj in objects_list
                if isinstance(obj, types.VrsObject) and obj.id is not None
            ]
            if len(dicts) > 0:
                stmt = insert(getattr(orm, orm.VrsObject.__name__))
                session.execute(stmt, dicts)

    def get_objects(
        self, object_type: type[types.VrsObject], object_ids: Iterable[str]
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
                    .limit(self.MAX_ROWS)
                )
                db_objects = session.scalars(stmt).all()
            elif object_type is vrs_models.SequenceLocation:
                # Get locations with eager loading
                stmt = (
                    select(orm.Location)
                    .options(joinedload(orm.Location.sequence_reference))
                    .where(orm.Location.id.in_(object_ids_list))
                    .limit(self.MAX_ROWS)
                )
                db_objects = session.scalars(stmt).all()
            elif object_type is vrs_models.SequenceReference:
                # Get sequence references
                stmt = (
                    select(orm.SequenceReference)
                    .where(orm.SequenceReference.id.in_(object_ids_list))
                    .limit(self.MAX_ROWS)
                )
                db_objects = session.scalars(stmt).all()
            else:
                raise ValueError(f"Unsupported object type: {object_type}")

            for db_object in db_objects:
                vrs_object = mapper_registry.from_db_entity(db_object)
                results.append(vrs_object)

        return results

    def delete_objects(
        self, object_type: type[types.VrsObject], object_ids: Iterable[str]
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
            stmt = None
            stmt2 = None
            if object_type is vrs_models.Allele:
                if not self.use_dynamic_tables:
                    stmt = delete(orm.Allele).where(orm.Allele.id.in_(object_ids_list))
                stmt2 = delete(orm.VrsObject).where(
                    orm.VrsObject.id.in_(object_ids_list)
                )
            elif object_type is vrs_models.SequenceLocation:
                if not self.use_dynamic_tables:
                    stmt = delete(orm.Location).where(
                        orm.Location.id.in_(object_ids_list)
                    )
            elif object_type is vrs_models.SequenceReference:
                if not self.use_dynamic_tables:
                    stmt = delete(orm.SequenceReference).where(
                        orm.SequenceReference.id.in_(object_ids_list)
                    )
            else:
                raise ValueError(f"Unsupported object type: {object_type}")
            try:
                if stmt is not None:
                    session.execute(stmt)
                if stmt2 is not None:
                    session.execute(stmt2)
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
        :raises ValueError: If source_id equals dest_id
        :raise MissingVariationReferenceError: if source or destination IDs aren't present in DB

        """
        if mapping.source_id == mapping.dest_id:
            msg = f"source_id cannot equal dest_id: {mapping.source_id}"
            raise ValueError(msg)

        # use a merge statement to avoid duplicates if we are protecting against them
        #   since this is a single row insert, just use MERGE.  If this becomes a bulk
        #   insert, switch to use a JOIN to mimic MERGE
        if (
            os.getenv("ANYVAR_SNOWFLAKE_STORE_USE_JOIN_FOR_MERGE", "true").lower()
            == "true"
        ):
            source = Values(
                column("source_id", String()),
                column("dest_id", String()),
                column("mapping_type", orm.mapping_type_enum),
                name="src",
            ).data([(mapping.source_id, mapping.dest_id, mapping.mapping_type)])

            # Define the MERGE statement
            stmt = MergeInto(
                target=orm.VariationMapping.__table__,
                source=source,
                on=(
                    (orm.VariationMapping.__table__.c.source_id == source.c.source_id)
                    & (orm.VariationMapping.__table__.c.dest_id == source.c.dest_id)
                    & (
                        orm.VariationMapping.__table__.c.mapping_type
                        == source.c.mapping_type
                    )
                ),
            )

            # Define clauses for matched and not-matched scenarios
            stmt.when_not_matched_then_insert().values(
                source_id=source.c.source_id,
                dest_id=source.c.dest_id,
                mapping_type=source.c.mapping_type,
            )
        # otherwise do a straight insert
        else:
            stmt = insert(orm.VariationMapping).values(
                [
                    {
                        "source_id": mapping.source_id,
                        "dest_id": mapping.dest_id,
                        "mapping_type": mapping.mapping_type,
                    }
                ]
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
        stmt = (
            select(orm.VariationMapping)
            .where(orm.VariationMapping.source_id == source_object_id)
            .limit(self.MAX_ROWS)
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
        stmt = insert(orm.Annotation)
        with self.session_factory() as session, session.begin():
            session.execute(stmt, db_entity.to_dict())

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

        stmt = stmt.limit(self.MAX_ROWS)

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
            .where(orm.Annotation.annotation_value == annotation.annotation_value)
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

        Todo (see Issue #338):
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

        with self.session_factory() as session:
            # Query alleles with overlapping locations
            # NOTE: this is any overlap, not containment.
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
                .limit(self.MAX_ROWS)
            )
            db_alleles = session.scalars(stmt).all()

            return [
                mapper_registry.from_db_entity(db_allele) for db_allele in db_alleles
            ]


@compiles(Insert, "snowflake")
def compile_insert_with_parse_json_and_join_for_merge(
    insert_stmt: Insert, compiler: SQLCompiler, **kwargs
) -> str:
    """Custom compilation of INSERT statements for Snowflake to use PARSE_JSON
    to convert strings into VARIANTs and optionally use a LEFT OUTER JOIN to avoid
    inserting duplicate IDs.
    """
    # determine if the insert is for a table where we need to modify the insert statement
    json_col = None
    target_table = None
    if (
        insert_stmt.entity_description.get("table", None)
        == orm.SequenceReference.__table__
    ):
        target_table = orm.SequenceReference.__tablename__
    elif insert_stmt.entity_description.get("table", None) == orm.Location.__table__:
        target_table = orm.Location.__tablename__
    elif insert_stmt.entity_description.get("table", None) == orm.Allele.__table__:
        json_col = orm.Allele.state.name
        target_table = orm.Allele.__tablename__
    elif insert_stmt.entity_description.get("table", None) == orm.VrsObject.__table__:
        json_col = orm.VrsObject.vrs_object.name
        target_table = orm.VrsObject.__tablename__
    elif insert_stmt.entity_description.get("table", None) == orm.Annotation.__table__:
        json_col = orm.Annotation.annotation_value.name
        target_table = orm.Annotation.__tablename__

    if target_table:
        # Generate the default insert SQL, usually of the form:
        #   INSERT INTO table (col1, col2, json_col, ...) VALUES (%(col1)s, %(col2)s, %(json_col)s, ...)
        insert_sql = compiler.visit_insert(insert_stmt, **kwargs)

        # Collect information about the columns being inserted
        select_list = []
        id_col_idx = -1
        idx = 1
        found = False
        for key in insert_stmt.compile().params:
            # skip any keys that are not in the insert statement
            if f"%({key})s" not in insert_sql:
                continue

            # all the primary key columns are named "id"
            if key == "id":
                id_col_idx = idx
                found = True

            # for the JSON column, use PARSE_JSON to convert the string into a VARIANT
            if key == json_col:
                select_list.append(f"PARSE_JSON(v.${idx})")
                found = True
            # otherwise, just reference the value directly
            else:
                select_list.append(f"v.${idx}")

            idx += 1

        # Either an "id" or JSON column was found so need to modify the insert SQL
        if found:
            # Replace the VALUES clause with a SELECT from VALUES clause
            insert_sql = insert_sql.replace(
                ") VALUES (",
                f") SELECT {', '.join(select_list)} FROM VALUES (",  # noqa: S608
            )
            insert_sql += " v"

            # If we have an id column and are using join to mimic merge, use a LEFT OUTER JOIN to avoid inserting duplicates
            if (
                target_table
                and id_col_idx != -1
                and os.getenv(
                    "ANYVAR_SNOWFLAKE_STORE_USE_JOIN_FOR_MERGE", "true"
                ).lower()
                == "true"
            ):
                insert_sql += f" LEFT OUTER JOIN {target_table} vo ON vo.id = v.${id_col_idx} WHERE vo.id IS NULL"

            # Return the modified insert SQL
            return insert_sql

    # If not modifying the SQL, return the default compilation
    return compiler.visit_insert(insert_stmt, **kwargs)
