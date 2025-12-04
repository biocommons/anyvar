"""Provide helpful type definitions, references, and type-based operations."""

from enum import StrEnum
from typing import TypeVar, get_args

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models, vrs_deref, vrs_enref
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
    This should only be used to parse HTTP input in the `src/anyvar/restapi/schema.py` models, not within application logic.

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


class AnnotationType(StrEnum):
    """Describe commonly used annotation types"""

    CREATION_TIMESTAMP = "creation_timestamp"


Type_VrsObject = TypeVar("Type_VrsObject", bound=VrsObject)


def recursive_identify(vrs_object: Type_VrsObject) -> Type_VrsObject:
    """Add GA4GH IDs to an object and all GA4GH-identifiable objects contained within.

    ***This is a very hack-y solution and should not be relied upon any more than it is.
    It appears that enref/deref() will add IDs within objects, but don't produce a
    correct ID, and ga4gh_identify() won't add IDs to contained objects, so this function
    runs both in succession.

    There is probably an upstream fix in VRS-Python that needs to happen.

    :param vrs_object: AnyVar-supported variation object
    :return: same object, with any missing ID fields filled in
    """
    storage = {}
    enreffed = vrs_enref(vrs_object, storage)
    dereffed = vrs_deref(enreffed, storage)
    dereffed.id = None  # type: ignore[reportAttributeAccessIssue]
    dereffed.digest = None  # type: ignore[reportAttributeAccessIssue]
    ga4gh_identify(dereffed, in_place="always")
    return dereffed  # type: ignore[reportReturnType]
