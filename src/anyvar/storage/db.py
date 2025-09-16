"""SQLAlchemy ORM models for AnyVar database schema."""

from sqlalchemy import ForeignKey, Index, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


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
    location_id: Mapped[str] = mapped_column(String, ForeignKey("locations.id"))
    location: Mapped["Location"] = relationship()
    state: Mapped[dict] = mapped_column(JSONB)


class Location(Base):
    """AnyVar ORM model for Locations"""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
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
    refseq_id: Mapped[str | None]
    molecule_type: Mapped[str | None]


class Annotation(Base):
    """AnyVar ORM model for annotations table."""

    __tablename__ = "annotations"

    object_id: Mapped[str] = mapped_column(
        String, ForeignKey("vrs_objects.vrs_id"), primary_key=True
    )
    annotation_type: Mapped[str] = mapped_column(String, primary_key=True)
    annotation: Mapped[dict] = mapped_column(JSONB)

    # https://docs.sqlalchemy.org/en/20/core/constraints.html#indexes
    __table_args__ = (
        Index(
            "idx_annotations_object_id_annotation_type",
            "object_id",
            "annotation_type",
        ),
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
