"""Provide API routes relating to translate operations"""

from fastapi import APIRouter, Request
from ga4gh.vrs.extras.translator import AlleleTranslator
from ga4gh.vrs.models import Allele

from anyvar.anyvar import AnyVar
from anyvar.restapi.schema import TranslateToResponse
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
    identifiers = {
        fmt: translator.translate_to(vrs_object, fmt) for fmt in translator.to_translators
    }
    return TranslateToResponse(identifiers=identifiers)


@translate_router.get(
    "/translate_from",
    response_model_exclude_none=True,
    operation_id="translateFrom",
    summary="Translate the specified identifier to a VRS Object",
    description="Return the full VRS Object for any given variant identifier",
)
def translate_from(
    request: Request,
) -> None:
    raise NotImplementedError
