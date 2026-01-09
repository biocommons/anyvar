"""Provide core route definitions for REST service."""

import json
import logging
import logging.config
import os
import pathlib
from collections.abc import Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated, cast

import anyio
import yaml
from dotenv import load_dotenv
from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
)
from fastapi.responses import JSONResponse, StreamingResponse
from ga4gh.vrs.dataproxy import DataProxyValidationError
from hgvs.exceptions import HGVSParseError
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar, ObjectNotFoundError
from anyvar.restapi.auth import get_token_auth_dependency
from anyvar.restapi.schema import (
    AddAnnotationRequest,
    AddAnnotationResponse,
    AddMappingRequest,
    AddMappingResponse,
    EndpointTag,
    GetAnnotationResponse,
    GetMappingResponse,
    GetObjectResponse,
    RegisterVariationResponse,
    SearchResponse,
    ServiceInfo,
    TranslationResult,
    VariationRequest,
)
from anyvar.restapi.vcf import router as vcf_router
from anyvar.storage.base_storage import IncompleteVrsObjectError
from anyvar.translate.translate import (
    TranslationError,
    Translator,
)
from anyvar.utils import liftover_utils, types
from anyvar.utils.types import (
    VrsObject,
    VrsVariation,
    recursive_identify,
)

load_dotenv()
_logger = logging.getLogger(__name__)


def _get_vrs_object(
    av: AnyVar, vrs_object_id: str, object_type: type[types.VrsObject] | None = None
) -> VrsObject:
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


@asynccontextmanager
async def app_lifespan(param_app: FastAPI):  # noqa: ANN201
    """Initialize AnyVar instance and associate with FastAPI app on startup
    and teardown the AnyVar instance on shutdown
    """
    # Configure logging from file or use default
    logging_config_file = os.environ.get("ANYVAR_LOGGING_CONFIG", None)
    if logging_config_file and pathlib.Path(logging_config_file).is_file():
        async with await anyio.open_file(logging_config_file) as f:
            try:
                contents = await f.read()
                config = yaml.safe_load(contents)
                logging.config.dictConfig(config)
                _logger.info("Logging using configs set from %s", logging_config_file)
            except Exception:
                _logger.exception(
                    "Error in Logging Configuration. Using default configs"
                )
    else:
        _logger.info("Logging with default configs.")

    # Override default service-info parameters
    service_info_config_file = os.environ.get("ANYVAR_SERVICE_INFO")
    if service_info_config_file and pathlib.Path(service_info_config_file).is_file():
        async with await anyio.open_file(service_info_config_file) as f:
            try:
                contents = await f.read()
                param_app.state.service_info = yaml.safe_load(contents)
                _logger.info(
                    "Assigning service info values from %s", service_info_config_file
                )
            except Exception:
                _logger.exception(
                    "Error loading from service info description at %s. Using default configs",
                    service_info_config_file,
                )
    else:
        _logger.warning("Falling back on default service description.")

    # create anyvar instance
    storage = anyvar.anyvar.create_storage()
    translator = anyvar.anyvar.create_translator()
    anyvar_instance = AnyVar(object_store=storage, translator=translator)

    # associate anyvar with the app state
    param_app.state.anyvar = anyvar_instance
    yield

    # close storage connector on shutdown
    storage.close()


app = FastAPI(
    title="AnyVar",
    version=anyvar.__version__,
    docs_url="/",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"tryItOutEnabled": True},
    description="Register and retrieve VRS value objects.",
    lifespan=app_lifespan,
    dependencies=[Depends(get_token_auth_dependency())],
)
app.include_router(vcf_router)


@app.get(
    "/service-info",
    summary="Get basic service information",
    description="Retrieve service metadata, such as versioning and contact info. Structured in conformance with the [GA4GH service info API specification](https://www.ga4gh.org/product/service-info/)",
    tags=[EndpointTag.GENERAL],
)
def service_info(
    request: Request,
) -> ServiceInfo:
    """Provide service info per GA4GH Service Info spec

    :param request: FastAPI request object
    :return: service info description
    """
    service_info = getattr(request.app.state, "service_info", {})
    return ServiceInfo(**service_info)


VARIATION_EXAMPLE_PAYLOAD = {
    "definition": "NC_000007.13:g.36561662_36561663del",
    "input_type": "Allele",
    "copies": 0,
    "copy_change": "complete genomic loss",
    "assembly_name": None,
}


_variation_request_body = Body(
    description="Variation description, including (at minimum) a definition property. Can provide optional input_type if the expected output representation is known, as well as an assembly_name (e.g.,'GRCh37' or 'GRCh38'). If representing copy number, provide copies or copy_change.",
    examples=[VARIATION_EXAMPLE_PAYLOAD],
)


def _translate_variation(
    tlr: Translator, variation_request: VariationRequest
) -> TranslationResult:
    """Perform variant translation

    :param tlr: Translator instance
    :param variation_request: Input variation request to translate
    :return: TranslationResult object with translated variation, if translation is
        successful. Otherwise, return error message
    """
    definition = variation_request.definition

    try:
        translated_variation = tlr.translate_variation(
            definition, **variation_request.model_dump(mode="json")
        )
        return TranslationResult(variation=translated_variation)
    except DataProxyValidationError as e:
        return TranslationResult(error=str(e))
    except HGVSParseError:
        return TranslationResult(
            error=f'Unable to parse HGVS expression "{definition}"'
        )
    except NotImplementedError:
        return TranslationResult(
            error=f"Variation class for {definition} is currently unsupported."
        )
    except TranslationError:
        return TranslationResult(error=f'Unable to translate "{definition}"')


def _handle_translation_request(
    tlr: Translator, var_req: VariationRequest
) -> VrsVariation:
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


def _register_variations(
    av: AnyVar, variation_requests: list[VariationRequest]
) -> list[RegisterVariationResponse]:
    """Bulk register variations

    :param av: AnyVar instance
    :param variation_requests: Input variation requests to register
    :return: List of RegisterVariationResponse objects in the same order as the input.
        Variations that fail translation are not registered and are returned with null
        `object` and `object_id` fields. Registration or liftover failure messages may
        also be included in the `messages` field.
    """
    translation_results: list[TranslationResult] = []
    variations_to_store: list[VrsObject] = []

    for variation_request in variation_requests:
        translation_result = _translate_variation(av.translator, variation_request)
        translation_results.append(translation_result)

        if translation_result.variation:
            variations_to_store.append(translation_result.variation)

    if variations_to_store:
        av.put_objects(variations_to_store)

    responses: list[RegisterVariationResponse] = []

    for variation_request, translation_result in zip(
        variation_requests, translation_results, strict=True
    ):
        if not translation_result.variation:
            responses.append(
                RegisterVariationResponse(
                    input_variation=variation_request,
                    messages=[translation_result.error]
                    if translation_result.error
                    else [],
                )
            )
            continue

        messages: list[str] = (
            liftover_utils.add_liftover_mapping(
                variation=translation_result.variation,
                storage=av.object_store,
                dataproxy=av.translator.dp,
            )
            or []
        )

        responses.append(
            RegisterVariationResponse(
                input_variation=variation_request,
                object=translation_result.variation,
                object_id=translation_result.variation.id
                if translation_result.variation
                else None,
                messages=messages,
            )
        )

    return responses


@app.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and digest is returned for later reference.",
    tags=[EndpointTag.VRS_OBJECTS],
)
def register_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference."""
    av: AnyVar = request.app.state.anyvar

    responses: list[RegisterVariationResponse] = _register_variations(av, [variation])
    return responses[0]


@app.put(
    "/variations",
    response_model_exclude_none=True,
    summary="Bulk register alleles or copy number objects",
    description="Provide a list of variation definitions to be normalized and registered with AnyVar. The response contains one result per input, in the same order. Variations that fail translation are not registered and are returned with null `object` and `object_id` fields. Registration or liftover failure messages may also be included in the `messages` field.",
    tags=[EndpointTag.VRS_OBJECTS],
)
def register_variations(
    request: Request,
    variations: Annotated[
        list[VariationRequest], Body(description="List of variations to register")
    ],
) -> list[RegisterVariationResponse]:
    """Register multiple variations based on provided descriptions or references."""
    av: AnyVar = request.app.state.anyvar
    return _register_variations(av, variations)


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


@app.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. A digest is returned for later reference.",
    response_model_exclude_none=True,
    tags=[EndpointTag.VRS_OBJECTS],
)
def register_vrs_object(
    request: Request,
    variation: Annotated[
        VrsVariation,
        Body(
            description="Valid VRS object.",
            examples=[PUT_VRS_VARIATION_EXAMPLE_PAYLOAD],
        ),
    ],
) -> RegisterVariationResponse:
    """Register a complete VRS object. No additional normalization is performed."""
    av: AnyVar = request.app.state.anyvar
    input_variation = variation
    try:
        av.put_objects([variation])
    except IncompleteVrsObjectError:
        variation = recursive_identify(variation)
        av.put_objects([variation])
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Variation could not be registered",
        ) from e

    liftover_messages = liftover_utils.add_liftover_mapping(
        variation, av.object_store, av.translator.dp
    )

    return RegisterVariationResponse(
        input_variation=input_variation,
        object=variation,
        object_id=variation.id,
        messages=liftover_messages or [],
    )


@app.post(
    "/variation",
    response_model_exclude_none=True,
    summary="Retrieve a registered allele or copy number variation",
    description="Provide a variation definition to be normalized and searched for in AnyVar",
    tags=[EndpointTag.VRS_OBJECTS],
)
def get_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> GetObjectResponse:
    """Search for registered variation"""
    av: AnyVar = request.app.state.anyvar
    translated_variation = _handle_translation_request(av.translator, variation)
    vrs_id: str = translated_variation.id  # type: ignore
    _get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=translated_variation)


@app.get(
    "/object/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a VRS object",
    description="Gets a VRS object by ID. May return any supported type of VRS Object.",
    tags=[EndpointTag.VRS_OBJECTS],
)
def get_object_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for object")],
) -> GetObjectResponse:
    """Get registered VRS object given its VRS ID.

    :param request: FastAPI request object
    :param object_id: ID to look up
    :return: VRS Object if successful
    :raise HTTPException: if no variation matches provided ID
    """
    av: AnyVar = request.app.state.anyvar
    vrs_object: VrsObject = _get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=vrs_object)


@app.post(
    "/object/{vrs_id}/annotations",
    response_model_exclude_none=True,
    summary="Add annotation to a VRS Object",
    description="Provide an annotation to associate with a VRS object. The object must be registered with AnyVar before adding annotations.",
    tags=[EndpointTag.VRS_OBJECTS],
)
def add_object_annotation(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    annotation_request: Annotated[
        AddAnnotationRequest,
        Body(
            description="Annotation to associate with the variation",
        ),
    ],
) -> AddAnnotationResponse:
    """Store an annotation for a VRS Object.

    :param request: FastAPI request object
    :param vrs_id: the VRS ID of the VRS Object to annotate
    :param annotation: the annotation to store
    :return: the VRS Object and annotations if stored
    :raise HTTPException: if requested location isn't found
    """
    # Look up the VRS Object from the AnyVar store
    av: AnyVar = request.app.state.anyvar
    vrs_object: VrsObject = _get_vrs_object(av, vrs_id)

    # Add the annotation to the database
    annotation_id: int | None = None
    try:
        annotation = types.Annotation(
            object_id=vrs_object.id,  # pyright: ignore[reportArgumentType] - VRS Objects from the DB will never NOT have an ID
            annotation_type=annotation_request.annotation_type,
            annotation_value=annotation_request.annotation_value,
        )
        annotation_id = av.put_annotation(annotation)
    except ValueError as e:
        _logger.exception(
            "Failed to add annotation `%s` on VRS Object `%s`",
            annotation_request,
            vrs_id,
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to add annotation: {annotation_request}",
        ) from e

    return AddAnnotationResponse(
        object=vrs_object,
        object_id=vrs_id,
        annotation_type=annotation_request.annotation_type,
        annotation_value=annotation_request.annotation_value,
        annotation_id=annotation_id,
    )


@app.get(
    "/object/{vrs_id}/annotations/{annotation_type}",
    response_model_exclude_none=True,
    summary="Retrieve annotations for a VRS Object",
    description="Retrieve annotations for a VRS Object by VRS ID and annotation type",
    tags=[EndpointTag.VRS_OBJECTS],
)
def get_object_annotations(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for VRS Object")],
    annotation_type: Annotated[StrictStr, Path(..., description="Annotation type")],
) -> GetAnnotationResponse:
    """Retrieve annotations for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    try:
        annotations = av.get_object_annotations(vrs_id, annotation_type)
    except ObjectNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_id} not found",
        ) from e
    return GetAnnotationResponse(annotations=annotations)


@app.put(
    "/object/{vrs_id}/mappings",
    response_model_exclude_none=True,
    summary="Add mapping to a VRS Object",
    description="Provide a mapping to associate with a VRS object. The source and dest objects must be registered with AnyVar before adding mappings.",
    tags=[EndpointTag.VRS_OBJECTS],
)
async def add_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID")],
    mapping_request: Annotated[
        AddMappingRequest, Body(description="Mapping to associate with the VRS Object")
    ],
) -> AddMappingResponse:
    """Store a mapping for a VRS Object

    :param request: FastAPI request object
    :param vrs_id: The VRS ID of the object to add mapping to
    :param mapping_request: The mapping to store
    :raises HTTPException: If unable to store a mapping, or source or dest objects
        not registered
    :return: source and destination VRS object and mapping type, if found
    """
    av: AnyVar = request.app.state.anyvar
    source_vrs_obj: VrsObject = _get_vrs_object(av, vrs_id)
    dest_vrs_id = mapping_request.dest_id
    dest_vrs_obj: VrsObject = _get_vrs_object(av, dest_vrs_id)

    # Add the mapping to the database
    mapping: types.VariationMapping | None = None
    mapping_type = mapping_request.mapping_type
    try:
        mapping = types.VariationMapping(
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
            detail=f"Failed to add annotation: {mapping_request}. {e}",
        ) from e

    return AddMappingResponse(
        source_object=source_vrs_obj,
        source_object_id=vrs_id,
        dest_object=dest_vrs_obj,
        dest_object_id=dest_vrs_id,
        mapping_type=mapping_type,
    )


@app.get(
    "/object/{vrs_id}/mappings/{mapping_type}",
    response_model_exclude_none=True,
    summary="Retrieve mappings for a VRS Object",
    description="Retrieve mappings for a VRS Object by ID and mapping type",
    tags=[EndpointTag.VRS_OBJECTS],
)
def get_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    mapping_type: Annotated[
        types.VariationMappingType, Path(..., description="Mapping type")
    ],
) -> GetMappingResponse:
    """Retrieve mappings for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    try:
        mappings = av.get_object_mappings(vrs_id, mapping_type)
    except ObjectNotFoundError as e:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            detail=f"VRS Object {vrs_id} not found",
        ) from e

    return GetMappingResponse(mappings=mappings)


@app.middleware("http")
async def add_registration_annotations(
    request: Request, call_next: Callable
) -> Response:
    """Add all required annotations ("creation_timestamp") for newly-registered variants

    :param request: FastAPI `Request` object
    :param call_next: A FastAPI function that receives the `request` as a parameter, passes it to the corresponding path operation, and returns the generated `response`
    :return: FastAPI`Response` object
    """
    # Do nothing on request. Pass downstream.
    response = await call_next(request)

    # Make sure we're only targeting the registration endpoints
    registration_endpoints = [
        "/variation",
        "/vrs_variation",
    ]

    if request.url.path not in registration_endpoints:
        return response

    response_json, new_response = await parse_and_rebuild_response(
        response
    )  # We'll need to return the `new_response` object since we have now exhausted the original response body iterator

    input_vrs_id, input_variant = (
        response_json.get("object_id"),
        response_json.get("object"),
    )
    if (
        (not input_vrs_id) or (not input_variant)
    ):  # If there's no input_vrs_id/input variant, registration was unsuccessful. Do not attempt any further operations.
        return new_response

    # Add creation timestamp annotation
    av: AnyVar = request.app.state.anyvar
    av.create_timestamp_annotation_if_missing(input_vrs_id)
    return new_response


@app.get(
    "/search",
    response_model_exclude_none=True,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Fetch all registered variations within the provided genomic coordinates",
    tags=[EndpointTag.SEARCH],
)
def search_variations(
    request: Request,
    accession: Annotated[str, Query(..., description="Sequence accession identifier")],
    start: Annotated[int, Query(..., description="Start position for genomic region")],
    end: Annotated[int, Query(..., description="End position for genomic region")],
) -> SearchResponse:
    """Fetch all registered variations within the provided genomic coordinates.

    :param request: FastAPI request object
    :param accession: sequence accession
    :param start: start position for genomic region
    :param end: end position for genomic region
    :return: list (possibly empty) of variations in the given region
    """
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
