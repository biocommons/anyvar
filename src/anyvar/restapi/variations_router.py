"""Provide API routes relating to search operations"""

import logging
import os
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response, status
from fastapi.params import Path
from fastapi.responses import JSONResponse

import anyvar
from anyvar.anyvar import AnyVar
from anyvar.core import objects
from anyvar.mapping import liftover
from anyvar.restapi import has_async_imports
from anyvar.restapi.async_utils import (
    check_async_enabled,
    validate_run_id_available,
)
from anyvar.restapi.schema import (
    ErrorResponse,
    GetObjectResponse,
    RegisterVariationResponse,
    RunStatusResponse,
    SearchResponse,
    VariationRequest,
)
from anyvar.restapi.utils import get_vrs_object
from anyvar.storage.base import IncompleteVrsObjectError
from anyvar.translate.base import Translator
from anyvar.translate.register import (
    register_variations as _register_variations,
)
from anyvar.translate.register import (
    translate_variation as _translate_variation,
)

if has_async_imports:
    from celery.result import AsyncResult

    from anyvar.queueing import celery_worker
    from anyvar.restapi.async_utils import resolve_async_task_status

_logger = logging.getLogger(__name__)

variations_router = APIRouter()

VARIATION_EXAMPLE_PAYLOAD = {
    "definition": "NC_000007.13:g.36561662_36561663del",
    "input_type": "Allele",
    "copies": 0,
    "copy_change": "complete genomic loss",
    "assembly_name": None,
}


_variation_request_body = Body(
    description='Variation description, including (at minimum) a `definition` property. Can provide optional `input_type` if the expected output representation type is known, as well as an assembly_name (e.g.,"GRCh37" or "GRCh38"). If representing copy number, provide `copies` or `copy_change`.',
    examples=[VARIATION_EXAMPLE_PAYLOAD],
)


def _handle_translation_request(
    tlr: Translator, var_req: VariationRequest
) -> objects.SupportedVrsVariation:
    """Perform variant translation and convert known exceptions to appropriate HTTP responses

    :param tlr: Translator instance
    :param var_req: request object relayed to variation endpoint
    :return: VRS variation instance
    :raise HTTPException: return 422 response if
       * Variant definition cannot be translated
       * Reference base in gnomad/VCF-style expression fails to validate
       * translator returns not-implemented variation type
    """
    translation_result = _translate_variation(tlr, var_req)
    if translation_result.error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=translation_result.error,
        )

    return translation_result.variation  # type: ignore


@variations_router.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition  to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and ID is returned.",
)
def register_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference."""
    av: AnyVar = request.app.state.anyvar

    responses: list[RegisterVariationResponse] = _register_variations(av, [variation])
    return responses[0]


@variations_router.put(
    "/variations",
    response_model_exclude_none=True,
    summary="Bulk register alleles or copy number objects",
    description="Provide a list of variation definitions to be normalized and registered with AnyVar. The response contains one result per input, in the same order. Variations that fail translation are not registered and are returned with null `object` and `object_id` fields. Registration or liftover failure messages may also be included in the `messages` field.",
)
async def register_variations(
    request: Request,
    response: Response,
    variations: Annotated[
        list[VariationRequest], Body(description="List of variations to register")
    ],
    run_async: Annotated[
        bool,
        Query(
            description="If true, immediately return a '202 Accepted' response and run asynchronously",
        ),
    ] = False,
    run_id: Annotated[
        str | None,
        Query(
            description="When running asynchronously, use the specified value as the run id instead of generating a random uuid",
        ),
    ] = None,
) -> list[RegisterVariationResponse] | RunStatusResponse | ErrorResponse:
    """Register multiple variations based on provided descriptions or references."""
    if run_async:
        if not anyvar.anyvar.has_variations_queueing_enabled() or not has_async_imports:
            _logger.warning(
                "Async variation registration requested but not enabled (has_variations_queueing_enabled=%s, has_async_imports=%s)",
                anyvar.anyvar.has_variations_queueing_enabled(),
                has_async_imports,
                stack_info=True,
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ErrorResponse(
                error="Required modules and/or configurations for asynchronous variation registration are missing"
            )

        if run_id:
            error = validate_run_id_available(run_id, response)
            if error:
                return error

        # submit async job
        variation_requests_json = [v.model_dump(mode="json") for v in variations]
        task_result = celery_worker.register_variations.apply_async(
            kwargs={
                "variation_requests_json": variation_requests_json,
            },
            task_id=run_id,
        )
        _logger.info(
            "%s - async variation registration submitted for %s variations",
            task_result.id,
            len(variations),
        )

        # estimate retry-after based on ~100 variations/second
        _expected_variations_per_second = int(
            os.getenv("ANYVAR_EXPECTED_VARIATIONS_PER_SECOND", "100")
        )
        retry_after = max(
            1, round(len(variations) / _expected_variations_per_second, 0)
        )

        response.status_code = status.HTTP_202_ACCEPTED
        response.headers["Location"] = f"/variations/{task_result.id}"
        response.headers["Retry-After"] = str(int(retry_after))
        return RunStatusResponse(
            run_id=task_result.id,
            status="PENDING",
            status_message=f"Run submitted. Check status at /variations/{task_result.id}",
        )

    av: AnyVar = request.app.state.anyvar
    return _register_variations(av, variations)


@variations_router.get(
    "/variations/{run_id}",
    summary="Poll for status and/or result for asynchronous variation registration",
    description="Provide a valid run id to get the status and/or result of an asynchronous variation registration run",
    response_model=None,
)
async def get_variations_run_status(
    response: Response,
    run_id: Annotated[
        str, Path(description="The run id to retrieve the result or status for")
    ],
) -> RunStatusResponse | JSONResponse | ErrorResponse:
    """Return the status or result of an asynchronous registration of variations."""
    enabled = bool(
        anyvar.anyvar.has_variations_queueing_enabled() and has_async_imports
    )
    if not enabled:
        _logger.warning(
            "Async variation registration status requested but not enabled (has_variations_queueing_enabled=%s, has_async_imports=%s)",
            anyvar.anyvar.has_variations_queueing_enabled(),
            has_async_imports,
            stack_info=True,
        )
    error = check_async_enabled(
        enabled,
        response,
        "Required modules and/or configurations for asynchronous variation registration are missing",
    )
    if error:
        return error

    def on_success(async_result: AsyncResult) -> JSONResponse:
        result_data = async_result.result
        return JSONResponse(content=result_data, status_code=status.HTTP_200_OK)

    return await resolve_async_task_status(
        run_id,
        response,
        on_success=on_success,
        failure_status_env_var="ANYVAR_VARIATIONS_ASYNC_FAILURE_STATUS_CODE",
        status_path_prefix="/variations",
    )


PUT_VRS_VARIATION_EXAMPLE_PAYLOAD = {
    "location": {
        "end": 87894077,
        "start": 87894076,
        "sequenceReference": {
            "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
            "type": "SequenceReference",
        },
        "type": "SequenceLocation",
    },
    "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    "type": "Allele",
}


@variations_router.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. Returns a fully-identified VRS object.",
    response_model_exclude_none=True,
)
def register_vrs_variation(
    request: Request,
    variation: Annotated[
        objects.SupportedVrsVariation,
        Body(
            description="Valid VRS object.",
            examples=[PUT_VRS_VARIATION_EXAMPLE_PAYLOAD],
        ),
    ],
) -> RegisterVariationResponse:
    """Register a complete VRS variation object.

    No additional formatting or normalization is performed. IDs are added if not provided.
    """
    av: AnyVar = request.app.state.anyvar
    input_variation = variation
    try:
        av.put_objects([variation])
    except IncompleteVrsObjectError:
        variation = objects.recursive_identify(variation)
        av.put_objects([variation])

    liftover_messages = liftover.add_liftover_mapping(
        variation, av.object_store, av.translator.dp
    )

    return RegisterVariationResponse(
        input_variation=input_variation,
        object=variation,
        object_id=variation.id,
        messages=liftover_messages or [],
    )


@variations_router.post(
    "/variation",
    response_model_exclude_none=True,
    summary="Retrieve a registered VRS allele or copy number variation",
    description="Provide a variation definition to be normalized and searched for in AnyVar",
)
def get_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> GetObjectResponse:
    """Search for registered variation"""
    av: AnyVar = request.app.state.anyvar
    translated_variation = _handle_translation_request(av.translator, variation)
    vrs_id: str = translated_variation.id  # type: ignore
    _ = get_vrs_object(av, vrs_id)  # raise NOT_FOUND for vrs_id not present in DB
    return GetObjectResponse(messages=[], data=translated_variation)


@variations_router.get(
    "/variations",
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
    page_size: int = Query(1000, ge=1, le=10000),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
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
            refget_accession, start, end, page_size=page_size, cursor=cursor
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Search not implemented for current storage backend",
        ) from e

    return SearchResponse(variations=page.items, next_cursor=page.next_cursor)
