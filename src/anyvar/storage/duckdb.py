"""Provide DuckDB-based storage implementation.

Most live, persistent variant registration and search services will want to employ the
PostgreSQL storage option for its performance, particularly for concurrent writes and
large-scale datasets. However, DuckDB may be better in certain use cases:

* The DuckDB file-based option can be used to assemble a cohort or a dataset into a static
  file, like an index, that can be easily passed along to other uses for later lookup This
  option can also function as a simple registration service in cases where a
  separately-provisioned PostgreSQL server is logistically prohibitive, although this is not ideal.
* The DuckDB in-memory option can be used for simple testing and demonstration purposes,
  and also works as a less-performant "stateless" translation service. Note that the
  database is wiped and recreated every time a FastAPI service restarts.

.. code-block:: pycon

   >>> from anyvar.storage.duckdb import DuckDbObjectStore
   >>> file_based = DuckDbObjectStore("duckdb:///path/to/my/variants.duckdb")
   >>> in_memory = DuckDbObjectStore("duckdb:///:memory:")

Under the hood, this should behave like a simpler but less-performant equivalent of
Postgres. Our implementation is designed to employ common SqlAlchemy resources so there
should be minimal specific maintenance required here.
"""

import json

from pydantic import JsonValue
from sqlalchemy import ColumnElement, create_engine, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from anyvar.storage import orm
from anyvar.storage.sqlalchemy import SqlAlchemyStorage


class DuckDbObjectStore(SqlAlchemyStorage):
    """DuckDB-backed AnyVar object store."""

    def __init__(self, db_uri: str, *args, **kwargs) -> None:
        """Initialize PostgreSQL storage.

        :param db_uri: DuckDB connection URI. See above for options.
        """
        self.db_url = db_uri
        self.engine = create_engine(self.db_url, poolclass=StaticPool)
        orm.Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.batch_size = kwargs.get("batch_size", 1000)

    def close(self) -> None:
        """Close the storage backend."""
        self.engine.dispose()

    def wait_for_writes(self) -> None:
        """Wait for all background writes to complete.
        NOTE: This is a no-op for synchronous storage backends.
        """

    def wipe_db(self) -> None:
        """Wipe all data from the storage backend."""
        # Need a bunch of redundant sessions for DuckDB reasons that I don't totally get
        with self.session_factory() as session, session.begin():
            session.execute(delete(orm.VariationMapping))
        with self.session_factory() as session, session.begin():
            session.execute(delete(orm.Allele))
        with self.session_factory() as session, session.begin():
            session.execute(delete(orm.Location))
        with self.session_factory() as session, session.begin():
            session.execute(delete(orm.SequenceReference))

            # Delete other tables
            session.execute(delete(orm.VrsObject))
            session.execute(delete(orm.Extension))

    def _insert_ignore_conflict(
        self, session: Session, orm_model: type[orm.Base], values: list[dict]
    ) -> None:
        """Perform an insert of the given values, ignoring ID conflicts

        Should be implemented using specific engines/dialects of subclasses
        """
        stmt = insert(orm_model).on_conflict_do_nothing()
        session.execute(stmt, values)

    def _extension_delete_predicates(
        self,
        object_id: str,
        name: str | None = None,
        value: JsonValue | None = None,
    ) -> list[ColumnElement[bool]]:
        predicates = [orm.Extension.object_id == object_id]

        if name is not None:
            predicates.append(orm.Extension.name == name)

            if value is not None:
                predicates.append(orm.Extension.value == json.dumps(value))

        return predicates

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

        Note that this gets a little slow in DuckDB, because we have to manually query
        the # of matching rows first.

        :param object_id: The object ID
        :param name: Optional extension key/name to delete
        :param value: Optional extension value to delete. Ignored if ``name`` is not provided
        :return: Number of deleted rows
        """
        predicates = self._extension_delete_predicates(object_id, name, value)

        count_stmt = select(func.count()).select_from(orm.Extension).where(*predicates)
        delete_stmt = delete(orm.Extension).where(*predicates)

        with self.session_factory() as session, session.begin():
            deleted_count = session.scalar(count_stmt) or 0
            session.execute(delete_stmt)
            return deleted_count
