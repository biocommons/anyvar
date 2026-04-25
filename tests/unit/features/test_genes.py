from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from asyncpg.pool import PoolConnectionProxy
from cool_seq_tool.sources import UtaDatabase

from anyvar.features.genes import get_gene_coords


@pytest_asyncio.fixture
async def uta_db() -> AsyncGenerator[UtaDatabase, None]:
    db = await UtaDatabase.create()
    if not db._connection_pool:  # noqa: SLF001
        await db.create_pool()
    try:
        yield db
    finally:
        if db._connection_pool:  # noqa: SLF001
            await db._connection_pool.close()  # noqa: SLF001


@pytest_asyncio.fixture
async def uta_conn(uta_db: UtaDatabase) -> AsyncGenerator[PoolConnectionProxy, None]:
    async with uta_db._connection_pool.acquire() as conn:  # noqa: SLF001
        yield conn


@pytest.mark.asyncio
async def test_get_gene_coords(uta_conn: PoolConnectionProxy):
    result = await get_gene_coords(uta_conn, "brca1")

    assert result is not None
    assert result.hgnc_symbol == "BRCA1"
    assert result.accession == "NC_000017.11"
    assert result.start_i == 43044294
    assert result.end_i == 43170327


@pytest.mark.asyncio
async def test_get_gene_coords_none(uta_conn: PoolConnectionProxy):
    result = await get_gene_coords(uta_conn, "fake symbol")

    assert result is None
