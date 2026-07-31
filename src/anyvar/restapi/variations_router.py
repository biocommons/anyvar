"""Provide API routes relating to variation operations"""

import logging
import os
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response, status
from fastapi.params import Path
from fastapi.responses import JSONResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar, ObjectNotFoundError
from anyvar.core import metadata, objects
from anyvar.restapi import has_async_imports
from anyvar.restapi.async_utils import (
    check_async_enabled,
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
    SearchResponse,
    VariationRequest,
)
from anyvar.restapi.utils import get_vrs_object
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


PUT_VARIATIONS_EXAMPLE_PAYLOAD = [
    {
        "definition": "NC_000010.11:g.87894077C>T",
        "assembly_name": None,
    },
    {
        "definition": {
            "type": "Allele",
            "location": {
                "id": "ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
                "type": "SequenceLocation",
                "digest": "JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
                "sequenceReference": {
                    "type": "SequenceReference",
                    "refgetAccession": "SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
                },
                "start": 36561661,
                "end": 36561663,
            },
            "state": {
                "type": "ReferenceLengthExpression",
                "length": 0,
                "sequence": "",
                "repeatSubunitLength": 2,
            },
        }
    },
]

_put_variations_request_body = Body(
    description='Variation description, including (at minimum) a `definition` property. Can provide optional `input_type` if the expected output representation type is known, as well as an assembly_name (e.g.,"GRCh37" or "GRCh38").',
    examples=[PUT_VARIATIONS_EXAMPLE_PAYLOAD],
)


@variations_router.put(
    "/variations",
    response_model_exclude_none=True,
    summary="Bulk register alleles",
    description="Provide a list of variation definitions to be normalized and registered with AnyVar. The response contains one result per input, in the same order. Variations that fail translation are not registered and are returned with null `object` and `object_id` fields. Registration or liftover failure messages may also be included in the `messages` field.",
)
async def register_variations(
    request: Request,
    response: Response,
    variations: Annotated[list[VariationRequest], _put_variations_request_body],
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
            status_message=f"Run submitted. Check status at /variations/runs/{task_result.id}",
        )

    av: AnyVar = request.app.state.anyvar
    return _register_variations(av, variations)


POST_VARIATIONS_EXAMPLE_PAYLOAD = {"definition": "NM_000551.3:c.1A>T"}
_post_variations_request_body = Body(
    description='Variation description, including (at minimum) a `definition` property. Can provide optional `input_type` if the expected output representation type is known, as well as an assembly_name (e.g.,"GRCh37" or "GRCh38").',
    examples=[POST_VARIATIONS_EXAMPLE_PAYLOAD],
)


@variations_router.post(
    "/variations",
    response_model_exclude_none=True,
    summary="Retrieve a registered VRS allele or copy number variation",
    description="Provide a variation definition to be normalized and searched for in AnyVar",
)
def get_variation(
    request: Request,
    variation: Annotated[VariationRequest, _post_variations_request_body],
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


@variations_router.get(
    "/variations/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a variation",
    description="Gets a variation by ID. May return any supported type of variation.",
)
def get_variation_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for object")],
) -> GetObjectResponse:
    """Get registered variation given its VRS ID."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=vrs_object)


@variations_router.delete(
    "/variations/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="deleteObject",
    summary="Delete a variation and any associated mappings and extensions",
    description="Attempt deletion of a variation by its ID. Mappings and Extensions that reference this object will also be deleted.",
)
def delete_variation_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="ID of object to delete")],
) -> None:
    """Delete a variation."""
    av: AnyVar = request.app.state.anyvar
    try:
        av.delete_object(vrs_id)
    except ObjectNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND) from e


@variations_router.post(
    "/variations/{vrs_id}/extensions",
    response_model_exclude_none=True,
    summary="Add an extension to a variation",
    description="Provide an extension to associate with a variation. The object MUST already be registered with AnyVar.",
)
def add_variation_extension(
    request: Request,
    vrs_id: Annotated[
        StrictStr, Path(..., description="VRS ID of variation to annotate")
    ],
    extension_request: Annotated[
        AddExtensionRequest,
        Body(
            description="Extension to associate with the variation",
            examples=[{"name": "source_dataset", "value": "gnomAD_v4.1"}],
        ),
    ],
) -> AddExtensionResponse:
    """Store an extension for a variation."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)

    extension_id: int | None = None
    try:
        extension = metadata.Extension(
            object_id=vrs_object.id,  # pyright: ignore[reportArgumentType] - variations from the DB will never NOT have an ID
            name=extension_request.name,
            value=extension_request.value,
        )
        extension_id = av.put_extension(extension)
    except ValueError as e:
        _logger.exception(
            "Failed to add Extension `%s` on variation `%s`",
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


@variations_router.get(
    "/variations/{vrs_id}/extensions/{extension_name}",
    response_model_exclude_none=True,
    summary="Retrieve extensions for a variation",
    description="Retrieve extensions for a variation by VRS ID and extension type",
)
def get_variation_extensions(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    extension_name: Annotated[StrictStr, Path(..., description="Extension name")],
) -> GetExtensionResponse:
    """Retrieve extensions for a variation."""
    av: AnyVar = request.app.state.anyvar
    try:
        extensions = av.get_object_extensions(vrs_id, extension_name)
    except ObjectNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Variation {vrs_id} not found",
        ) from e
    return GetExtensionResponse(extensions=extensions)


@variations_router.delete(
    "/variations/{vrs_id}/extensions/{extension_name}",
    response_model_exclude_none=True,
    summary="Delete extensions for a variation.",
    description="Delete all extensions under a given extension name for a variation. Returns idempotently regardless of whether there were extensions under that name for the object. Return 404 NOT FOUND if no known object matches given object ID.",
    status_code=HTTPStatus.NO_CONTENT,
)
def delete_variation_extensions(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    extension_name: Annotated[StrictStr, Path(..., description="Extension name")],
) -> Response:
    """Delete extensions associated with a variation."""
    av: AnyVar = request.app.state.anyvar
    try:
        av.delete_object_extensions(vrs_id, extension_name)
    except ObjectNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Variation {vrs_id} not found"
        ) from e
    return Response(status_code=HTTPStatus.NO_CONTENT)  # blank response if successful


@variations_router.put(
    "/variations/{vrs_id}/mappings",
    response_model_exclude_none=True,
    summary="Add mapping to a variation",
    description="Provide a mapping to associate with a variation. The source and dest objects must be registered with AnyVar before adding mappings.",
)
def add_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID")],
    mapping_request: Annotated[
        AddMappingRequest, Body(description="Mapping to associate with the variation")
    ],
) -> AddMappingResponse:
    """Store a mapping for a variation"""
    av: AnyVar = request.app.state.anyvar
    source_vrs_obj: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)
    dest_vrs_id = mapping_request.dest_id
    dest_vrs_obj: objects.SupportedVrsObject = get_vrs_object(av, dest_vrs_id)

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


_get_mappings_description = """Retrieve mappings associated with a variation.

Mappings are *directed*; if `as_source=true`, then retrieve mappings where the variation is the mapping *source*, i.e. where the mapping points from the object to another. Otherwise, get mappings where another object points to the variation.

By default, retrieve mappings of any type. Use the `mapping_type` argument to specify a specific type.
"""


@variations_router.get(
    "/variations/{vrs_id}/mappings",
    response_model_exclude_none=True,
    summary="Retrieve mappings for a variation",
    description=_get_mappings_description,
)
def get_variation_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    mapping_type: Annotated[
        metadata.VariationMappingType | None, Query(..., description="Mapping type")
    ] = None,
    as_source: Annotated[
        bool,
        Query(
            ...,
            description="If `true`, get mappings where `vrs_id` corresponds to the mapping source; otherwise, get mappings where `vrs_id` is the mapping destination",
        ),
    ] = True,
) -> GetMappingResponse:
    """Retrieve mappings for a variation."""
    av: AnyVar = request.app.state.anyvar
    try:
        mappings = av.get_object_mappings(vrs_id, mapping_type, as_source)
    except ObjectNotFoundError as e:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            detail=f"Variation {vrs_id} not found",
        ) from e

    return GetMappingResponse(mappings=mappings)


@variations_router.get(
    "/variations/runs/{run_id}",
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
