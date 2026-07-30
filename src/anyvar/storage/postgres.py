"""Provide PostgreSQL-based storage implementation."""

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import JsonValue
from sqlalchemy import (
    ColumnElement,
    Engine,
    Index,
    Inspector,
    delete,
    func,
    inspect,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from anyvar.storage import orm
from anyvar.storage.alembic_config import configure_alembic
from anyvar.storage.sqlalchemy import SqlAlchemyStorage


class PostgresObjectStore(SqlAlchemyStorage):
    """PostgreSQL storage backend using dedicated ORM tables."""

    def __init__(self, db_url: str, *args, **kwargs) -> None:
        """Initialize PostgreSQL storage.

        :param db_url: Database connection URL (e.g., postgresql://user:pass@host:port/db)
        """
        super().__init__(db_url=db_url)
        self._create_indices(self.engine)

    def _create_tables(self) -> None:
        """Initialize database tables"""
        inspector: Inspector = inspect(subject=self.engine)
        tables: set[str] = set(inspector.get_table_names())
        anyvar_tables: set[str] = set(orm.Base.metadata.tables)

        # If the DB is empty, create all the required tables
        if not tables & anyvar_tables:
            repo_root: Path = Path(__file__).resolve().parents[3]
            config: Config = Config(file_=str(repo_root / "alembic.ini"))
            configure_alembic(config, db_url_override=self.db_url)
            command.upgrade(config=config, revision="head")

    def _create_indices(self, engine: Engine) -> None:
        """Create postgres-specific indices"""
        indices = [
            Index(
                "ix_location_ref_overlap",
                orm.Location.sequence_reference_id,
                func.int8range(
                    orm.Location.start,
                    orm.Location.end,
                    "[]",
                ),
                postgresql_using="gist",
            ),
            Index(
                "idx_extensions_object_id_name",
                orm.Extension.object_id,
                orm.Extension.name,
            ),
            Index(
                "idx_mappings_dest_id",
                orm.VariationMapping.dest_id,
            ),
        ]

        for idx in indices:
            idx.create(bind=engine, checkfirst=True)

    def close(self) -> None:
        """Close the storage backend."""

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.
        NOTE: This is a no-op for synchronous storage backends.
        """

    def _insert_ignore_conflict(
        self, session: Session, orm_model: type[orm.Base], values: list[dict]
    ) -> None:
        """Perform an insert of the given values, ignoring ID conflicts

        Should be implemented using specific engines/dialects of subclasses
        """
        stmt = insert(orm_model).on_conflict_do_nothing()
        session.execute(stmt, values)

    def _overlaps_interval_predicate(
        self,
        start: int,
        stop: int,
    ) -> ColumnElement[bool]:
        """Return a PostgreSQL range-overlap predicate.

        Uses PostgreSQL's native range types and overlap operator to enable
        efficient interval searches via a GiST index.
        """
        return func.int8range(
            orm.Location.start,
            orm.Location.end,
            "[]",
        ).op("&&")(func.int8range(start, stop, "[]"))

    def delete_extensions(
        self,
        object_id: str,
        name: str | None = None,
        value: JsonValue | None = None,
    ) -> int:
        """Delete extension(s) for an object

        Supports gradual specificity -- either delete all extensions,
        or delete all extensions under a given key/name, or delete all extensions
        with a given name AND value.

        If no extension matching given args exists, do nothing.

        :param object_id: The object ID
        :param name: Optional extension key/name to delete
        :param value: Optional extension value to delete. Ignored if ``name`` is not provided
        :return: Number of deleted rows
        """
        stmt = delete(orm.Extension).where(orm.Extension.object_id == object_id)
        if name:
            stmt = stmt.where(orm.Extension.name == name)
            if value:
                stmt = stmt.where(orm.Extension.value == json.dumps(value))
        with self.session_factory() as session, session.begin():
            result = session.execute(stmt)
            return result.rowcount or 0
