"""Provide API routes relating to sequence location operations"""

import logging
from typing import Annotated

from fastapi import APIRouter, Path, Request
from pydantic import StrictStr

from anyvar import AnyVar
from anyvar.core import objects
from anyvar.restapi.schema import GetObjectResponse
from anyvar.restapi.utils import get_vrs_object

_logger = logging.getLogger(__name__)

sequence_locations_router = APIRouter()


@sequence_locations_router.get(
    "/sequence_locations/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="getSequenceLocation",
    summary="Retrieve a sequence location",
    description="Gets a sequence location by ID.",
)
def get_sequence_location_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for object")],
) -> GetObjectResponse:
    """Get registered sequence location given its VRS ID."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=vrs_object)
