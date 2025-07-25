"""Defines functions used to lift over variants between GRCh37 & GRCh38"""

import copy
from enum import Enum
from typing import TypeVar

from agct import Converter, Strand
from bioutils.accessions import chr22XY
from ga4gh.vrs.enderef import vrs_deref, vrs_enref

from anyvar.anyvar import AnyAnnotation, AnyVar
from anyvar.utils.types import VrsObject, VrsVariation, variation_class_map


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


class CoordinateConversionError(LiftoverError):
    """Indicates a failure to lift over a variant's coordinate"""

    error_details = "Could not convert start and/or end position(s)"


class AccessionConversionError(LiftoverError):
    """Indicates a failure to convert a variant's refget accession"""

    error_details = "Could not convert refget accession)"


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

    # TODO: Handle cases where coordinate conversion returns negative-stranded coordinates. See Issue #197.
    if converted_position and converted_position[0][2] == Strand.POSITIVE:
        # TODO: Don't just return coordinates from the first result set - handle cases where coordinate map to multiple positions. See Issue #198.
        return converted_position[0][1]
    raise CoordinateConversionError


_PositionType = TypeVar("_PositionType", int, list[int | None])


def convert_position(
    converter: Converter, chromosome: str, position: _PositionType
) -> _PositionType:
    """Convert a SequenceLocation position (i.e., `start` or `end`) to another reference Genome. `position` can either be a `list[int | None]` or an `int` - return type will match.

    :param converter: An AGCT Converter instance.
    :param chromosome: The chromosome number where the position is found. Must be a string consisting of a) the prefix "chr", and b) a number OR "X" or "Y" -> e.g. "chr10", "chrX", etc.
    :param position: A SequenceLocation start or end position. Can be a `list[int | None]` or an `int`.

    :return: A lifted-over position. Type (`list[int | None]` or `int`) will match that of `position`
    """
    # Handle int positions
    if isinstance(position, int):
        return _convert_coordinate(converter, chromosome, position)

    # Handle Range (list) positions
    lower_bound, upper_bound = position
    lower_bound = (
        _convert_coordinate(converter, chromosome, lower_bound) if lower_bound else None
    )
    upper_bound = (
        _convert_coordinate(converter, chromosome, upper_bound) if upper_bound else None
    )
    return [lower_bound, upper_bound]


def get_liftover_variant(variant_object: dict, anyvar: AnyVar) -> VrsVariation:
    """Liftover a variant from GRCh37 or GRCH38 into the opposite assembly, and return the converted variant as a VrsObject.
    If liftover is unsuccessful, raise an Exception.

    :param variant_object: A dictionary representation of a `VrsVariation`.
    :param seqrepo_dataproxy: A `SeqrepoDataproxy` instance.
    :return: The converted variant as a `VrsObject`.
    :raises:
        - `MalformedInputError`:  If the `variant_object` is empty or otherwise falsy

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

    # Get the Converter that will liftover the variant's coordinates
    converter_key = f"{from_assembly}_to_{to_assembly}"
    converter = anyvar.liftover_converters.get(converter_key)
    if not converter:
        raise LiftoverError  # This won't happen, but Python doesn't know that and gets mad cuz it thinks `converter` might be `None`

    # Determine which chromosome we're on
    chromosome = chr22XY(accession_aliases[0].split(":")[1])

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
    converted_variant_dict = copy.deepcopy(variant_object)

    # Replace the location with the lifted-over version
    converted_variant_dict["location"] = converted_variant_location

    # Get rid of the identifiers since these were from the original variant object and we need to re-compute them
    converted_variant_dict["digest"] = None
    converted_variant_dict["id"] = None

    # Convert the dict into a VrsObject class instance so we can compute the identifiers
    variant_type = variant_object.get("type", "")
    converted_variant_object: VrsObject = variation_class_map[variant_type](
        **converted_variant_dict
    )

    # Compute the identifiers
    object_store = {}
    enreffed_variant = vrs_enref(
        o=converted_variant_object,
        object_store=object_store,
        return_id_obj_tuple=False,
    )

    # return the dereffed lifted-over variant as a VrsObject
    dereffed_variant = vrs_deref(o=enreffed_variant, object_store=object_store)
    return variation_class_map[variant_type](**dereffed_variant.model_dump())


def add_liftover_annotations(
    original_vrs_id: str,
    original_vrs_object: dict,
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
    if annotator and annotator.get_annotation(original_vrs_id, "liftover"):
        return

    annotation_type = "liftover"

    lifted_over_variant: VrsObject | None = None
    try:
        lifted_over_variant = get_liftover_variant(
            variant_object=original_vrs_object,
            anyvar=anyvar,
        )
        # If liftover was successful, we'll annotate with the ID of the lifted-over variant
        annotation_value = lifted_over_variant.model_dump().get("id")
    except LiftoverError as e:
        # If liftover was unsuccessful, we'll annotate with an error message
        annotation_value = e.get_error_message()

    # Add the annotation to the original variant
    if annotator:
        annotator.put_annotation(
            object_id=original_vrs_id,
            annotation_type=annotation_type,
            annotation={annotation_type: annotation_value},
        )

    # If liftover was successful, also register the lifted-over variant
    # and add an annotation on the lifted-over variant linking it back to the original
    if lifted_over_variant:
        anyvar.put_object(lifted_over_variant)

        # TODO: Verify that the liftover is reversible first. See Issue #195
        if annotator:
            annotator.put_annotation(
                object_id=lifted_over_variant.model_dump().get("id", ""),
                annotation_type=annotation_type,
                annotation={annotation_type: original_vrs_id},
            )
