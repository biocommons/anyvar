"""Provide API routes relating to sequence reference operations"""

import logging
from typing import Annotated

from fastapi import APIRouter, Path, Request
from pydantic import StrictStr

from anyvar import AnyVar
from anyvar.core import objects
from anyvar.restapi.schema import GetObjectResponse
from anyvar.restapi.utils import get_vrs_object

_logger = logging.getLogger(__name__)

sequence_references_router = APIRouter()


@sequence_references_router.get(
    "/sequence_references/{vrs_id}",
    response_model_exclude_none=True,
    operation_id="getSequenceReference",
    summary="Retrieve a sequence reference",
    description="Gets a sequence reference by ID.",
)
def get_sequence_reference_by_id(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for object")],
) -> GetObjectResponse:
    """Get registered sequence reference given its VRS ID."""
    av: AnyVar = request.app.state.anyvar
    vrs_object: objects.SupportedVrsObject = get_vrs_object(av, vrs_id)
    return GetObjectResponse(messages=[], data=vrs_object)
