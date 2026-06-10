"""Provide router for operations on stored objects"""

import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.params import Path
from pydantic import StrictStr

from anyvar.anyvar import AnyVar, ObjectNotFoundError
from anyvar.core import metadata, objects
from anyvar.restapi.schema import (
    AddExtensionRequest,
    AddExtensionResponse,
    AddMappingRequest,
    AddMappingResponse,
    GetExtensionResponse,
    GetMappingResponse,
    GetObjectResponse,
)
from anyvar.restapi.utils import get_vrs_object

_logger = logging.getLogger(__name__)

objects_router = APIRouter()


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
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)
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
            example={"name": "source_dataset", "value": "gnomAD_v4.1"},
        ),
    ],
) -> AddExtensionResponse:
    """Store an extension for a VRS Object."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)

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


@objects_router.delete(
    "/object/{vrs_id}/extensions/{extension_name}",
    response_model_exclude_none=True,
    summary="Delete extensions for a VRS object.",
    description="Delete all extensions under a given extension name for a VRS object. Returns idempotently regardless of whether there were extensions under that name for the object. Return 404 NOT FOUND if no known object matches given object ID.",
    status_code=HTTPStatus.NO_CONTENT,
)
def delete_object_extensions(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for VRS Object")],
    extension_name: Annotated[StrictStr, Path(..., description="Extension name")],
) -> Response:
    """Delete extensions associated with a VRS object."""
    av: AnyVar = request.app.state.anyvar
    try:
        av.delete_object_extensions(vrs_id, extension_name)
    except ObjectNotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Object `{vrs_id}` not found"
        ) from e
    return Response(status_code=HTTPStatus.NO_CONTENT)  # blank response if successful


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
