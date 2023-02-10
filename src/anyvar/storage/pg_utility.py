import contextlib
import inspect
import logging
import os
import weakref

import hgvs
import psycopg2
from hgvs.dataproviders.uta import _parse_url

_logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(self,
                 db_url,
                 pooling=False,
                 application_name=None,
                 mode=None,
                 cache=None):
        url = _parse_url(db_url)
        #if url.schema is None:
         #   raise Exception("No schema name provided in {url}".format(url=url))
        if url.scheme != "postgresql":
            raise Exception("Only Postgres databases supported for now")
        self.application_name = application_name
        self.pooling = pooling
        self._conn = None
        self.url = url
        # If we're using connection pooling, track the set of DB
        # connections we've seen; on first use we set the schema
        # search path. Use weak references to avoid keeping connection
        # objects alive unnecessarily.
        self._conns_seen = weakref.WeakSet()

    def __del__(self):
        self.close()

    def close(self):
        if self.pooling:
            self._pool.closeall()
        else:
            if self._conn is not None:
                self._conn.close()

    def _connect(self):
        if self.application_name is None:
            st = inspect.stack()
            self.application_name = os.path.basename(st[-1][1])
        conn_args = dict(
            host=self.url.hostname,
            port=self.url.port,
            database=self.url.database,
            user=self.url.username,
            password=self.url.password,
            application_name=self.application_name + "/" + hgvs.__version__,
        )
        if self.pooling:
            _logger.info("Using UTA ThreadedConnectionPool")
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                hgvs.global_config.uta.pool_min,
                hgvs.global_config.uta.pool_max, **conn_args)
        else:
            self._conn = psycopg2.connect(**conn_args)
            self._conn.autocommit = True
            with self._get_cursor() as cur:
                self._set_search_path(cur)

        self.ensure_schema_exists()

    def _create_schema(self):
        create_sql = (
            "CREATE TABLE vrs_objects "
            "(id BIGSERIAL primary key, vrs_id text, vrs_object jsonb);"
        )
        self._insert_one(create_sql)

    def ensure_schema_exists(self):
        # N.B. On AWS RDS, information_schema.schemata always returns zero rows
        r = self._fetchone(
            "select exists("
            "SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')"
        )
        if r[0]:
            return
        self._create_schema()

    def _fetchone(self, sql, *args):
        with self._get_cursor() as cur:
            cur.execute(sql, *args)
            return cur.fetchone()

    def _fetchall(self, sql, *args):
        with self._get_cursor() as cur:
            cur.execute(sql, *args)
            return cur.fetchall()

    def _insert_one(self, sql, *args):
        with self._get_cursor() as cur:
            cur.execute(sql, *args)

    @contextlib.contextmanager
    def _get_cursor(self, n_retries=1):
        """Returns a context manager for obtained from a single or pooled
        connection, and sets the PostgreSQL search_path to the schema
        specified in the connection URL.
        Although *connections* are threadsafe, *cursors* are bound to
        connections and are *not* threadsafe. Do not share cursors
        across threads.
        Use this funciton like this::
            with hdp._get_cursor() as cur:
                # your code
        Do not call this function outside a contextmanager.
        """

        n_tries_rem = n_retries + 1
        while n_tries_rem > 0:
            try:

                conn = self._pool.getconn() if self.pooling else self._conn

                # autocommit=True obviates closing explicitly
                conn.autocommit = True

                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                if self.pooling:
                    # this might be a new connection, in which case we
                    # need to set the search path
                    if conn not in self._conns_seen:
                        self._set_search_path(cur)
                        self._conns_seen.add(conn)

                yield cur

                # contextmanager executes these when context exits
                cur.close()
                if self.pooling:
                    self._pool.putconn(conn)

                break

            except psycopg2.OperationalError:

                _logger.warning(
                    "Lost connection to {url}; attempting reconnect".format(
                        url=self.url))
                if self.pooling:
                    self._pool.closeall()
                self._connect()
                _logger.warning("Reconnected to {url}".format(url=self.url))

            n_tries_rem -= 1

        else:

            # N.B. Probably never reached
            raise RuntimeError(
                "Permanently lost connection to {url} ({n} retries)".format(
                    url=self.url, n=n_retries))

    def _set_search_path(self, cur):
        cur.execute(
            "set search_path = {self.url.schema},public;".format(self=self))
