"""Defines utility functions"""

import json
import re
from typing import cast

from agct import Converter, Genome, Strand
from fastapi import Response
from fastapi.responses import JSONResponse, StreamingResponse
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.enderef import vrs_enref

from anyvar.utils.types import VrsObject, variation_class_map


class AliasRetrievalError(Exception):
    """Indicates a failure to retrieve alias data for a refget accession in any supported reference assembly."""


class AmbiguousReferenceAssemblyError(Exception):
    """Indicates a failure to determine which reference assembly a variant is one due to alias matches in multiple reference assemblies, making the result ambiguous"""


async def parse_and_rebuild_response(
    response: StreamingResponse,
) -> tuple[dict, Response]:
    """Convert a `Response` object to a dict, then re-build a new Response object (since parsing exhausts the Response `body_iterator`).

    :param response: the `Response` object to parse
    :return: a dictionary representation of the Response
    """
    response_chunks: list[bytes] = [
        cast(bytes, chunk) async for chunk in response.body_iterator
    ]
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

    :param aliases: the list of aliases to search through for the chromosome number
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


def get_from_and_to_assemblies(aliases: dict) -> tuple[str, str]:
    """Determine which assembly we're starting from, and which we're lifting over to.

    Takes in a dictionary containing two lists of aliases, one for each supported reference assembly (GRCh37 and GRCh38):
    - If an assembly contains aliases for the variant, the variant is part of that assembly.
    - If *both* assemblies contain aliases for the variant, then it is identical across assemblies and requires no liftover.
    - If *neither* assembly contains the variant, something has gone wrong: raises an exception

    :param aliases: A dictionary containing a list of aliases for both supported reference assemblies (GRCh37 and GRCh38)
    :return: A tuple containing the assembly we're converting from and the one we're converting to
    :raise: A ReferenceAssemblyResolutionError if neither assembly contains the variant
    """
    grch37, grch38 = sorted(aliases.keys())

    if aliases[grch37] and not aliases[grch38]:
        from_assembly = grch37
        to_assembly = grch38
    elif aliases[grch38] and not aliases[grch37]:
        from_assembly = grch38
        to_assembly = grch37
    elif not aliases[grch37] and not aliases[grch38]:
        raise AliasRetrievalError
    else:
        raise AmbiguousReferenceAssemblyError

    return from_assembly, to_assembly


def convert_position(
    converter: Converter, chromosome: str, position: list | int
) -> list | int:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be a `List` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of the prefix "chr" plus a number, i.e. "chr10".
    :param position: A SequenceLocation start or end position. Can be a `List` or an `int`.

    :return: A lifted-over position. Type (`List` or `int`) will match that of `position`
    """
    if isinstance(position, int):
        return converter.convert_coordinate(chromosome, position, Strand.POSITIVE)[0][1]

    lower, upper = position
    lower = (
        converter.convert_coordinate(chromosome, lower, Strand.POSITIVE)[0][1]
        if lower
        else None
    )
    upper = (
        converter.convert_coordinate(chromosome, upper, Strand.POSITIVE)[0][1]
        if upper
        else None
    )
    return [lower, upper]


def get_liftover_annotation(
    variation_object: dict, seqrepo_dataproxy: _DataProxy
) -> str:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the string identifier for the converted variant.
    If liftover is unsuccessful, return a string error message instead.

    :param variation_object: A dictionary representation of a `VrsVariation`.
    :param seqrepo_dataproxy: A SeqrepoDataproxy instance.
    :return: The string ga4gh identifier of the lifted-over variant on success; else a string error message indicating why liftover was unsuccessful on failure.
    """
    error_msg = "Unable to complete liftover"

    if not variation_object:
        return f"{error_msg}: no variation found"

    # Get variant start position, end position, and refget accession - liftover is currently unsupported without these
    refget_accession = (
        variation_object.get("location", {})
        .get("sequenceReference", {})
        .get("refgetAccession")
    )
    start_position = variation_object.get("location", {}).get("start")
    end_position = variation_object.get("location", {}).get("end")
    if not refget_accession or not start_position or not end_position:
        return f"{error_msg}: liftover is unsupported for variants without refget accession, start position and end position"

    # Determine which assembly we're converting from/to
    prefixed_accession = f"ga4gh:{refget_accession}"

    grch37 = "GRCh37"
    grch38 = "GRCh38"
    aliases = {
        grch37: list(
            seqrepo_dataproxy.translate_sequence_identifier(prefixed_accession, grch37)
        ),
        grch38: list(
            seqrepo_dataproxy.translate_sequence_identifier(prefixed_accession, grch38)
        ),
    }

    from_assembly = None
    to_assembly = None
    try:
        from_assembly, to_assembly = get_from_and_to_assemblies(aliases)
    except AliasRetrievalError:
        return f"{error_msg}: could not resolve reference assembly - alias data not found in any supported assembly"
    except AmbiguousReferenceAssemblyError:
        return f"{error_msg}: could not resolve reference assembly - alias data found in multiple supported assemblies"

    # Determine which chromosome the variant is on
    chromosome = get_chromosome_from_aliases(aliases.get(from_assembly, []))
    if not chromosome:
        return f"{error_msg}: unable to resolve variant's chromosome"

    # Begin liftover conversion
    assembly_map = {grch37: Genome.HG19, grch38: Genome.HG38}
    converter = Converter(assembly_map[from_assembly], assembly_map[to_assembly])

    # Get converted start/end positions
    converted_start = None
    converted_end = None
    try:
        converted_start = convert_position(converter, chromosome, start_position)
        converted_end = convert_position(converter, chromosome, end_position)
    except Exception:
        return f"{error_msg}: could not convert start and/or end position(s)"

    # Get converted refget_accession (without 'ga4gh:' prefix)
    new_alias = f"{to_assembly}:{chromosome}"
    converted_refget_accession = seqrepo_dataproxy.translate_sequence_identifier(
        new_alias, "ga4gh"
    )[0].split("ga4gh:")[1]
    if not converted_refget_accession:
        return f"{error_msg}: could not convert refget accession"

    # Build the converted location dict
    converted_variation_location = {
        "start": converted_start,
        "end": converted_end,
        "id": None,
        "sequenceReference": {
            "type": "SequenceReference",
            "refgetAccession": converted_refget_accession,
        },
    }

    # Build the liftover variation object w/ converted location
    converted_variation_dict = variation_object
    converted_variation_dict["location"] = converted_variation_location
    # Get rid of the identifiers since these were from the original variation object and we need to re-compute them
    converted_variation_dict["digest"] = None
    converted_variation_dict["id"] = None

    # Convert the dict into a VrsObject class instance so we can compute the identifiers
    converted_variation_object: VrsObject = variation_class_map[
        variation_object.get("type", "")
    ](**converted_variation_dict)

    # Compute the identifiers and return the ga4gh id of the converted variant
    return vrs_enref(converted_variation_object, return_id_obj_tuple=True)[0]
