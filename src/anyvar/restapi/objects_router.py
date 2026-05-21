"""Provide router for operations on stored objects"""

import json
import logging
import os
from http import HTTPStatus
from typing import Annotated, cast

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response, status
from fastapi.params import Path
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar, ObjectNotFoundError
from anyvar.core import metadata, objects
from anyvar.mapping import liftover
from anyvar.restapi.async_utils import (
    check_async_enabled,
    resolve_async_task_status,
    validate_run_id_available,
)
from anyvar.restapi.schema import (
    AddExtensionRequest,
    AddExtensionResponse,
    AddMappingRequest,
    AddMappingResponse,
    ErrorResponse,
    GetExtensionResponse,
    GetMappingResponse,
    GetObjectResponse,
    RegisterVariationResponse,
    RunStatusResponse,
    VariationRequest,
)
from anyvar.storage.base import IncompleteVrsObjectError
from anyvar.translate.base import Translator
from anyvar.translate.register import (
    register_variations as _register_variations,
)
from anyvar.translate.register import (
    translate_variation as _translate_variation,
)

_async_imports_available = True
try:
    from billiard.exceptions import TimeLimitExceeded  # noqa: F401
    from celery.exceptions import WorkerLostError  # noqa: F401
    from celery.result import AsyncResult

    from anyvar.queueing import celery_worker
except ImportError:
    _async_imports_available = False

_logger = logging.getLogger(__name__)

objects_router = APIRouter()


def _get_vrs_object(
    av: AnyVar, vrs_object_id: str, object_type: type[objects.VrsObject] | None = None
) -> objects.VrsObject:
    """Get VRS variation given VRS ID

    :param av: AnyVar instance
    :param vrs_object_id: VRS Object ID to retrieve
    :param object_type: (Optional) The type of object to retrieve
    :raises HTTPException: If no VRS object ID found
    :return: VrsObject
    """
    try:
        return av.get_object(vrs_object_id, object_type)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_object_id} not found",
        ) from e


async def parse_and_rebuild_response(
    response: StreamingResponse,
) -> tuple[dict, Response]:
    """Convert a `Response` object to a dict, then re-build a new Response object (since parsing exhausts the Response `body_iterator`).

    :param response: the `Response` object to parse
    :return: a tuple with a dictionary representation of the Response and a new `Response` object
    """
    response_chunks: list[bytes] = [
        cast(bytes, chunk) async for chunk in response.body_iterator
    ]
    response_body_encoded = b"".join(response_chunks)
    response_body = response_body_encoded.decode("utf-8")
    response_json = json.loads(response_body)

    new_response = JSONResponse(
        content=response_json,
        status_code=response.status_code,
        media_type=response.media_type,
    )

    return (response_json, new_response)


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
) -> objects.VrsVariation:
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


@objects_router.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition  to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and ID is returned.",
)
def register_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
    do_liftover: Annotated[
        bool,
        Query(
            ...,
            description="Whether to perform liftover and store liftover mappings for the registered variation",
        ),
    ] = True,
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference."""
    av: AnyVar = request.app.state.anyvar

    responses: list[RegisterVariationResponse] = _register_variations(
        av, [variation], do_liftover=do_liftover
    )
    return responses[0]


@objects_router.put(
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
    do_liftover: Annotated[
        bool,
        Query(
            ...,
            description="Whether to perform liftover and store liftover mappings for the registered variation",
        ),
    ] = True,
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
        if (
            not anyvar.anyvar.has_variations_queueing_enabled()
            or not _async_imports_available
        ):
            _logger.warning(
                "Async variation registration requested but not enabled (has_variations_queueing_enabled=%s, _async_imports_available=%s)",
                anyvar.anyvar.has_variations_queueing_enabled(),
                _async_imports_available,
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
                "do_liftover": do_liftover,
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
    return _register_variations(av, variations, do_liftover=do_liftover)


@objects_router.get(
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
        anyvar.anyvar.has_variations_queueing_enabled() and _async_imports_available
    )
    if not enabled:
        _logger.warning(
            "Async variation registration status requested but not enabled (has_variations_queueing_enabled=%s, _async_imports_available=%s)",
            anyvar.anyvar.has_variations_queueing_enabled(),
            _async_imports_available,
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


@objects_router.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. Returns a fully-identified VRS object.",
    response_model_exclude_none=True,
)
def register_vrs_variation(
    request: Request,
    variation: Annotated[
        objects.VrsVariation,
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

    liftover_messages, _ = liftover.add_liftover_mapping(
        variation, av.object_store, av.translator.dp
    )

    return RegisterVariationResponse(
        input_variation=input_variation,
        object=variation,
        object_id=variation.id,
        messages=liftover_messages or [],
    )


@objects_router.post(
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
    _ = _get_vrs_object(av, vrs_id)  # raise NOT_FOUND for vrs_id not present in DB
    return GetObjectResponse(messages=[], data=translated_variation)


@objects_router.get(
    "/object/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a VRS object",
    description="Gets a VRS object by ID. May return any supported type of VRS Object.",
)
def get_object_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for object")],
) -> GetObjectResponse:
    """Get registered VRS object given its VRS ID."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.VrsObject = _get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=vrs_object)


@objects_router.delete(
    "/object/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="deleteObject",
    summary="Delete a VRS object and any associated mappings and extensions",
    description="Attempt deletion of a VRS object by its ID. Mappings and Extensions that reference this object will also be deleted.",
)
def delete_object_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="ID of object to delete")],
) -> None:
    """Delete a VRS object."""
    av: AnyVar = request.app.state.anyvar
    try:
        av.delete_object(vrs_id)
    except ObjectNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND) from e


@objects_router.post(
    "/object/{vrs_id}/extensions",
    response_model_exclude_none=True,
    summary="Add an extension to a VRS Object",
    description="Provide an extension to associate with a VRS object. The object MUST already be registered with AnyVar.",
)
def add_object_extension(
    request: Request,
    vrs_id: Annotated[
        StrictStr, Path(..., description="VRS ID of variation to annotate")
    ],
    extension_request: Annotated[
        AddExtensionRequest,
        Body(
            description="Extension to associate with the variation",
        ),
    ],
) -> AddExtensionResponse:
    """Store an extension for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.VrsObject = _get_vrs_object(av, vrs_id)

    extension_id: int | None = None
    try:
        extension = metadata.Extension(
            object_id=vrs_object.id,  # pyright: ignore[reportArgumentType] - VRS Objects from the DB will never NOT have an ID
            name=extension_request.name,
            value=extension_request.value,
        )
        extension_id = av.put_extension(extension)
    except ValueError as e:
        _logger.exception(
            "Failed to add Extension `%s` on VRS Object `%s`",
            extension_request,
            vrs_id,
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to add extension: {extension_request}",
        ) from e

    return AddExtensionResponse(
        object=vrs_object,
        object_id=vrs_id,
        extension_name=extension_request.name,
        extension_value=extension_request.value,
        extension_id=extension_id,
    )


@objects_router.get(
    "/object/{vrs_id}/extensions/{extension_name}",
    response_model_exclude_none=True,
    summary="Retrieve extensions for a VRS Object",
    description="Retrieve extensions for a VRS Object by VRS ID and extension type",
)
def get_object_extensions(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for VRS Object")],
    extension_name: Annotated[StrictStr, Path(..., description="Extension name")],
) -> GetExtensionResponse:
    """Retrieve extensions for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    try:
        extensions = av.get_object_extensions(vrs_id, extension_name)
    except ObjectNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_id} not found",
        ) from e
    return GetExtensionResponse(extensions=extensions)


@objects_router.put(
    "/object/{vrs_id}/mappings",
    response_model_exclude_none=True,
    summary="Add mapping to a VRS Object",
    description="Provide a mapping to associate with a VRS object. The source and dest objects must be registered with AnyVar before adding mappings.",
)
def add_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID")],
    mapping_request: Annotated[
        AddMappingRequest, Body(description="Mapping to associate with the VRS Object")
    ],
) -> AddMappingResponse:
    """Store a mapping for a VRS Object"""
    av: AnyVar = request.app.state.anyvar
    source_vrs_obj: objects.VrsObject = _get_vrs_object(av, vrs_id)
    dest_vrs_id = mapping_request.dest_id
    dest_vrs_obj: objects.VrsObject = _get_vrs_object(av, dest_vrs_id)

    # Add the mapping to the database
    mapping: metadata.VariationMapping | None = None
    mapping_type = mapping_request.mapping_type
    try:
        mapping = metadata.VariationMapping(
            source_id=vrs_id, dest_id=dest_vrs_id, mapping_type=mapping_type
        )
        av.put_mapping(mapping)
    except ValueError as e:
        _logger.exception(
            "Failed to add mapping `%s` on variation `%s`",
            mapping_request,
            vrs_id,
        )
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"Failed to add mapping: {mapping_request}. {e}",
        ) from e

    return AddMappingResponse(
        source_object=source_vrs_obj,
        source_object_id=vrs_id,
        dest_object=dest_vrs_obj,
        dest_object_id=dest_vrs_id,
        mapping_type=mapping_type,
    )


_get_mappings_description = """Retrieve mappings associated with a VRS object.

Mappings are *directed*; if `as_source=true`, then retrieve mappings where the VRS object is the mapping *source*, i.e. where the mapping points from the object to another. Otherwise, get mappings where another object points to the VRS object.

By default, retrieve mappings of any type. Use the `mapping_type` argument to specify a specific type.
"""


@objects_router.get(
    "/object/{vrs_id}/mappings/{mapping_type}",
    response_model_exclude_none=True,
    summary="Retrieve mappings for a VRS Object",
    description=_get_mappings_description,
)
def get_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    mapping_type: Annotated[
        metadata.VariationMappingType, Path(..., description="Mapping type")
    ],
    as_source: Annotated[
        bool,
        Query(
            ...,
            description="If `true`, get mappings where `vrs_id` corresponds to the mapping source; otherwise, get mappings where `vrs_id` is the mapping destination",
        ),
    ] = True,
) -> GetMappingResponse:
    """Retrieve mappings for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    try:
        mappings = av.get_object_mappings(vrs_id, mapping_type, as_source)
    except ObjectNotFoundError as e:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_id} not found",
        ) from e

    return GetMappingResponse(mappings=mappings)
