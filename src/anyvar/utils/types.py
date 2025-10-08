"""Provide helpful type definitions and references."""

from dataclasses import dataclass
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
    """Describe a mapping between two variations.

    The ``.id`` property may be unavailable, depending on whether the instance is
    supposed to correspond to a mapping that may be retained in storage.
    """

    id: int | None = None
    source_id: str
    dest_id: str
    mapping_type: VariationMappingType


@dataclass
class AnnotationKey:
    """Generic annotation key class which specifies the object and the type of annotation"""

    object_id: str
    annotation_type: str


@dataclass
class Annotation(AnnotationKey):
    """Generic annotation class which attaches any object to an identifier"""

    annotation: Any

    def key(self) -> AnnotationKey:
        """Return the key of the annotation"""
        return AnnotationKey(self.object_id, self.annotation_type)
