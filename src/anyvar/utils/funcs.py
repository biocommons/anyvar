"""Defines utility functions used throughout AnyVar"""

from typing import Any

from anyvar.utils.types import VrsVariation, variation_class_map


def get_nested_key(dict_object: dict, *keys: Any) -> Any:  # noqa: ANN401
    """Traverses the path of `keys` in `dict` and returns the final value.
    If any key does not exist, returns None.

    :param dict: The dictionary to traverse.
    :param keys: The keys that will be used to traverse the dictionary, in the order they should be used.
    :returns: The final value in the dictionary traversal, if all keys exist; else None.
    """
    for index, key in enumerate(keys):
        if dict_object and key in dict_object:
            if index == len(keys) - 1:
                return dict_object[key]
            dict_object = dict_object[key]
        else:
            return None
    return None


def get_nested_attribute(class_object: object, *attributes: Any) -> Any:  # noqa: ANN401
    """Traverses the path of nested `attributes` in `class_object` and returns the final value.
    If any key does not exist, returns None.

    :param class_object: The class_object to traverse.
    :param attributes: The attributes that will be used to traverse the attributes of the class_object, in the order they should be used.
    :returns: The final value in the property traversal, if all attributes exist; else None.
    """
    for attr in attributes:
        try:
            class_object = getattr(class_object, attr)
        except AttributeError:
            return None
    return class_object


def build_vrs_variant_from_dict(variant_dict: dict) -> VrsVariation:
    """Construct a `VrsVariation` class instance from a dictionary representation of one"""
    variant_type = variant_dict.get("type", "")
    return variation_class_map[variant_type](**variant_dict)
