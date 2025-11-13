"""Defines utility functions used throughout AnyVar"""

import re

from anyvar.utils.types import VrsObject, vrs_object_class_map


def camel_case_to_snake_case(word: str, uppercase: bool = True) -> str:
    """Transform a string from camelCase (or PascalCase) into snake_case, optionally UPPER_CASED as well

    :param word: The word to transform
    :param uppercase: Whether or not to return the word in UPPER_SNAKE_CASE (defaults to true)
    :return: The provided word, transformed to snake case
    """
    snake_case_word: str = re.sub(r"(?<!^)(?=[A-Z])", "_", word)
    return snake_case_word.upper() if uppercase else snake_case_word.lower()


def build_vrs_object_from_dict(variant_dict: dict) -> VrsObject:
    """Construct a `VrsObject` class instance from a dictionary representation of one

    :param variant_dict: a dictionary representation of a `VrsObject` object
    :return: a `VrsObject` object
    """
    variant_type = variant_dict.get("type", "")
    return vrs_object_class_map[variant_type](**variant_dict)
