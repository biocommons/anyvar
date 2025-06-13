"""Defines utility functions used in routing handlers"""

import json
import re
from typing import Literal

from fastapi import Response
from fastapi.responses import JSONResponse
from ga4gh.vrs import models


async def parse_and_rebuild_response(response: Response) -> tuple[dict, Response]:
    """Convert a Response object to a dict, then re-build a new Response object (since parsing exhausts the response `body_iterator`).

    :param: response: the `Response` object to parse
    :return: a dictionary representation of the response
    """
    response_chunks = [chunk async for chunk in response.body_iterator]
    response_body_encoded = b"".join(response_chunks)
    response_body = response_body_encoded.decode("utf-8")
    response_json = json.loads(response_body)

    new_response = JSONResponse(
        content=response_json,
        status_code=response.status_code,
        media_type=response.media_type,
    )

    return response_json, new_response


def get_chromosome_from_aliases(aliases: list[str]) -> str | None:
    """Extract a string chromosome number from a list of aliases for a refget accession.

    :param: aliases: the list of aliases to search through for the chromosome number
    :return: a string chromosome number, prefixed by "chr"
    """
    reference_alias = None
    for alias in aliases:
        if "GRCh" in alias:
            reference_alias = alias
            break

    if reference_alias is None:
        return None

    # matches strings that start with a `:` character, then optionally the string "chr",
    # then a group of digits -> returns the digits
    # Example: "GRCh38:chr10" -> returns "10"
    match_group = re.search(r":(?:chr)?(\d+)$", reference_alias)
    chromosome_number: str | None = match_group.group(1) if match_group else None
    if chromosome_number is None:
        return None

    return f"chr{chromosome_number}"


def get_from_and_to_assemblies(aliases: dict) -> tuple[str | None, str | None]:
    """Determine which assembly we're starting from, and which we're lifting over to.

    Takes in a dictionary containing two lists of aliases, one for each supported reference assembly (GRCh37 and GRCh38):
    - If an assembly contains aliases for the variant, the variant is part of that assembly.
    - If *both* assemblies contain aliases for the variant, then it is identical across assemblies and requires no liftover.
    - If *neither* assembly contains the variant, something has gone wrong: raises an exception

    :param: aliases: A dictionary containing a list of aliases for both supported reference assemblies (GRCh37 and GRCh38)
    :return: A tuple containing the assembly we're converting from and the one we're converting to
    :raises: An Exception if neither assembly contains the variant
    """
    grch37, grch38 = sorted(aliases.keys())

    from_assembly = None
    to_assembly = None
    if aliases[grch37] and not aliases[grch38]:
        from_assembly = grch37
        to_assembly = grch38
    elif aliases[grch38] and not aliases[grch37]:
        from_assembly = grch38
        to_assembly = grch37
    elif not aliases[grch37] and not aliases[grch38]:
        raise Exception  # TODO - be more specific

    return from_assembly, to_assembly


def convert_range_to_int(
    range_object: models.Range, bound: Literal["lower", "upper"]
) -> int | None:
    """Convert a VRS Range object to an integer. If both an upper and lower bound are present, select for either the min or
    max of the Range as dictated by the value of the param `bound`. If one bound is missing, returns the one that is
    present. Returns `None` if both are missing.

    :param: range_object: the VRS Range object to convert
    :returns: An `int` representing the specified upper or lower value in the Range if possible, else `None` if neither bound is defined
    """
    lower, upper = range_object.root

    if bound == "lower":
        return lower or upper

    return upper or lower  # else: bound is 'upper'
