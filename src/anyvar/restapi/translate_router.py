"""Provide API routes relating to translate operations"""

from http import HTTPStatus
from fastapi import APIRouter, HTTPException, Request
from fastapi.params import Path
from ga4gh.vrs.extras.translator import AlleleTranslator
from ga4gh.vrs.models import Allele
from typing import Annotated
from pydantic import StrictStr

from anyvar.anyvar import AnyVar
from anyvar.core.objects import VrsObject
from anyvar.restapi.schema import TranslateToResponse, TranslateFromResponse
translate_router = APIRouter()


@translate_router.post(
    "/translate_to",
    response_model_exclude_none=True,
    operation_id="translateTo",
    summary="Translate the specified VRS object to other identifiers",
    description="Return a dictionary of variant identifiers keyed by identifier type (i.e. hgvs, spdi) that are represented by the specified VRS Allele object",
)
def translate_to(
    request: Request,
    vrs_object: Allele,
) -> TranslateToResponse:
    av: AnyVar = request.app.state.anyvar
    translator: AlleleTranslator = av.translator.allele_tlr
    try:
        identifiers = {
            fmt: translator.translate_to(vrs_object, fmt) for fmt in translator.to_translators
        }
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return TranslateToResponse(identifiers=identifiers)


@translate_router.get(
    "/translate_from/{format}/{identifier}",
    response_model_exclude_none=True,
    operation_id="translateFrom",
    summary="Translate the specified identifier to a VRS Object",
    description="Return the full VRS Object for the given variant identifier",
)
def translate_from(
    request: Request,
    format: Annotated[StrictStr, Path(..., description="Format for identifier (i.e. hgvs, gnomad)")],
    identifier: Annotated[StrictStr, Path(..., description="Identifier")],
) -> TranslateFromResponse:
    av: AnyVar = request.app.state.anyvar
    translator: AlleleTranslator = av.translator.allele_tlr
    try:
        vrs_object = translator.translate_from(identifier, format)
    except (ValueError, NotImplementedError) as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return TranslateFromResponse(object=vrs_object)
