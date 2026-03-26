"""Provide API routes relating to search operations"""

from http import HTTPStatus
from typing import Annotated

from asyncpg.pool import PoolConnectionProxy
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from anyvar.anyvar import AnyVar
from anyvar.features.genes import get_gene_coords
from anyvar.restapi.dependencies import (
    PaginationParams,
    get_pagination_params,
    get_uta_conn,
)
from anyvar.restapi.schema import GeneSearchResponse, SearchResponse

search_router = APIRouter()


@search_router.get(
    "/search",
    response_model_exclude_none=True,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Return all variants with start and end positions that fall within the provided start and end arguments (inclusive).",
)
def search_variations(
    request: Request,
    accession: Annotated[
        str,
        Query(
            ...,
            description='Sequence accession identifier (for example: `"ga4gh:SQ.8_liLu1aycC0tPQPFmUaGXJLDs5SbPZ5"`)',
            examples=["ga4gh:SQ.8_liLu1aycC0tPQPFmUaGXJLDs5SbPZ5"],
        ),
    ],
    start: Annotated[
        int,
        Query(..., description="Start position for genomic region", examples=[2781631]),
    ],
    end: Annotated[
        int,
        Query(..., description="End position for genomic region", examples=[2781758]),
    ],
    pagination_params: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> SearchResponse:
    """Perform genomic coordinate-based search over all registered variations."""
    av: AnyVar = request.app.state.anyvar
    try:
        if accession.startswith("ga4gh:"):
            ga4gh_id = accession
        else:
            ga4gh_id = av.translator.get_sequence_id(accession)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Unable to dereference provided accession ID",
        ) from e

    if not ga4gh_id:
        return SearchResponse(variations=[], next_cursor=None)

    try:
        refget_accession = ga4gh_id.split("ga4gh:")[-1]
        page = av.object_store.search_alleles(
            refget_accession,
            start,
            end,
            page_size=pagination_params.page_size,
            cursor=pagination_params.cursor,
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Search not implemented for current storage backend",
        ) from e

    return SearchResponse(variations=page.items, next_cursor=page.next_cursor)


@search_router.get(
    "/search_by_gene",
    response_model_exclude_none=True,
    operation_id="searchVariationsByGene",
    summary="Search for registered genomic variations by gene context",
    description="Return all genomic variants with start and end positions that fall within the contours of the gene",
)
async def search_variations_by_gene(
    request: Request,
    gene: Annotated[
        str, Query(..., description="HGNC-approved gene symbol", examples=["BRAF"])
    ],
    pagination_params: Annotated[PaginationParams, Depends(get_pagination_params)],
    uta_conn: Annotated[PoolConnectionProxy, Depends(get_uta_conn)],
) -> GeneSearchResponse:
    """Retrieve all genomic variants located within the bounds of a gene"""
    gene_result = await get_gene_coords(uta_conn, gene)
    if not gene_result:
        return GeneSearchResponse(gene_name=gene, variations=[], next_cursor=None)

    av: AnyVar = request.app.state.anyvar
    try:
        ga4gh_acc_id = av.translator.get_sequence_id(f"refseq:{gene_result.acc}")
        refget_accession = ga4gh_acc_id.split("ga4gh:")[-1]
    except KeyError:
        return GeneSearchResponse(gene_name=gene, variations=[], next_cursor=None)
    page = av.object_store.search_alleles(
        refget_accession,
        gene_result.start_i,
        gene_result.end_i,
        page_size=pagination_params.page_size,
        cursor=pagination_params.cursor,
    )
    return GeneSearchResponse(
        variations=page.items,
        next_cursor=page.next_cursor,
        gene_name=gene_result.hgnc_symbol,
    )
