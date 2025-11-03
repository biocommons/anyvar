"""Defines functions used to lift over variants between GRCh37 & GRCh38"""

import logging
from enum import Enum
from typing import TypeVar

from agct import (
    Assembly,
    Converter,
    Strand,
    get_converter,
    get_refget_id_from_seqinfo,
    get_seqinfo_from_refget_id,
)
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, normalize
from ga4gh.vrs.dataproxy import _DataProxy

from anyvar.storage.base_storage import Storage
from anyvar.utils.types import VariationMapping, VariationMappingType, VrsVariation

_logger = logging.getLogger(__name__)


class ReferenceAssembly(Enum):
    """Supported reference assemblies"""

    GRCH37 = "GRCh37"
    GRCH38 = "GRCh38"


class LiftoverError(Exception):
    """Indicates a failure to liftover a variant between GRCh37 & GRCh38"""

    base_error_message = "Unable to complete liftover"
    error_details = ""

    @classmethod
    def get_error_message(cls) -> str:
        """Return the error message associated with the Exception"""
        return (
            f"{cls.base_error_message}: {cls.error_details}"
            if cls.error_details
            else cls.base_error_message
        )


class MalformedInputError(LiftoverError):
    """Indicates a malformed variant input"""

    error_details = "Malformed variant input"


class UnsupportedVariantLocationTypeError(LiftoverError):
    """Indicates a variant with a 'location' type that is unsupported"""

    error_details = "Liftover is unsupported for variants without refget accession, start position, and end position"


class UnsupportedReferenceAssemblyError(LiftoverError):
    """Indicates a failure to retrieve alias data for a refget accession in any supported reference assembly."""

    error_details = "Could not resolve reference assembly - accession not found in any supported assembly"


class CoordinateConversionFailureError(LiftoverError):
    """Indicates a failure to lift over a variant's coordinate"""

    error_details = "Could not convert start and/or end position(s)"


class AmbiguousCoordinateConversionError(LiftoverError):
    """Indicates AnyVar cannot lift over a variant because its start and/or end coordinates mapped to multiple possible locations"""

    error_details = "Start and/or end positions mapped to multiple possible locations"


class AccessionConversionError(LiftoverError):
    """Indicates a failure to convert a variant's refget accession"""

    error_details = "Could not convert refget accession"


def _convert_coordinate(converter: Converter, chromosome: str, coordinate: int) -> int:
    """Convert an individual coordinate to another reference genome. If the conversion is unsuccessful, raises a `CoordinateConversionError`

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the coordinate is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> i.e. "chr10".
    :param coordinate: A single start or end coordinate. MUST be an `int`.
    :return: A converted coordinate value as an `int`
    :raises: A `CoordinateConversionFailureError` if the conversion returns no results.
    :raises: A `AmbiguousCoordinateConversionError` if the conversion returns more than one result.
    """
    converted_positions = converter.convert_coordinate(
        chromosome, coordinate, coordinate, Strand.POSITIVE
    )  # returns a list of tuples with a) the coordinate's chromosome number, b) the converted coordinate position, and c) the strand (Strand.POSITIVE or Strand.NEGATIVE)

    if len(converted_positions) > 1:
        raise AmbiguousCoordinateConversionError

    if (
        len(converted_positions) == 1
        and converted_positions[0].strand
        == Strand.POSITIVE  # TODO: Handle cases where coordinate converts to the negative strand. See Issue #197.
    ):
        return converted_positions[0].start

    raise CoordinateConversionFailureError


_PositionType = TypeVar("_PositionType", int, models.Range)


def convert_position(
    converter: Converter, chromosome: str, position: _PositionType
) -> _PositionType:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be a `models.Range` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> e.g. "chr10", "chrX", etc.
    :param position: A SequenceLocation start or end position. Can be a `models.Range` or an `int`.

    :return: A lifted-over position. Type (`models.Range` or `int`) will match that of `position`
    """
    # Handle int positions
    if isinstance(position, int):
        return _convert_coordinate(converter, chromosome, position)

    # Handle Range positions
    lower_bound, upper_bound = position.root
    lower_bound = (
        _convert_coordinate(converter, chromosome, lower_bound) if lower_bound else None
    )
    upper_bound = (
        _convert_coordinate(converter, chromosome, upper_bound) if upper_bound else None
    )
    return models.Range([lower_bound, upper_bound])


def get_liftover_variant(input_variant: VrsVariation) -> VrsVariation:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the converted variant as a VrsVariation.
    If liftover is unsuccessful, raise an Exception.

    :param input_variant: A `VrsVariation`.
    :return: The converted variant as a `VrsVariation`.
    :raises:
        - `MalformedInputError`:  If the `input_variant` is empty or otherwise falsy

        - `UnsupportedVariantLocationTypeError`: If the variant lacks a refget accession, start position or end position

        - `UnsupportedReferenceAssemblyError`: If the variant's accession was not found in any supported assembly

        - `CoordinateConversionFailureError`: If unable to lift over the variant's start and/or end position(s)

        - `AmbiguousCoordinateConversionError`: If variant's start and/or end position(s) map to multiple possible locations

        - `AccessionConversionError`: If unable to lift over the variant's refget accession
    """
    if not input_variant:
        raise MalformedInputError

    try:
        refget_accession = input_variant.location.sequenceReference.refgetAccession
        start_position = input_variant.location.start
        end_position = input_variant.location.end
    except AttributeError as err:
        raise UnsupportedVariantLocationTypeError from err

    seqinfo = get_seqinfo_from_refget_id(refget_accession)
    if not seqinfo:
        msg = f"Unable to get reference sequence ID for {refget_accession}"
        _logger.error(msg)
        raise UnsupportedReferenceAssemblyError(msg)
    assembly, chromosome = seqinfo
    to_assembly = Assembly.HG19 if assembly == Assembly.HG38 else Assembly.HG38
    converter = get_converter(assembly, to_assembly)

    # Get converted start/end positions. `convert_position` will raise a `CoordinateConversionError` if unsuccessful
    converted_start = convert_position(converter, chromosome, start_position)  # type: ignore (`converter` and `start_position` will always be valid)
    converted_end = convert_position(converter, chromosome, end_position)  # type: ignore (`converter` and `end_position` will always be valid)

    # Get converted refget_accession (without 'ga4gh:' prefix)
    new_alias = f"{to_assembly}:{chromosome}"
    converted_refget_accession = get_refget_id_from_seqinfo(to_assembly, chromosome)
    if not converted_refget_accession:
        # should be impossible
        _logger.error(
            "Unable to convert constructed sequence ID `%s` into refgetAccession",
            new_alias,
        )
        raise AccessionConversionError

    # Build the converted location object
    converted_variant_location = models.SequenceLocation(
        start=converted_start,
        end=converted_end,
        type="SequenceLocation",
        sequenceReference=models.SequenceReference(
            type="SequenceReference", refgetAccession=converted_refget_accession
        ),
    )
    ga4gh_identify(converted_variant_location, in_place="always")

    # Build the liftover variant object
    # Start by copying the original variant
    converted_variant = input_variant.model_copy(deep=True)

    # Replace the location with the lifted-over version
    converted_variant.location = converted_variant_location

    # Recompute object ID
    converted_variant.digest = None
    converted_variant.id = ga4gh_identify(converted_variant, in_place="always")

    return converted_variant


def add_liftover_mapping(
    variation: VrsVariation, storage: Storage, dataproxy: _DataProxy
) -> list[str] | None:
    """Perform liftover between GRCh37 <-> GRCh38. Store mappings between the original and lifted-over variants.

    Don't register lifted-over variant or mappings if
    * liftover fails in either direction
    * liftover is ambiguous in either direction
    * liftover fails to roundtrip accurately

    This function is intended to be quite directly 'user-facing', i.e. it catches and
    suppresses major error cases and communicates results as they are to be transmitted
    in the REST API routes. Library users hoping for more direct control will want to
    employ ``get_liftover_variant`` to perform liftover and make their own decisions
    about when to register objects and mappings.

    :param variation: variation to attempt liftover upon
    :param storage: Storage instance
    :param dataproxy: SeqRepo DataProxy instance, for normalizing lifted-over alleles
    :return: list of messages describing warnings or failures, or ``None`` if completely successful
    """
    input_vrs_id: str = variation.id  # type: ignore
    try:
        lifted_over_variant = get_liftover_variant(variation)
        reverse_liftover_variant = get_liftover_variant(lifted_over_variant)
    except LiftoverError as e:
        _logger.exception(
            "Encountered error during liftover of variation `%s`",
            variation,
        )
        return [e.get_error_message()]

    if reverse_liftover_variant.id != variation.id:
        return [
            f"{LiftoverError.base_error_message}: Roundtripped lifted-over id `{reverse_liftover_variant.id}` does not match initial value of {input_vrs_id}"
        ]

    normalized_lifted_over_variant = normalize(
        lifted_over_variant, data_proxy=dataproxy
    )
    normalized_lifted_over_variant_id: str = normalized_lifted_over_variant.id  # type: ignore
    storage.add_objects([normalized_lifted_over_variant])
    storage.add_mapping(
        VariationMapping(
            source_id=input_vrs_id,
            dest_id=normalized_lifted_over_variant_id,
            mapping_type=VariationMappingType.LIFTOVER,
        )
    )
    storage.add_mapping(
        VariationMapping(
            source_id=normalized_lifted_over_variant_id,
            dest_id=input_vrs_id,
            mapping_type=VariationMappingType.LIFTOVER,
        )
    )
    return None
