"""Provide API routes relating to search operations"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from anyvar.anyvar import AnyVar
from anyvar.restapi.schema import SearchResponse

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

    alleles = []
    if ga4gh_id:
        try:
            refget_accession = ga4gh_id.split("ga4gh:")[-1]
            alleles = av.object_store.search_alleles(refget_accession, start, end)
        except NotImplementedError as e:
            raise HTTPException(
                status_code=HTTPStatus.NOT_IMPLEMENTED,
                detail="Search not implemented for current storage backend",
            ) from e

    return SearchResponse(variations=alleles)
