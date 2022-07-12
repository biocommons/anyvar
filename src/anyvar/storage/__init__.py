import logging
import os
from urllib.parse import urlparse


_logger = logging.getLogger(__name__)

default_storage_uri = "memory:"


def create_storage(uri=None):
    """factory to create storage based on `uri`, the ANYVAR_STORAGE_URI
    environment value, or in-memory storage.

    The URI format is one of the following:

    * in-memory dictionary:
    `memory:`
    Remaining URI elements ignored, if provided

    * Python shelf (dbm) persistence

    `file:///full/path/to/filename.db`
    `path/to/filename`

    The `file` scheme permits only full paths.  When scheme is not
    provided, the path may be absolute or relative.

    * Redis URI
    `redis://[[username]:[password]]@localhost:6379/0`
    `rediss://[[username]:[password]]@localhost:6379/0`
    `unix://[[username]:[password]]@/path/to/socket.sock?db=0`

    The URIs are passed as-is to `redis.Redis.from_url()`

    """

    uri = uri or os.environ.get("ANYVAR_STORAGE_URI", default_storage_uri)

    parsed_uri = urlparse(uri)

    if parsed_uri.scheme == "memory":
        _logger.warning("Using memory storage; stored data will be discarded when process exits")
        storage = dict()

    elif parsed_uri.scheme in ("", "file"):
        from .shelf import ShelfStorage
        storage = ShelfStorage(parsed_uri.path)

    elif parsed_uri.scheme == "redis":
        import redis
        from .redisobjectstore import RedisObjectStore
        storage = RedisObjectStore(redis.Redis.from_url(uri))

    elif parsed_uri.scheme == "postgres":
        from .postgres import PostgresObjectStore
        storage = PostgresObjectStore(uri)

    else:
        raise ValueError(f"URI scheme {parsed_uri.scheme} is not implemented")

    _logger.debug(f"create_storage: {uri} → {storage}")
    return storage
