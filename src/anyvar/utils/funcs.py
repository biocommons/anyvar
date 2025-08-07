"""Defines utility functions used throughout AnyVar"""

from typing import Any


def get_nested_key(dict_object: dict, *keys: Any) -> Any:  # noqa: ANN401
    """Traverses the path of `keys` in `dict` and returns the final value.
    If any key does not exist, returns None.

    :param dict: The dictionary to traverse
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
