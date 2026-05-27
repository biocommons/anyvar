"""Helper functions used by routers"""

from http import HTTPStatus

from fastapi import HTTPException

from anyvar import AnyVar
from anyvar.core import objects


def get_vrs_object(
    av: AnyVar,
    vrs_object_id: str,
    object_type: type[objects.SupportedVrsObject] | None = None,
) -> objects.SupportedVrsObject:
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
