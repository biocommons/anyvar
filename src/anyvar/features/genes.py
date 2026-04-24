"""Provide tools for gene-based searches.

Use in contexts like gene-based searches; functions here provide coordinates, which can
be fed to core AnyVar tables for variant retrieval.
"""

from typing import NamedTuple

from asyncpg.pool import PoolConnectionProxy


class GeneCoords(NamedTuple):
    """Data class for gene coords lookup result"""

    hgnc_symbol: str
    accession: str
    start_i: int
    end_i: int


async def get_gene_coords(
    uta_conn: PoolConnectionProxy, gene: str
) -> GeneCoords | None:
    """Fetch gene location information for a given HGNC symbol

    Fetches the highest match for a set of coordinates on an `NC_` accession (ie gets the
    newest accession version if available). Otherwise, returns nothing.

    :param uta_conn: postgres connection from asyncpg connection pool. Should already
        have `search_path` set to proper schema
    :param gene: HGNC gene symbol (case-neutral)
    :return: gene coordinate description if lookup succeeds
    """
    result = await uta_conn.fetchrow(
        """SELECT
t.hgnc AS hgnc_symbol,
tea.alt_ac AS accession,
MIN(tea.alt_start_i) AS start_i,
MAX(tea.alt_end_i) AS end_i
FROM uta_20241220.tx_exon_aln_mv tea
JOIN uta_20241220.transcript t ON tea.tx_ac = t.ac
WHERE t.hgnc = $1
AND tea.alt_ac LIKE 'NC_000%'
GROUP BY t.hgnc, tea.alt_ac
ORDER BY tea.alt_ac DESC;
""",
        gene.upper(),
    )
    if not result:
        return None
    return GeneCoords(**result)
