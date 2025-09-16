"""SQLAlchemy ORM models for AnyVar database schema."""

from sqlalchemy import ForeignKey, Index, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all AnyVar ORM models."""


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
    start: Mapped[int]
    end: Mapped[int]
    start_outer: Mapped[int]
    start_inner: Mapped[int]
    end_outer: Mapped[int]
    end_inner: Mapped[int]


class SequenceReference(Base):
    """AnyVar ORM model for SequenceReferences"""

    __tablename__ = "sequence_references"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    refseq_id: Mapped[str]
    molecule_type: Mapped[str]


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
