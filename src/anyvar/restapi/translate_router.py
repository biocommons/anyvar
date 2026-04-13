"""Provide API routes relating to translate operations"""

from fastapi import APIRouter, Request

translate_router = APIRouter()


@translate_router.get(
    "/translate_to",
    response_model_exclude_none=True,
    operation_id="translateTo",
    summary="Translate the specified VRS object to other identifiers",
    description="Return the a list of variant identifiers that are represented by the specified VRS object",
)
def translate_to(
    request: Request,
) -> None:
    raise NotImplementedError


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
