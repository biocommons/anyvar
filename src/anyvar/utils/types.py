"""Provide helpful type definitions and references."""
from typing import Union
from enum import StrEnum

from ga4gh.vrs import models

# should include all supported VRS Python variation types
VrsVariation = Union[
    models.Allele,
    models.CopyNumberChange,
    models.CopyNumberCount,
]

# should include all supported VRS Python variation types + location types
VrsObject = Union[
    models.Allele,
    models.CopyNumberChange,
    models.CopyNumberCount,
    models.SequenceLocation,
]

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
