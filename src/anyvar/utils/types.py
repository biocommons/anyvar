"""Provide helpful type definitions and references."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ga4gh.vrs import models

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
variation_class_map = {
    "Allele": models.Allele,
    "CopyNumberCount": models.CopyNumberCount,
    "CopyNumberChange": models.CopyNumberChange,
}


class SupportedVariationType(StrEnum):
    """Define constraints for supported variation types"""

    ALLELE = "Allele"
    COPY_NUMBER_COUNT = "CopyNumberCount"
    COPY_NUMBER_CHANGE = "CopyNumberChange"


@dataclass
class AnnotationKey:
    """Generic annotation key class which specifies the object and the type of annotation"""

    object_id: str
    annotation_type: str


@dataclass
class Annotation(AnnotationKey):
    """Generic annotation class which attaches any object to an identifier"""

    annotation: Any

    def key(self):
        return AnnotationKey(self.object_id, self.annotation_type)
