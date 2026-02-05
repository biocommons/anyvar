"""Provide router for operations on stored objects"""

import json
import logging
from http import HTTPStatus
from typing import Annotated, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.params import Path
from fastapi.responses import JSONResponse, StreamingResponse
from ga4gh.vrs.dataproxy import DataProxyValidationError
from hgvs.exceptions import HGVSParseError
from pydantic import StrictStr

from anyvar.anyvar import AnyVar, ObjectNotFoundError
from anyvar.core import metadata, objects
from anyvar.mapping import liftover
from anyvar.restapi.dependencies import (
    RegistrationExtras,
    registration_extras,
)
from anyvar.restapi.schema import (
    AddAnnotationRequest,
    AddAnnotationResponse,
    AddMappingRequest,
    AddMappingResponse,
    GetAnnotationResponse,
    GetMappingResponse,
    GetObjectResponse,
    RegisterVariationResponse,
    TranslationResult,
    VariationRequest,
)
from anyvar.storage.base import IncompleteVrsObjectError
from anyvar.translate.base import TranslationError, Translator

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


def _register_variations(
    av: AnyVar,
    variation_requests: list[VariationRequest],
    add_annotations: RegistrationExtras,
) -> list[RegisterVariationResponse]:
    """Bulk register variations

    :param av: AnyVar instance
    :param variation_requests: Input variation requests to register
    :param add_annotations:
    :return: List of RegisterVariationResponse objects in the same order as the input.
        Variations that fail translation are not registered and are returned with null
        `object` and `object_id` fields. Registration or liftover failure messages may
        also be included in the `messages` field.
    """
    translation_results: list[TranslationResult] = []
    variations_to_store: list[objects.VrsObject] = []

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

        # add variant metadata
        messages: list[str] = []
        if add_annotations.add_timestamp:
            av.create_timestamp_annotation_if_missing(translation_result.variation.id)  # type: ignore (ID guaranteed to be present)
        if add_annotations.add_liftover:
            messages = (
                liftover.add_liftover_mapping(
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


@objects_router.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition  to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and ID is returned.",
)
def register_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
    add_annotations: Annotated[RegistrationExtras, Depends(registration_extras)],
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference."""
    av: AnyVar = request.app.state.anyvar

    responses: list[RegisterVariationResponse] = _register_variations(
        av, [variation], add_annotations
    )
    return responses[0]


@objects_router.put(
    "/variations",
    response_model_exclude_none=True,
    summary="Bulk register alleles or copy number objects",
    description="Provide a list of variation definitions to be normalized and registered with AnyVar. The response contains one result per input, in the same order. Variations that fail translation are not registered and are returned with null `object` and `object_id` fields. Registration or liftover failure messages may also be included in the `messages` field.",
)
def register_variations(
    request: Request,
    variations: Annotated[
        list[VariationRequest], Body(description="List of variations to register")
    ],
    add_annotations: Annotated[RegistrationExtras, Depends(registration_extras)],
) -> list[RegisterVariationResponse]:
    """Register multiple variations based on provided descriptions or references."""
    av: AnyVar = request.app.state.anyvar
    return _register_variations(av, variations, add_annotations)


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

    liftover_messages = liftover.add_liftover_mapping(
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


@objects_router.post(
    "/object/{vrs_id}/annotations",
    response_model_exclude_none=True,
    summary="Add annotation to a VRS Object",
    description="Provide an annotation to associate with a VRS object. The object MUST be registered with AnyVar before it can be annotated.",
)
def add_object_annotation(
    request: Request,
    vrs_id: Annotated[
        StrictStr, Path(..., description="VRS ID of variation to annotate")
    ],
    annotation_request: Annotated[
        AddAnnotationRequest,
        Body(
            description="Annotation to associate with the variation",
        ),
    ],
) -> AddAnnotationResponse:
    """Store an annotation for a VRS Object."""
    # Look up the VRS Object from the AnyVar store
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.VrsObject = _get_vrs_object(av, vrs_id)

    # Add the annotation to the database
    annotation_id: int | None = None
    try:
        annotation = metadata.Annotation(
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


@objects_router.get(
    "/object/{vrs_id}/annotations/{annotation_type}",
    response_model_exclude_none=True,
    summary="Retrieve annotations for a VRS Object",
    description="Retrieve annotations for a VRS Object by VRS ID and annotation type",
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
            detail=f"Failed to add annotation: {mapping_request}. {e}",
        ) from e

    return AddMappingResponse(
        source_object=source_vrs_obj,
        source_object_id=vrs_id,
        dest_object=dest_vrs_obj,
        dest_object_id=dest_vrs_id,
        mapping_type=mapping_type,
    )


@objects_router.get(
    "/object/{vrs_id}/mappings/{mapping_type}",
    response_model_exclude_none=True,
    summary="Retrieve mappings for a VRS Object",
    description="Retrieve mappings for a VRS Object by ID and mapping type",
)
def get_object_mapping(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    mapping_type: Annotated[
        metadata.VariationMappingType, Path(..., description="Mapping type")
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
