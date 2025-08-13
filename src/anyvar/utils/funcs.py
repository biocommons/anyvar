"""Defines utility functions used throughout AnyVar"""

from anyvar.utils.types import VrsVariation, variation_class_map


def build_vrs_variant_from_dict(variant_dict: dict) -> VrsVariation:
    """Construct a `VrsVariation` class instance from a dictionary representation of one

    :param variant_dict: a dictionary representation of a `VrsVariation` object
    :return: a `VrsVariation` object
    """
    variant_type = variant_dict.get("type", "")
    return variation_class_map[variant_type](**variant_dict)
