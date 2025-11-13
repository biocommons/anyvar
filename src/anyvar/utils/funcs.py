"""Defines utility functions used throughout AnyVar"""

import re

from anyvar.utils.types import VrsVariation, variation_class_map


def camel_case_to_snake_case(word: str, uppercase: bool = True) -> str:
    """Transform a string from camelCase or PascalCase into snake_case, optionally UPPER_CASED as well

    :param word: The word to transform
    :param uppercase: Whether or not to return the word in UPPER_SNAKE_CASE (defaults to true)
    :return: The provided word, transformed to snake case
    """
    snake_case_word: str = re.sub(r"(?<!^)(?=[A-Z])", "_", word)
    return snake_case_word.upper() if uppercase else snake_case_word


def build_vrs_variant_from_dict(variant_dict: dict) -> VrsVariation:
    """Construct a `VrsVariation` class instance from a dictionary representation of one

    :param variant_dict: a dictionary representation of a `VrsVariation` object
    :return: a `VrsVariation` object
    """
    variant_type = variant_dict.get("type", "")
    return variation_class_map[variant_type](**variant_dict)
