"""Dependencies for API routes"""

from collections.abc import AsyncGenerator
from typing import NamedTuple

from asyncpg.pool import PoolConnectionProxy
from cool_seq_tool.sources import UtaDatabase
from fastapi import Query, Request


class PaginationParams(NamedTuple):
    """Contain page size/cursor for pagination"""

    page_size: int
    cursor: str | None


def get_pagination_params(
    page_size: int = Query(1000, ge=1, le=10000),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
) -> PaginationParams:
    """FastAPI dependency for reusable pagination args

    :param page_size: size of page to fetch
    :param cursor: cursor to key page from
    :return: args to pass to search functions
    """
    return PaginationParams(page_size=page_size, cursor=cursor)


async def get_uta_conn(request: Request) -> AsyncGenerator[PoolConnectionProxy, None]:
    """Provide connection context for UTA-based lookups

    :param request: FastAPI request
    :return: generator yielding a connection from a connection pool
    """
    uta: UtaDatabase = request.app.state.uta
    async with uta._connection_pool.acquire() as conn:  # noqa: SLF001
        await conn.execute("set SEARCH_PATH to uta_20241220;")
        yield conn
