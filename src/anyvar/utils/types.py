"""Provide helpful type definitions and references."""

from enum import StrEnum
from typing import Any

from ga4gh.vrs import models
from pydantic import BaseModel

# should include all supported VRS Python variation types
VrsVariation = models.Allele | models.CopyNumberChange | models.CopyNumberCount


# should include all supported VRS Python variation types + location types
VrsObject = (
    models.Allele
    | models.CopyNumberChange
    | models.CopyNumberCount
    | models.SequenceLocation
    | models.SequenceReference
)


# variation type: VRS-Python model
variation_class_map: dict[str, type[VrsVariation]] = {
    "Allele": models.Allele,
    "CopyNumberCount": models.CopyNumberCount,
    "CopyNumberChange": models.CopyNumberChange,
}


class SupportedVariationType(StrEnum):
    """Define constraints for supported variation types"""

    ALLELE = "Allele"
    COPY_NUMBER_COUNT = "CopyNumberCount"
    COPY_NUMBER_CHANGE = "CopyNumberChange"


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
    annotation_value: Any
