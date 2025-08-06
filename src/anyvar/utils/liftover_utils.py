"""Defines functions used to lift over variants between GRCh37 & GRCh38"""

import copy
from enum import Enum
from typing import TypeVar

from agct import Converter, Strand
from bioutils.accessions import chr22XY
from ga4gh.vrs import models
from ga4gh.vrs.enderef import vrs_deref, vrs_enref

from anyvar.anyvar import AnyAnnotation, AnyVar
from anyvar.utils.funcs import get_nested_attribute
from anyvar.utils.types import VrsVariation, variation_class_map


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


class AmbiguousReferenceAssemblyError(LiftoverError):
    """Indicates a failure to determine which reference assembly a variant is one due to alias matches in multiple reference assemblies, making the result ambiguous"""

    error_details = "Could not resolve reference assembly - accession found in multiple supported assemblies"


class ChromosomeResolutionError(LiftoverError):
    """Indicates a failure to resolve a variant's chromosome"""

    error_details = "Unable to resolve variant's chromosome"


class CoordinateConversionFailureError(LiftoverError):
    """Indicates a failure to lift over a variant's coordinate"""

    error_details = "Could not convert start and/or end position(s)"


class AmbiguousCoordinateConversionError(LiftoverError):
    """Indicates a failure to lift over a variant's coordinate"""

    error_details = "Variant coordinates mapped to multiple possible locations"


class AccessionConversionError(LiftoverError):
    """Indicates a failure to convert a variant's refget accession"""

    error_details = "Could not convert refget accession"


_PositionType = TypeVar("_PositionType", int, models.Range)


def _build_position_list(
    start_positions: list[int] | list[None],
    end_positions: list[int] | list[None],
) -> list[list[int | None]]:
    if len(start_positions) == 1 and len(end_positions) > 1:
        return [[start_positions[0], end] for end in end_positions]
    elif len(end_positions) == 1 and len(start_positions) > 1:  # noqa: RET505
        return [[start, end_positions[0]] for start in start_positions]
    elif len(start_positions) == 1 and len(end_positions) == 1:
        return [[start_positions[0], end_positions[0]]]
    raise AmbiguousCoordinateConversionError


def _convert_coordinate(
    converter: Converter, chromosome: str, coordinate: int
) -> list[int]:
    """Convert an individual coordinate to another reference genome. If the conversion is unsuccessful, raises a `CoordinateConversionError`

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the coordinate is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> i.e. "chr10".
    :param coordinate: A single start or end coordinate. MUST be an `int`.

    :return: A converted coordinate value as an `int`
    :raises: A `CoordinateConversionError` if the conversion is unsuccessful.
    """
    converted_positions = converter.convert_coordinate(
        chromosome, coordinate, Strand.POSITIVE
    )

    # TODO: Handle cases where coordinate conversion returns negative-stranded coordinates. See Issue #197.
    # `position` is a tuple with a) the coordinate's chromosome, b) the actual position, and c) the strand (Positive or Negative)
    return [
        position[1]
        for position in converted_positions
        if position[2] == Strand.POSITIVE
    ]

    # if converted_position and converted_position[0][2] == Strand.POSITIVE:
    #     # TODO: Don't just return coordinates from the first result set - handle cases where coordinate map to multiple positions. See Issue #198.
    #     return converted_position[0][1]
    raise CoordinateConversionFailureError


def convert_position(
    converter: Converter, chromosome: str, position: _PositionType
) -> list[int] | list[list[int | None]]:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be `models.Range` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> e.g. "chr10", "chrX", etc.
    :param position: A SequenceLocation start or end position. Can be `models.Range` or an `int`.

    :return: A lifted-over position. Type (`models.Range` or `int`) will match that of `position`
    """
    # Handle int positions
    if isinstance(position, int):
        return _convert_coordinate(converter, chromosome, position)

    # Handle Range (list) positions
    lower_bound_coords, upper_bound_coords = position.root
    lower_bound_coords = (
        _convert_coordinate(converter, chromosome, lower_bound_coords)
        if lower_bound_coords
        else [None]
    )
    upper_bound_coords = (
        _convert_coordinate(converter, chromosome, upper_bound_coords)
        if upper_bound_coords
        else [None]
    )

    return _build_position_list(lower_bound_coords, upper_bound_coords)
    # return [models.Range(position_entry) for position_entry in position_list]


def get_liftover_variant(input_variant: VrsVariation, anyvar: AnyVar) -> VrsVariation:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the converted variant as a VrsVariation.
    If liftover is unsuccessful, raise an Exception.

    :param input_variant: A dictionary representation of a `VrsVariation`.
    :param seqrepo_dataproxy: A `SeqrepoDataproxy` instance.
    :return: The converted variant as a `VrsVariation`.
    :raises:
        - `MalformedInputError`:  If the `input_variant` is empty or otherwise falsy

        - `UnsupportedVariantLocationTypeError`: If the variant lacks a refget accession, start position or end position

        - `UnsupportedReferenceAssemblyError`: If the variant's accession was not found in any supported assembly

        - `AmbiguousReferenceAssemblyError`: If the variant's accession was found in multiple supported assemblies

        - `ChromosomeResolutionError`: If unable to resolve variant's chromosome

        - `CoordinateConversionError`: If unable to lift over the variant's start and/or end position(s)

        - `AccessionConversionError`: If unable to lift over the variant's refget accession
    """
    if not input_variant:
        raise MalformedInputError

    refget_accession = get_nested_attribute(
        input_variant, "location", "sequenceReference", "refgetAccession"
    )
    start_position = get_nested_attribute(input_variant, "location", "start")
    end_position = get_nested_attribute(input_variant, "location", "end")
    if not refget_accession or not start_position or not end_position:
        raise UnsupportedVariantLocationTypeError

    # Determine which assembly we're converting from/to
    prefixed_accession = f"ga4gh:{refget_accession}"
    seqrepo_dataproxy = anyvar.translator.dp
    if accession_aliases := seqrepo_dataproxy.translate_sequence_identifier(
        prefixed_accession, ReferenceAssembly.GRCH38.value
    ):
        from_assembly, to_assembly = (
            ReferenceAssembly.GRCH38.value,
            ReferenceAssembly.GRCH37.value,
        )
    elif accession_aliases := seqrepo_dataproxy.translate_sequence_identifier(
        prefixed_accession, ReferenceAssembly.GRCH37.value
    ):
        from_assembly, to_assembly = (
            ReferenceAssembly.GRCH37.value,
            ReferenceAssembly.GRCH38.value,
        )
    else:
        msg = f"Unable to get reference sequence ID for {prefixed_accession}"
        raise UnsupportedReferenceAssemblyError(msg)

    # Determine which chromosome we're on
    chromosome = chr22XY(accession_aliases[0].split(":")[1])

    # Get the Converter that will liftover the variant's coordinates
    converter_key = f"{from_assembly}_to_{to_assembly}"
    converter = anyvar.liftover_converters.get(converter_key)
    if not converter:
        raise LiftoverError  # This won't happen, but Python doesn't know that and gets mad cuz it thinks `converter` might be `None`

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

    # Build the converted location object
    converted_variant_location = models.SequenceLocation(
        start=converted_start,
        end=converted_end,
        id=None,
        type="SequenceLocation",
        description=None,
        name=None,
        aliases=None,
        sequence=None,
        extensions=None,
        digest=None,
        sequenceReference=models.SequenceReference(
            type="SequenceReference",
            refgetAccession=converted_refget_accession,
            name=None,
            id=None,
            description=None,
            aliases=None,
            extensions=None,
            residueAlphabet=None,
            circular=None,
            sequence=None,
            moleculeType=None,
        ),
    )

    # Build the liftover variant object
    # Start by copying the original variant
    converted_variant = copy.deepcopy(input_variant)

    # Replace the location with the lifted-over version
    converted_variant.location = converted_variant_location

    # Get rid of the identifiers since these were from the original input variant and we need to re-compute them
    converted_variant.digest = None
    converted_variant.id = None

    # Compute the identifiers
    object_store = {}
    enreffed_variant = vrs_enref(
        o=converted_variant,
        object_store=object_store,
        return_id_obj_tuple=False,
    )

    # return the dereffed lifted-over variant
    dereffed_variant = vrs_deref(o=enreffed_variant, object_store=object_store)
    return variation_class_map[dereffed_variant.type](
        **dereffed_variant.model_dump()
    )  # explicitly cast to a VrsVariant so Pylance doesn't get mad


def add_liftover_annotations(
    input_vrs_id: str,
    input_vrs_variant_dict: dict,
    anyvar: AnyVar,
    annotator: AnyAnnotation | None,
) -> None:
    """Perform liftover between GRCh37 <-> GRCh38. Store the ID of converted variant as an annotation of the original,
    register the lifted-over variant, and store the ID of the original variant as an annotation of the lifted-over one.

    :param original_vrs_id: The ID of the VRS variant to lift over
    :param original_vrs_object: A dictionary representation of the VRS variant to lift over
    :param anyvar: An `AnyVar` instance
    :param annotator: An `AnyAnnotation` instance
    """
    # convert `input_vrs_object_dict` into an actual VrsVariation class instance
    variant_type = input_vrs_variant_dict.get("type", "")
    input_vrs_variant: VrsVariation = variation_class_map[variant_type](
        **input_vrs_variant_dict
    )

    lifted_over_variant: VrsVariation | None = None
    try:
        lifted_over_variant = get_liftover_variant(
            input_variant=input_vrs_variant,
            anyvar=anyvar,
        )
        # If liftover was successful, we'll annotate with the ID of the lifted-over variant
        annotation_value = lifted_over_variant.id
    except LiftoverError as e:
        # If liftover was unsuccessful, we'll annotate with an error message
        annotation_value = e.get_error_message()

    # Add the annotation to the original variant
    annotation_type = "liftover"
    if annotator:
        annotator.put_annotation(
            object_id=input_vrs_id,
            annotation_type=annotation_type,
            annotation={annotation_type: annotation_value},
        )

    # If liftover was successful, also register the lifted-over variant
    # and add an annotation on the lifted-over variant linking it back to the original
    if lifted_over_variant:
        anyvar.put_object(lifted_over_variant)

        if annotator:
            # TODO: Verify that the liftover is reversible first. See Issue #195
            annotator.put_annotation(
                object_id=str(lifted_over_variant.id),
                annotation_type=annotation_type,
                annotation={annotation_type: input_vrs_id},
            )
