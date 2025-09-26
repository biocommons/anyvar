"""Provide helpful type definitions and references."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeAlias

from ga4gh.vrs import models
from pydantic import BaseModel

from anyvar.storage.abc import StoredVrsObjectType

# should include all supported VRS Python variation types
VrsVariation = models.Allele | models.CopyNumberChange | models.CopyNumberCount


# should include all supported VRS Python variation types + location types
VrsObject: TypeAlias = (
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


@dataclass
class Annotation(BaseModel):
    """Generic annotation class which attaches any object to an identifier"""

    annotation_id: int | None
    object_id: str
    object_type: StoredVrsObjectType
    annotation_type: str
    annotation_value: Any

    def __init__(
        self,
        object_id: str,
        object_type: StoredVrsObjectType,
        annotation_type: str,
        annotation_value: Any,  # noqa: ANN401
        annotation_id: int | None = None,
    ) -> None:
        """Initialize an Annotation object

        :param annotation_id: The annotation's ID
        :param object_id: The ID of the object this annotation describes
        :param object_type: The type of object this annotation describes
        :param annotation_type: The type of annotation being added
        :param annotation_value: The annotation itself
        """
        self.object_id = object_id
        self.object_type = object_type
        self.annotation_type = annotation_type
        self.annotation_value = annotation_value
        self.annotation_id = annotation_id
