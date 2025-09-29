"""Provide core route definitions for REST service."""

import datetime
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
import ga4gh.vrs
import yaml
from dotenv import load_dotenv
from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyAnnotation, AnyVar
from anyvar.restapi.schema import (
    AddAnnotationRequest,
    AddAnnotationResponse,
    AnyVarStatsResponse,
    EndpointTag,
    GetAnnotationResponse,
    GetSequenceLocationResponse,
    GetVariationResponse,
    RegisterVariationRequest,
    RegisterVariationResponse,
    RegisterVrsVariationResponse,
    SearchResponse,
    ServiceInfo,
    VariationStatisticType,
)
from anyvar.restapi.vcf import router as vcf_router
from anyvar.translate.translate import (
    TranslationError,
)
from anyvar.utils import liftover_utils
from anyvar.utils.types import VrsVariation, variation_class_map

load_dotenv()
_logger = logging.getLogger(__name__)


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

    # create annotation instance if configured
    annotation_storage = None
    if "ANYVAR_ANNOTATION_STORAGE_URI" in os.environ:
        if "ANYVAR_ANNOTATION_TABLE_NAME" not in os.environ:
            raise ValueError(
                "ANYVAR_ANNOTATION_TABLE_NAME is required if ANYVAR_ANNOTATION_STORAGE_URI is set"
            )
        annotation_storage = anyvar.anyvar.create_annotation_storage(
            os.environ["ANYVAR_ANNOTATION_STORAGE_URI"],
            table_name=os.environ["ANYVAR_ANNOTATION_TABLE_NAME"],
        )
        anyannotation_instance = AnyAnnotation(annotation_storage)
        param_app.state.anyannotation = anyannotation_instance

    yield

    # close storage connector on shutdown
    storage.close()
    if annotation_storage:
        annotation_storage.close()


app = FastAPI(
    title="AnyVar",
    version=anyvar.__version__,
    docs_url="/",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"tryItOutEnabled": True},
    description="Register and retrieve VRS value objects.",
    lifespan=app_lifespan,
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


@app.get(
    "/locations/{location_id}",
    response_model_exclude_none=True,
    summary="Retrieve sequence location",
    description="Retrieve registered sequence location by ID",
    tags=[EndpointTag.LOCATIONS],
)
def get_location_by_id(
    request: Request,
    location_id: Annotated[StrictStr, Path(..., description="Location VRS ID")],
) -> GetSequenceLocationResponse:
    """Retrieve stored location object by ID.

    :param request: FastAPI request object
    :param location_id: VRS location identifier
    :return: complete location object if successful
    :raise HTTPException: if requested location isn't found
    """
    av: AnyVar = request.app.state.anyvar
    try:
        location: ga4gh.vrs.models.SequenceLocation = av.get_object(location_id)  # type: ignore[reportAssignmentType]
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
        ) from e

    if location:
        return GetSequenceLocationResponse(location=location)
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
    )


@app.post(
    "/variation/{vrs_id}/annotations",
    response_model_exclude_none=True,
    summary="Add annotation to a variation",
    description="Provide an annotation to associate with a Variation object. The Variation must be registered with AnyVar before adding annotations.",
    tags=[EndpointTag.VARIATIONS],
)
def add_variation_annotation(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    annotation: Annotated[
        AddAnnotationRequest,
        Body(
            description="Annotation to associate with the variation",
        ),
    ],
) -> AddAnnotationResponse:
    """Store an annotation for a variation.

    :param request: FastAPI request object
    :param vrs_id: the VRS ID of the variation to annotate
    :param annotation: the annotation to store
    :return: the variation and annotations if stored
    :raise HTTPException: if requested location isn't found
    """
    messages: list[str] = []
    # Look up the variation from the AnyVar store
    av: AnyVar = request.app.state.anyvar
    try:
        variation = av.get_object(vrs_id)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Variation {vrs_id} not found"
        ) from e

    # Add the annotation to the annotation store
    if hasattr(request.app.state, "anyannotation"):
        anyannotation: AnyAnnotation = request.app.state.anyannotation
        try:
            anyannotation.put_annotation(
                object_id=vrs_id,
                annotation_type=annotation.annotation_type,
                annotation=annotation.annotation,
            )
        except ValueError as e:
            _logger.exception(
                "Failed to add annotation `%s` on variation `%s`", annotation, vrs_id
            )
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"Failed to add annotation: {annotation}",
            ) from e
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Annotations are not supported by this backend configuration.",
        )

    return AddAnnotationResponse(
        messages=messages,
        object=variation,
        object_id=vrs_id,
        annotation_type=annotation.annotation_type,
        annotation=annotation.annotation,
    )


@app.get(
    "/variation/{vrs_id}/annotations/{annotation_type}",
    response_model_exclude_none=True,
    summary="Retrieve annotations for a variation",
    description="Retrieve annotations for a variation by VRS ID and annotation type",
    tags=[EndpointTag.VARIATIONS],
)
def get_variation_annotation(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    annotation_type: Annotated[StrictStr, Path(..., description="Annotation type")],
) -> GetAnnotationResponse:
    """Retrieve annotations for a variation.

    :param request: FastAPI request object
    :param vrs_id: VRS ID for variation
    :param annotation_type: type of annotation to retrieve
    :return: response object containing list of annotations for the variation
    """
    if not hasattr(request.app.state, "anyannotation"):
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Annotations are not supported by this backend configuration.",
        )
    anyannotation: AnyAnnotation = request.app.state.anyannotation
    annotations = anyannotation.get_annotation(vrs_id, annotation_type)

    return GetAnnotationResponse(annotations=annotations)


@app.middleware("http")
async def add_registration_annotations(
    request: Request, call_next: Callable
) -> Response:
    """Add all required annotations ("creation_timestamp" & "liftover") for newly-registered variants

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

    # Add annotations
    annotator: AnyAnnotation | None = getattr(request.app.state, "anyannotation", None)
    if annotator:
        timestamp_annotations = annotator.get_annotation(
            input_vrs_id, "creation_timestamp"
        )
        if not timestamp_annotations:
            annotator.put_annotation(
                object_id=input_vrs_id,
                annotation_type="creation_timestamp",
                annotation={
                    "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat()
                },
            )

        liftover_annotations = annotator.get_annotation(input_vrs_id, "liftover")
        if not liftover_annotations:
            liftover_utils.add_liftover_annotations(
                input_vrs_id=input_vrs_id,
                input_vrs_variant_dict=input_variant,
                anyvar=request.app.state.anyvar,
                annotator=annotator,
            )

    return new_response


@app.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and digest is returned for later reference.",
    tags=[EndpointTag.VARIATIONS],
)
def register_variation(
    request: Request,
    variation: Annotated[
        RegisterVariationRequest,
        Body(
            description="Variation description, including (at minimum) a definition property. Can provide optional input_type if the expected output representation is known. If representing copy number, provide copies or copy_change.",
            examples=[
                {
                    "definition": "NC_000007.13:g.36561662_36561663del",
                    "input_type": "Allele",
                    "copies": 0,
                    "copy_change": "complete genomic loss",
                }
            ],
        ),
    ],
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference.

    :param request: FastAPI request object
    :param variation: provided variation description
    :return: messages describing translation failure, or object and references if
        successful
    """
    av: AnyVar = request.app.state.anyvar
    definition = variation.definition

    result = {"object": None, "messages": [], "object_id": None}
    try:
        translated_variation = av.translator.translate_variation(
            definition, **variation.model_dump()
        )
    except TranslationError:
        result["messages"].append(f'Unable to translate "{definition}"')
    except NotImplementedError:
        result["messages"].append(
            f"Variation class for {definition} is currently unsupported."
        )
    else:
        if translated_variation:
            v_id = av.put_object(translated_variation)
            result["object"] = translated_variation
            result["object_id"] = v_id
        else:
            result["messages"].append(f"Translation of {definition} failed.")
    return RegisterVariationResponse(**result)


@app.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. A digest is returned for later reference.",
    response_model_exclude_none=True,
    tags=[EndpointTag.VARIATIONS],
)
def register_vrs_object(
    request: Request,
    variation: Annotated[
        VrsVariation,
        Body(
            description="Valid VRS object.",
            examples=[
                {
                    "location": {
                        "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
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
            ],
        ),
    ],
) -> RegisterVrsVariationResponse:
    """Register a complete VRS object. No additional normalization is performed.

    :param request: FastAPI request object
    :param variation: provided VRS variation object
    :return: object and references if successful
    """
    av: AnyVar = request.app.state.anyvar
    result = {
        "object": None,
        "messages": [],
    }
    variation_type = variation.type
    if variation_type not in variation_class_map:
        result["messages"].append(
            f"Registration for {variation_type} not currently supported."
        )
        return RegisterVrsVariationResponse(**result)

    variation_object = variation_class_map[variation_type](**variation.model_dump())
    v_id = av.put_object(variation_object)
    result["object"] = variation_object
    result["object_id"] = v_id
    return RegisterVrsVariationResponse(**result)


@app.get(
    "/variation/{variation_id}",
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a variation object",
    description="Gets a variation instance by ID. May return any supported type of variation.",
    tags=[EndpointTag.VARIATIONS],
)
def get_variation_by_id(
    request: Request,
    variation_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
) -> GetVariationResponse:
    """Get registered variation given VRS ID.

    :param request: FastAPI request object
    :param variation_id: ID to look up
    :return: VRS variation if successful
    :raise HTTPException: if no variation matches provided ID
    """
    av: AnyVar = request.app.state.anyvar
    try:
        variation = av.get_object(variation_id)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Variation {variation_id} not found",
        ) from e

    return GetVariationResponse(messages=[], data=variation)


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

    inline_alleles = []
    if alleles:
        for allele in alleles:
            try:
                # TODO is this necessary now? search_alleles may return full objects already
                var_object = av.get_object(allele.id)
            except KeyError:
                continue
            inline_alleles.append(var_object)

    return SearchResponse(variations=inline_alleles)


@app.get(
    "/stats/{variation_type}",
    operation_id="getStats",
    summary="Summary statistics for registered variations",
    description="Retrieve summary statistics for registered variation objects.",
    tags=[EndpointTag.GENERAL],
)
def get_stats(
    request: Request,  # noqa: ARG001
    variation_type: Annotated[  # noqa: ARG001
        VariationStatisticType, Path(..., description="category of variation")
    ],
) -> AnyVarStatsResponse:
    """Get summary statistics for registered variants. Currently just returns totals.

    :param request: FastAPI request object
    :param variation_type: type of variation to summarize
    :return: total number of matching variants
    :raise HTTPException: if invalid variation type is requested, although FastAPI
        should block the request from going through in that case
    """
    raise HTTPException(
        status_code=HTTPStatus.NOT_IMPLEMENTED,
        detail="Stats not implemented for current storage backend",
    )
