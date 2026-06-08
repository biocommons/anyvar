"""Provide API routes relating to stateless translation operations"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.params import Path

from anyvar.anyvar import AnyVar
from anyvar.restapi.schema import (
    TranslateToRequest,
    TranslateToResponse,
    TranslationResult,
)
from anyvar.restapi.utils import translate_variation
from anyvar.translate.base import TranslationError, Translator

translate_router = APIRouter(prefix="/translate")
TRANSLATE_TO_FMTS = ["hgvs", "spdi"]


@translate_router.post(
    "/vrs_to_identifiers",
    response_model_exclude_none=True,
    operation_id="translateVrsToIdentifiers",
    summary="Translate a VRS Allele to one or more identifiers in the requested format.",
    description="Translate the specified VRS Allele to equivalent identifiers in other formats (for example, HGVS or SPDI). This operation is stateless and does not require the variation to be registered in AnyVar.",
)
def translate_to(
    request: Request,
    translate_request: TranslateToRequest,
) -> TranslateToResponse:
    """Translate a VRS Allele to one or more identifiers in the requested format without registration."""
    av: AnyVar = request.app.state.anyvar
    translator = av.translator

    try:
        identifiers = {
            fmt: translator.translate_allele_to_format(
                allele=translate_request.allele,
                fmt=fmt,
                namespace=translate_request.namespace,
                ref_seq_limit=translate_request.ref_seq_limit,
            )
            for fmt in TRANSLATE_TO_FMTS
        }
    except TranslationError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    return TranslateToResponse(identifiers=identifiers)


@translate_router.get(
    "/identifier_to_vrs/{identifier}",
    response_model_exclude_none=True,
    operation_id="translateIdentifierToVrs",
    summary="Translate the specified identifier to a VRS Allele",
    description="Translate the specified identifier to its corresponding VRS Allele. This operation is stateless and does not require the variation to be registered in AnyVar.",
)
def translate_from(
    request: Request,
    identifier: Annotated[str, Path(..., description="Identifier")],
    fmt: Annotated[str | None, Query(description="")] = None,
    assembly_name: Annotated[
        str,
        Query(
            description="Assembly used for `identifier`. Only used for gnomad `fmt`."
        ),
    ] = "GRCh38",
    require_validation: Annotated[
        bool,
        Query(
            description="Whether validation checks must pass in order to return a VRS Allele."
        ),
    ] = True,
    rle_seq_limit: Annotated[
        int | None,
        Query(
            description="If Reference Length Expression is set as the new state after normalization, this sets the limit for the length of the `sequence`. To exclude `sequence` from the response, set to 0. For no limit, set to `None`."
        ),
    ] = 50,
) -> TranslationResult:
    """Translate the specified identifier to a VRS Allele"""
    av: AnyVar = request.app.state.anyvar
    translator: Translator = av.translator
    translation_result = translate_variation(
        translator,
        identifier,
        fmt=fmt,
        assembly_name=assembly_name,
        require_validation=require_validation,
        rle_seq_limit=rle_seq_limit,
    )
    if translation_result.error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=translation_result.error,
        )

    return translation_result
