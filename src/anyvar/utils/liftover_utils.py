"""Defines functions used to lift over variants between GRCh37 & GRCh38"""

import re

from agct import Converter, Genome, Strand
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.enderef import vrs_deref, vrs_enref

from anyvar.utils.types import VrsObject, VrsVariation, variation_class_map


class MalformedInputError(Exception):
    """Indicates a malformed variant input"""


class UnsupportedVariantLocationTypeError(Exception):
    """Indicates a variant with a 'location' type that is unsupported"""


class UnsupportedReferenceAssemblyError(Exception):
    """Indicates a failure to retrieve alias data for a refget accession in any supported reference assembly."""


class AmbiguousReferenceAssemblyError(Exception):
    """Indicates a failure to determine which reference assembly a variant is one due to alias matches in multiple reference assemblies, making the result ambiguous"""


class ChromosomeResolutionError(Exception):
    """Indicates a failure to resolve a variant's chromosome"""


class CoordinateConversionError(Exception):
    """Indicates a failure to lift over a variant's coordinate"""


class AccessionConversionError(Exception):
    """Indicates a failure to convert a variant's refget accession"""


liftover_error_prefix = "Unable to complete liftover"


LIFTOVER_ERROR_ANNOTATIONS = {
    MalformedInputError: f"{liftover_error_prefix}: malformed variant input",
    UnsupportedVariantLocationTypeError: f"{liftover_error_prefix}: liftover is unsupported for variants without refget accession, start position and end position",
    UnsupportedReferenceAssemblyError: f"{liftover_error_prefix}: could not resolve reference assembly - accession not found in any supported assembly",
    AmbiguousReferenceAssemblyError: f"{liftover_error_prefix}: could not resolve reference assembly - accession found in multiple supported assemblies",
    ChromosomeResolutionError: f"{liftover_error_prefix}: unable to resolve variant's chromosome",
    CoordinateConversionError: f"{liftover_error_prefix}: could not convert start and/or end position(s)",
    AccessionConversionError: f"{liftover_error_prefix}: could not convert refget accession",
}


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
    # then a group of digits OR the letters "X" or "Y" -> returns the group
    # Example:  "GRCh38:chr10" -> returns "10"
    #           "GRCh38:chrX" -> returns "X"
    match_group = re.search(r":(?:chr)?(\d+|[XY])$", reference_alias)
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


def _convert_coordinate(converter: Converter, chromosome: str, coordinate: int) -> int:
    """Convert an individual coordinate to another reference genome. If the conversion is unsuccessful, raises a `CoordinateConversionError`

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the coordinate is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> i.e. "chr10".
    :param coordinate: A single start or end coordinate. MUST be an `int`.

    :return: A converted coordinate value as an `int`
    :raises: A `CoordinateConversionError` if the conversion is unsuccessful.
    """
    converted_position = converter.convert_coordinate(
        chromosome, coordinate, Strand.POSITIVE
    )
    if converted_position:
        return converted_position[0][1]
    raise CoordinateConversionError


def convert_position(
    converter: Converter, chromosome: str, position: list | int
) -> list | int:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be a `list` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> i.e. "chr10".
    :param position: A SequenceLocation start or end position. Can be a `list` or an `int`.

    :return: A lifted-over position. Type (`list` or `int`) will match that of `position`
    """
    # Handle int positions
    if isinstance(position, int):
        return _convert_coordinate(converter, chromosome, position)

    # Handle Range positions
    lower_bound, upper_bound = position
    lower_bound = (
        _convert_coordinate(converter, chromosome, lower_bound) if lower_bound else None
    )
    upper_bound = (
        _convert_coordinate(converter, chromosome, upper_bound) if upper_bound else None
    )
    return [lower_bound, upper_bound]


def get_liftover_variant(
    variant_object: dict, seqrepo_dataproxy: _DataProxy
) -> VrsVariation:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the converted variant as a VrsObject.
    If liftover is unsuccessful, raise an Exception.

    :param variant_object: A dictionary representation of a `VrsVariation`.
    :param seqrepo_dataproxy: A `SeqrepoDataproxy` instance.
    :return: The converted variant as a `VrsObject`.
    :raises:
        - `MalformedInputError`:  If the `variant_object` is empty or otherwise falesy

        - `UnsupportedVariantLocationTypeError`: If the variant lacks a refget accession, start position or end position

        - `UnsupportedReferenceAssemblyError`: If the variant's accession was not found in any supported assembly

        - `AmbiguousReferenceAssemblyError`: If the variant's accession was found in multiple supported assemblies

        - `ChromosomeResolutionError`: If unable to resolve variant's chromosome

        - `CoordinateConversionError`: If unable to lift over the variant's start and/or end position(s)

        - `AccessionConversionError`: If unable to lift over the variant's refget accession
    """
    if not variant_object:
        raise MalformedInputError

    # Get variant start position, end position, and refget accession - liftover is currently unsupported without these
    refget_accession = (
        variant_object.get("location", {})
        .get("sequenceReference", {})
        .get("refgetAccession")
    )
    start_position = variant_object.get("location", {}).get("start")
    end_position = variant_object.get("location", {}).get("end")
    if not refget_accession or not start_position or not end_position:
        raise UnsupportedVariantLocationTypeError

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
    from_assembly, to_assembly = get_from_and_to_assemblies(
        aliases
    )  # Will raise an `UnsupportedReferenceAssemblyError` or `AmbiguousReferenceAssemblyError` if unsuccessful

    # Determine which chromosome the variant is on
    chromosome = get_chromosome_from_aliases(aliases.get(from_assembly, []))
    if not chromosome:
        raise ChromosomeResolutionError

    # Begin liftover conversion
    assembly_map = {grch37: Genome.HG19, grch38: Genome.HG38}
    converter = Converter(assembly_map[from_assembly], assembly_map[to_assembly])

    # Get converted start/end positions. `convert_position` will raise a `CoordinateConversionError` if unsuccessful
    converted_start = convert_position(converter, chromosome, start_position)
    converted_end = convert_position(converter, chromosome, end_position)

    # Get converted refget_accession (without 'ga4gh:' prefix)
    new_alias = f"{to_assembly}:{chromosome}"
    converted_refget_accession = seqrepo_dataproxy.translate_sequence_identifier(
        new_alias, "ga4gh"
    )[0].split("ga4gh:")[1]
    if not converted_refget_accession:
        raise AccessionConversionError

    # Build the converted location dict
    converted_variant_location = {
        "start": converted_start,
        "end": converted_end,
        "id": None,
        "sequenceReference": {
            "type": "SequenceReference",
            "refgetAccession": converted_refget_accession,
        },
    }

    # Build the liftover variant object
    # Start by copying the original variant
    converted_variant_dict = variant_object

    # Replace the location with the lifted-over version
    converted_variant_dict["location"] = converted_variant_location

    # Get rid of the identifiers since these were from the original variant object and we need to re-compute them
    converted_variant_dict["digest"] = None
    converted_variant_dict["id"] = None

    # Convert the dict into a VrsObject class instance so we can compute the identifiers
    converted_variant_object: VrsObject = variation_class_map[
        variant_object.get("type", "")
    ](**converted_variant_dict)

    # Compute the identifiers
    object_store = {}
    enreffed_variant = vrs_enref(
        o=converted_variant_object,
        object_store=object_store,
        return_id_obj_tuple=False,
    )

    # return the dereffed lifted-over variant
    return vrs_deref(o=enreffed_variant, object_store=object_store)


def get_liftover_error_annotation(error: Exception) -> str:
    """Get the annotation value for a failed liftover"""
    return LIFTOVER_ERROR_ANNOTATIONS.get(
        type(error), f"{liftover_error_prefix}: an unknown error occurred"
    )
