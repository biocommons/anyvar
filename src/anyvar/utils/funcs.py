"""Defines utility functions used throughout AnyVar"""

import re


def camel_case_to_snake_case(word: str, uppercase: bool = True) -> str:
    """Transform a string from camelCase (or PascalCase) into snake_case, optionally UPPER_CASED as well

    :param word: The word to transform
    :param uppercase: Whether or not to return the word in UPPER_SNAKE_CASE (defaults to true)
    :return: The provided word, transformed to snake case
    """
    snake_case_word: str = re.sub(r"(?<!^)(?=[A-Z])", "_", word)
    return snake_case_word.upper() if uppercase else snake_case_word.lower()
