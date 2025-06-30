"""Defines utility functions"""

import json
import os
import re
from enum import Enum
from typing import cast

from agct import Converter, Genome, Strand
from fastapi import Response
from fastapi.responses import JSONResponse, StreamingResponse
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.enderef import vrs_deref, vrs_enref
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from anyvar.utils.types import VrsObject, variation_class_map


class UnsupportedReferenceAssemblyError(Exception):
    """Indicates a failure to retrieve alias data for a refget accession in any supported reference assembly."""


class AmbiguousReferenceAssemblyError(Exception):
    """Indicates a failure to determine which reference assembly a variant is one due to alias matches in multiple reference assemblies, making the result ambiguous"""


class StrandResolutionError(Exception):
    """Indicates a failure to determine which strand an incoming variant is on"""


liftover_error_prefix = "Unable to complete liftover"


class LiftoverError(str, Enum):
    """Errors that can occur during variant liftover"""

    INPUT_ERROR = "Input Error"
    UNSUPPORTED_VARIANT_LOCATION_TYPE = "Unsupported Variant Location Type"
    UNSUPPORTED_REFERENCE_ASSEMBLY = "Unsupported Reference Assembly Error"
    AMBIGUOUS_REFERENCE_ASSEMBLY = "Ambiguous Reference Assembly Error"
    CHROMOSOME_RESOLUTION_ERROR = "Chromosome Resolution Error"
    STRAND_RESOLUTION_ERROR = "Strand Resolution Error"
    COORDINATE_CONVERSION_ERROR = "Coordinate Conversion Error"
    ACCESSION_CONVERSION_ERROR = "Accession Conversion Error"


LIFTOVER_ERROR_ANNOTATIONS = {
    LiftoverError.INPUT_ERROR: f"{liftover_error_prefix}: no variation found",
    LiftoverError.UNSUPPORTED_VARIANT_LOCATION_TYPE: f"{liftover_error_prefix}: liftover is unsupported for variants without refget accession, start position and end position",
    LiftoverError.UNSUPPORTED_REFERENCE_ASSEMBLY: f"{liftover_error_prefix}: could not resolve reference assembly - accession not found in any supported assembly",
    LiftoverError.AMBIGUOUS_REFERENCE_ASSEMBLY: f"{liftover_error_prefix}: could not resolve reference assembly - accession found in multiple supported assemblies",
    LiftoverError.CHROMOSOME_RESOLUTION_ERROR: f"{liftover_error_prefix}: unable to resolve variant's chromosome",
    LiftoverError.STRAND_RESOLUTION_ERROR: f"{liftover_error_prefix}: unable to resolve variant's strand",
    LiftoverError.COORDINATE_CONVERSION_ERROR: f"{liftover_error_prefix}: could not convert start and/or end position(s)",
    LiftoverError.ACCESSION_CONVERSION_ERROR: f"{liftover_error_prefix}: could not convert refget accession",
}


async def parse_and_rebuild_response(
    response: StreamingResponse,
) -> tuple[dict, Response]:
    """Convert a `Response` object to a dict, then re-build a new Response object (since parsing exhausts the Response `body_iterator`).

    :param response: the `Response` object to parse
    :return: a tuple with a dictionary representation of the Response and a new `Response` object
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

    return (response_json, new_response)


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
        raise UnsupportedReferenceAssemblyError
    else:
        raise AmbiguousReferenceAssemblyError

    return from_assembly, to_assembly


def convert_position(
    converter: Converter, chromosome: str, position: list | int, strand: Strand
) -> list | int:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be a `list` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of the prefix "chr" plus a number, i.e. "chr10".
    :param position: A SequenceLocation start or end position. Can be a `list` or an `int`.
    :param strand: The strand on which the variant is found (either Strand.POSITIVE or Strand.NEGATIVE)

    :return: A lifted-over position. Type (`list` or `int`) will match that of `position`
    """
    if isinstance(position, int):
        return converter.convert_coordinate(chromosome, position, strand)[0][1]

    lower, upper = position
    lower = (
        converter.convert_coordinate(chromosome, lower, strand)[0][1] if lower else None
    )
    upper = (
        converter.convert_coordinate(chromosome, upper, strand)[0][1] if upper else None
    )
    return [lower, upper]


def get_strand(
    prefixed_accession: str,
    start_position: int | list,
    end_position: int | list,
    seqrepo_dataproxy: _DataProxy,
) -> Strand | None:
    """Retrieve the strand (POSITIVE or NEGATIVE) of a variant based on its accession, start position, and end position.

    :param refget_accession: The variant's refget_accession
    :param start_position: The variant's start position. May be an `int` or a `list`
    :param end_position: The variant's end position. May be an `int` or a `list`
    :return: The Strand (POSITIVE or NEGATIVE) that the variant is one
    :raise: StrandResolutionError if the strand cannot be determined
    """
    # Get the refseq version of the accession
    refseq_accession_aliases = seqrepo_dataproxy.translate_sequence_identifier(
        prefixed_accession, "refseq"
    )
    accession = (
        refseq_accession_aliases[0].removeprefix("refseq:")
        if refseq_accession_aliases
        else None
    )
    if accession is None:
        raise StrandResolutionError(
            "Unable to find a refseq alias for variant's accession"
        )

    # Convert ranged positions into ints (using the lowest provided start position and highest provided end position)
    if type(start_position) is list:
        start_position = (
            start_position[0] if start_position[0] is not None else start_position[1]
        )
    if type(end_position) is list:
        end_position = (
            end_position[1] if end_position[1] is not None else end_position[0]
        )

    # Parse UTA_DB_URL into the {base URL} + {schema name}
    uta_db_url = os.environ.get("UTA_DB_URL", "")
    match = re.match(r"^(postgresql://[^/]+/[^/]+)(?:/([^/]+))?$", uta_db_url)
    if match:
        base_url = match.group(1)  # e.g., "postgresql://.../uta"
        schema = match.group(2) or None  # e.g., "uta_20210129b" or None
    else:
        raise StrandResolutionError("Invalid UTA_DB_URL format")

    engine = create_engine(base_url)
    connection: Connection = engine.connect()
    with connection as connection:
        connection.execute(text("SET search_path TO :schema"), {"schema": schema})

        query = text("""
            SELECT DISTINCT(alt_strand)
            FROM tx_exon_aln_v
            WHERE alt_ac = ':refget_accession'
            AND :start_position BETWEEN alt_start_i AND alt_end_i
            AND :end_position BETWEEN alt_start_i AND alt_end_i;
        """)

        result = connection.execute(
            query,
            {
                "refget_accession": accession,
                "start_position": start_position,
                "end_position": end_position,
            },
        )

        if result is None:
            raise StrandResolutionError("No strand results found")

        strand_values = [row[0] for row in result.fetchall()]
        if not strand_values:
            raise StrandResolutionError("No strand results")

        strand_value = strand_values[0]
        if strand_value < 0:
            return Strand.NEGATIVE
        return Strand.POSITIVE


def get_liftover_annotation(
    variation_object: dict, seqrepo_dataproxy: _DataProxy
) -> str | dict:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the string identifier for the converted variant.
    If liftover is unsuccessful, return a string error message instead.

    :param variation_object: A dictionary representation of a `VrsVariation`.
    :param seqrepo_dataproxy: A SeqrepoDataproxy instance.
    :return: The string ga4gh identifier of the lifted-over variant on success; else a string error message indicating why liftover was unsuccessful on failure.
    """
    if not variation_object:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.INPUT_ERROR]

    # Get variant start position, end position, and refget accession - liftover is currently unsupported without these
    refget_accession = (
        variation_object.get("location", {})
        .get("sequenceReference", {})
        .get("refgetAccession")
    )
    start_position = variation_object.get("location", {}).get("start")
    end_position = variation_object.get("location", {}).get("end")
    if not refget_accession or not start_position or not end_position:
        return LIFTOVER_ERROR_ANNOTATIONS[
            LiftoverError.UNSUPPORTED_VARIANT_LOCATION_TYPE
        ]

    # Determine which assembly we're converting from/to
    prefixed_accession = f"ga4gh:{refget_accession}"

    grch37 = "GRCh37"
    grch38 = "GRCh38"
    accession_aliases = {
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
        from_assembly, to_assembly = get_from_and_to_assemblies(accession_aliases)
    except UnsupportedReferenceAssemblyError:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.UNSUPPORTED_REFERENCE_ASSEMBLY]
    except AmbiguousReferenceAssemblyError:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.AMBIGUOUS_REFERENCE_ASSEMBLY]

    # Determine which chromosome the variant is on
    chromosome = get_chromosome_from_aliases(accession_aliases.get(from_assembly, []))
    if not chromosome:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.CHROMOSOME_RESOLUTION_ERROR]

    # Determine which strand the variant is on
    try:
        strand = get_strand(
            prefixed_accession, start_position, end_position, seqrepo_dataproxy
        )
    except StrandResolutionError:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.STRAND_RESOLUTION_ERROR]

    # Begin liftover conversion
    assembly_map = {grch37: Genome.HG19, grch38: Genome.HG38}
    converter = Converter(assembly_map[from_assembly], assembly_map[to_assembly])

    # Get converted start/end positions
    converted_start = None
    converted_end = None
    try:
        converted_start = convert_position(
            converter, chromosome, start_position, strand
        )
        converted_end = convert_position(converter, chromosome, end_position, strand)
    except Exception:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.COORDINATE_CONVERSION_ERROR]

    # Get converted refget_accession (without 'ga4gh:' prefix)
    new_alias = f"{to_assembly}:{chromosome}"
    converted_refget_accession = seqrepo_dataproxy.translate_sequence_identifier(
        new_alias, "ga4gh"
    )[0].split("ga4gh:")[1]
    if not converted_refget_accession:
        return LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.ACCESSION_CONVERSION_ERROR]

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

    # Compute the identifiers
    object_store = {}
    enreffed_variant = vrs_enref(
        o=converted_variation_object,
        object_store=object_store,
        return_id_obj_tuple=False,
    )

    # deref and convert back to a dict for storage
    return vrs_deref(o=enreffed_variant, object_store=object_store).model_dump()
