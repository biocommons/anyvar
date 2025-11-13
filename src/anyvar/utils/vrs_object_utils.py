"""Util functions related to vrs objects"""

from anyvar.utils.types import VrsObject, vrs_object_class_map


def build_vrs_object_from_dict(vrs_object_dict: dict) -> VrsObject:
    """Construct a `VrsObject` class instance from a dictionary representation of one

    :param variant_dict: a dictionary representation of a `VrsObject` object
    :return: a `VrsObject` object
    """
    variant_type = vrs_object_dict.get("type", "")
    return vrs_object_class_map[variant_type](**vrs_object_dict)
