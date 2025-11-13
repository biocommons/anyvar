"""Provide helpful type definitions and references."""

from enum import StrEnum
from typing import get_args

from ga4gh.vrs import models
from pydantic import BaseModel, JsonValue

from anyvar.utils.funcs import camel_case_to_snake_case

VrsObject = (
    models.Allele
    | models.CopyNumberChange
    | models.CopyNumberCount
    | models.SequenceLocation
    | models.SequenceReference
)


VrsVariation = models.Allele | models.CopyNumberChange | models.CopyNumberCount


class SupportedVariationType(StrEnum):
    """Supported variation types for API input. Enum is dynamically built from the models in the `VrsVariation` type union.

    Example:
    >>> SupportedVariationType.COPY_NUMBER_CHANGE = "CopyNumberChange"

    """

    locals().update(
        {
            camel_case_to_snake_case(cls.__name__): cls.__name__
            for cls in get_args(VrsObject)
        }
    )


"""
Builds a dict in the form of `"ModelName": models.ModelName` for every class listed in the `VrsObject` type union
For example:
>>> vrs_object_class_map["Allele"] = models.Allele
"""
vrs_object_class_map: dict[str, type[VrsObject]] = {
    cls.__name__: cls for cls in get_args(VrsObject)
}


class VariationMappingType(StrEnum):
    """Supported mapping types between VRS Variations."""

    LIFTOVER = "liftover"
    TRANSCRIPTION = "transcription"
    TRANSLATION = "translation"


class VariationMapping(BaseModel):
    """Describe a mapping between two variations."""

    source_id: str
    dest_id: str
    mapping_type: VariationMappingType


class Annotation(BaseModel):
    """Generic annotation class which attaches any object to an identifier"""

    object_id: str
    annotation_type: str
    annotation_value: JsonValue
