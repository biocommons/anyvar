"""SQLAlchemy ORM models for AnyVar database schema."""

import json
import os
from collections.abc import Iterator
from urllib.parse import urlparse

import snowflake.sqlalchemy.snowdialect
from ga4gh.vrs.models import MoleculeType
from sqlalchemy import (
    JSON,
    Dialect,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.orm.decl_api import declared_attr
from sqlalchemy.types import TypeDecorator

from anyvar.storage import DEFAULT_STORAGE_URI
from anyvar.utils.funcs import camel_case_to_snake_case
from anyvar.utils.types import VariationMappingType


class SnowflakeVARIANT(TypeDecorator):
    """Custom SQLAlchemy type to handle Snowflake VARIANT type.
    For INSERTs and UPDATEs, converts Python dicts to JSON strings.
    """

    impl = snowflake.sqlalchemy.snowdialect.VARIANT

    def process_bind_param(self, value, dialect: Dialect):  # noqa: ANN001 ANN201
        """Convert value to a JSON string for Snowflake VARIANT storage."""
        if value is not None and dialect.name == "snowflake":
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect: Dialect):  # noqa: ANN001 ANN201
        """Convert JSON string back to dict when retrieving from Snowflake VARIANT."""
        if value is not None and isinstance(value, str) and dialect.name == "snowflake":
            return json.loads(value)  # Convert JSON string back to dict
        return value


class Base(DeclarativeBase):
    """Base class for all AnyVar ORM models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805 (param name here should be 'cls', not 'self')
        # Default table name = class name, transformed from PascalCase into snake_case and pluralized.
        # Example: The table name created by the "VrsObject" ORM class is `vrs_objects`
        # NOTE: Classes/tables that require a different pluralization scheme should override this function.
        default_name: str = camel_case_to_snake_case(cls.__name__, False) + "s"

        # Environment variable name is the class name transformed into UPPER_SNAKE_CASE, pluralized, and prefixed by 'ANYVAR_' + suffixed with "_TABLE_NAME".
        # e.g., the environment variable to override the table name created by the "VrsObject" ORM class is `ANYVAR_VRS_OBJECTS_TABLE_NAME`
        environment_variable_name: str = f"ANYVAR_{default_name.upper()}_TABLE_NAME"

        return os.getenv(environment_variable_name) or default_name

    def to_dict(self) -> dict:
        """Convert the model fields to a dictionary (non-recursive)."""
        mapper = inspect(self.__class__)
        return {column.key: getattr(self, column.key) for column in mapper.column_attrs}

    def get_disassembler(self) -> Iterator["Base"]:
        """Yields an Iterator that recursively disassembles this entity into itself + its constituent ORM objects.
        Will simply yield self if object contains no other entities.

        :return: An Iterator yielding this entity + its constituent ORM objects
        """
        yield self

    def disassemble(self) -> dict[str, "Base"]:
        """Returns a dict containing this entity + all of its constituent ORM objects, keyed by type.
        If there are no constituent ORM objects, dict will just contain a single entry referring to this entity.

        Example:
        >>> sequence_reference = orm.SequenceReference(
            id="SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO",
            # etc...
        )
        >>> location = orm.Location(
            id="ga4gh:SL.U8b3eMCw6QjGA9cnDx_KYxqbol0UrEKx",
            sequence_reference_id=sequence_reference.id,
            sequence_reference=sequence_reference
            # etc...
        )
        >>> allele = orm.Allele(
            id="ga4gh:VA.uR23Z7AAFaLHhPUymUEYNG4o2CCE560T",
            location_id=location.id,
            location=location
            # etc...
        )
        >>> disassembled_allele = allele.disassemble()
        >>> print(disassembled_allele)
        {'Allele': <anyvar.storage.orm.Allele object at 0x108dfa780>, 'Location': <anyvar.storage.orm.Location object at 0x101416db0>, 'SequenceReference': <anyvar.storage.orm.SequenceReference object at 0x100af5250>}

        """
        objects: dict[str, Base] = {}
        for entity in self.get_disassembler():
            entity_type: str = entity.__class__.__name__
            objects[entity_type] = entity  # type: ignore (all children of orm.Base have an `id` property)

        return objects


class VrsObject(Base):
    """AnyVar ORM model for vrs_objects table."""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    vrs_object: Mapped[dict] = mapped_column(
        JSON()
        .with_variant(JSONB, "postgresql")
        .with_variant(SnowflakeVARIANT, "snowflake")
    )


class SequenceReference(Base):
    """AnyVar ORM model for SequenceReferences"""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    molecule_type: Mapped[MoleculeType | None] = mapped_column(
        Enum(
            MoleculeType,
            name="molecule_type",
            native_enum=True,
            values_callable=lambda mt_enum: [mt.value for mt in mt_enum],
            validate_strings=True,
        )
    )


class Location(Base):
    """AnyVar ORM model for Locations"""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[str] = mapped_column(String)
    sequence_reference_id: Mapped[str] = mapped_column(
        String, ForeignKey(SequenceReference.id)
    )
    sequence_reference: Mapped[SequenceReference] = relationship()
    start: Mapped[int | None] = mapped_column(name="start_pos")
    end: Mapped[int | None] = mapped_column(name="end_pos")
    start_outer: Mapped[int | None]
    start_inner: Mapped[int | None]
    end_outer: Mapped[int | None]
    end_inner: Mapped[int | None]

    def get_disassembler(self) -> Iterator[Base]:
        """Recursively disassemble to yield self + constituent `SequenceReference` object"""
        yield self
        yield self.sequence_reference


class Allele(Base):
    """AnyVar ORM model for Alleles"""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[str] = mapped_column(String)
    location_id: Mapped[str] = mapped_column(String, ForeignKey(Location.id))
    location: Mapped[Location] = relationship()
    state: Mapped[dict] = mapped_column(
        JSON()
        .with_variant(JSONB, "postgresql")
        .with_variant(SnowflakeVARIANT, "snowflake")
    )

    def get_disassembler(self) -> Iterator[Base]:
        """Recursively disassemble to yield self + constituent `Location` and `SequenceReference` objects"""
        yield self
        yield from self.location.get_disassembler()


class Annotation(Base):
    """AnyVar ORM model for annotations table."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(String)
    annotation_type: Mapped[str] = mapped_column(String)
    annotation_value: Mapped[dict] = mapped_column(
        JSON()
        .with_variant(JSONB, "postgresql")
        .with_variant(SnowflakeVARIANT, "snowflake")
    )

    # https://docs.sqlalchemy.org/en/20/core/constraints.html#indexes
    @declared_attr
    @classmethod
    def __table_args__(cls):  # noqa: ANN206
        uri = os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme == "snowflake":
            return ()
        return (
            Index(
                "idx_annotations_object_id_annotation_type",
                "object_id",
                "annotation_type",
            ),
        )


mapping_type_enum = Enum(
    VariationMappingType,
    name="mapping_type",
    native_enum=True,
    metadata=Base.metadata,
    create_type=True,
    validate_strings=True,
)


class VariationMapping(Base):
    """AnyVar ORM model for variation-to-variation mapping"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String)
    dest_id: Mapped[str] = mapped_column(String)
    mapping_type: Mapped[str] = mapped_column(mapping_type_enum)

    @declared_attr
    @classmethod
    def __table_args__(cls):  # noqa: ANN206
        uri = os.environ.get("ANYVAR_STORAGE_URI", DEFAULT_STORAGE_URI)
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme == "snowflake":
            return (UniqueConstraint("source_id", "dest_id", "mapping_type"),)
        return (
            Index("idx_mappings_source_id", "source_id"),
            Index("idx_mappings_dest_id", "dest_id"),
            Index("idx_mappings_source_id_type", "source_id", "mapping_type"),
            UniqueConstraint("source_id", "dest_id", "mapping_type"),
        )


def create_tables(db_url: str) -> None:
    """Create all tables in the database.

    :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
    """
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def session_factory(db_url: str) -> sessionmaker:
    """Create a SQLAlchemy session factory.

    Returns a sessionmaker factory that should be used to create sessions.
    Follows SQLAlchemy 2.0 recommended semantics where the session lifecycle
    is managed externally using context managers.

    Example usage:

    >>> sf = session_factory(db_url)
    >>> with sf() as session:
    >>>     with session.begin(): # Perform database operations
    >>>         session.add(some_object)
    >>>         session.execute(some_query)
    >>> # Transaction from session.begin() automatically commits if no exceptions occur
    >>> # Session automatically closes

    See: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-a-sessionmaker

    :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
    :return: SQLAlchemy sessionmaker factory
    """
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)
