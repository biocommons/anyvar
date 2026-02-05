"""Provide FastAPI route dependencies."""

from typing import NamedTuple


class RegistrationExtras(NamedTuple):
    """Optional mappings/annotations to add at registration"""

    add_timestamp: bool
    add_liftover: bool


def registration_extras(
    add_timestamp: bool = True, add_liftover: bool = True
) -> RegistrationExtras:
    """Provide args for extra annotations/mappings at registration

    :param add_timestamp: whether to attempt to add timestamp annotation
    :param add_liftover: whether to attempt to add liftover mapping and lifted-over variant
    :return: Route args for the above
    """
    return RegistrationExtras(add_timestamp=add_timestamp, add_liftover=add_liftover)
