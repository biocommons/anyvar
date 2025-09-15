"""SQLAlchemy ORM models for AnyVar database schema."""

from sqlalchemy import ForeignKey, Index, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class VrsObject(Base):
    """ORM model for vrs_objects table."""

    __tablename__ = "vrs_objects"

    vrs_id: Mapped[str] = mapped_column(String, primary_key=True)
    vrs_object: Mapped[dict] = mapped_column(JSONB)


class Annotation(Base):
    """ORM model for annotations table."""

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
