"""SQLAlchemy ORM models for AnyVar database schema."""

import os
import re

from sqlalchemy import ForeignKey, Index, Integer, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.orm.decl_api import declared_attr


class Base(DeclarativeBase):
    """Base class for all AnyVar ORM models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805 (param name here should be 'cls', not 'self')
        # Default table name = class name, transformed from PascalCase into snake_case and pluralized.
        # NOTE: May need more robust pluralization in the future to support additional classes/tables.
        default_name: str = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower() + "s"

        # Environment variable name is the class name transformed into UPPER_SNAKE_CASE, pluralized, and prefixed by 'ANYVAR_' + suffixed with "_TABLE_NAME".
        # e.g., the environment variable to override the table name created by the "VrsObject" ORM class is `ANYVAR_VRS_OBJECTS_TABLE_NAME`
        environment_variable_name: str = f"ANYVAR_{default_name.upper()}_TABLE_NAME"

        return os.getenv(environment_variable_name) or default_name

    def to_dict(self) -> dict:
        """Convert the model fields to a dictionary (non-recursive)."""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }


class VrsObject(Base):
    """AnyVar ORM model for vrs_objects table."""

    vrs_id: Mapped[str] = mapped_column(String, primary_key=True)
    vrs_object: Mapped[dict] = mapped_column(JSONB)


class Allele(Base):
    """AnyVar ORM model for Alleles"""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[str] = mapped_column(String)
    location_id: Mapped[str] = mapped_column(String, ForeignKey("locations.id"))
    location: Mapped["Location"] = relationship()
    state: Mapped[dict] = mapped_column(JSONB)


class Location(Base):
    """AnyVar ORM model for Locations"""

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

    id: Mapped[str] = mapped_column(String, primary_key=True)
    molecule_type: Mapped[str | None]


class Annotation(Base):
    """AnyVar ORM model for annotations table."""

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
