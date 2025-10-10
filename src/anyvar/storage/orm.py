"""SQLAlchemy ORM models for AnyVar database schema."""

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum  # noqa: N811
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from anyvar.utils.types import VariationMappingType


class Base(DeclarativeBase):
    """Base class for all AnyVar ORM models."""

    def to_dict(self) -> dict:
        """Convert the model fields to a dictionary (non-recursive)."""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }


class VrsObject(Base):
    """AnyVar ORM model for vrs_objects table."""

    __tablename__ = "vrs_objects"

    vrs_id: Mapped[str] = mapped_column(String, primary_key=True)
    vrs_object: Mapped[dict] = mapped_column(JSONB)


class Allele(Base):
    """AnyVar ORM model for Alleles"""

    __tablename__ = "alleles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[str] = mapped_column(String)
    location_id: Mapped[str] = mapped_column(String, ForeignKey("locations.id"))
    location: Mapped["Location"] = relationship()
    state: Mapped[dict] = mapped_column(JSONB)


class Location(Base):
    """AnyVar ORM model for Locations"""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[str] = mapped_column(String)
    sequence_reference_id: Mapped[str] = mapped_column(
        String, ForeignKey("sequence_references.id")
    )
    sequence_reference: Mapped["SequenceReference"] = relationship()
    start: Mapped[int | None]
    end: Mapped[int | None]
    start_outer: Mapped[int | None]
    start_inner: Mapped[int | None]
    end_outer: Mapped[int | None]
    end_inner: Mapped[int | None]


class SequenceReference(Base):
    """AnyVar ORM model for SequenceReferences"""

    __tablename__ = "sequence_references"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    molecule_type: Mapped[str | None]


class Annotation(Base):
    """AnyVar ORM model for annotations table."""

    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(String)
    annotation_type: Mapped[str] = mapped_column(String)
    annotation_value: Mapped[JSONB] = mapped_column(JSONB)

    # https://docs.sqlalchemy.org/en/20/core/constraints.html#indexes
    # TODO is this needed because of the primary key?
    __table_args__ = (
        Index(
            "idx_annotations_object_id_annotation_type",
            "object_id",
            "annotation_type",
        ),
    )


mapping_type_enum = PgEnum(
    VariationMappingType,
    name="mapping_type",
    metadata=Base.metadata,
    create_type=True,
    validate_strings=True,
)


class VariationMapping(Base):
    """AnyVar ORM model for variation-to-variation mapping"""

    __tablename__ = "variation_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("alleles.id", ondelete="cascade")
    )
    dest_id: Mapped[str] = mapped_column(
        String, ForeignKey("alleles.id", ondelete="cascade")
    )
    mapping_type: Mapped[str] = mapped_column(mapping_type_enum)

    __table_args__ = (
        Index("idx_mappings_source_id", "source_id"),
        Index("idx_mappings_dest_id", "dest_id"),
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
        sf = session_factory(db_url)
        with sf() as session:
            with session.begin():
                # Perform database operations
                session.add(some_object)
                session.execute(some_query)
            # Transaction from session.begin() automatically commits if no exceptions occur
        # Session automatically closes

    See: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#using-a-sessionmaker

    :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
    :return: SQLAlchemy sessionmaker factory
    """
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)
