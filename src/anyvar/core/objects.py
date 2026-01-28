"""Provide types, classes, and functions for objects stored by AnyVar."""

from enum import StrEnum
from typing import TypeVar, get_args

from ga4gh.core import ga4gh_identify
from ga4gh.vrs import VrsType, models, vrs_deref, vrs_enref

"""
Any time this is updated, a corresponding member MUST be added to ``SupportedObjectType``.

``tests/unit/core/test_objects.py::test_supported_object_type`` will fail if you don't.
"""
VrsObject = (
    models.Allele
    | models.CopyNumberChange
    | models.CopyNumberCount
    | models.SequenceLocation
    | models.SequenceReference
)


class SupportedObjectType(StrEnum):
    """Enumeration, by name, of objects that can be stored by AnyVar"""

    ALLELE = VrsType.ALLELE.value
    COPY_NUMBER_CHANGE = VrsType.CN_CHANGE.value
    COPY_NUMBER_COUNT = VrsType.CN_COUNT.value
    SEQUENCE_LOCATION = VrsType.SEQ_LOC.value
    SEQUENCE_REFERENCE = VrsType.SEQ_REF.value


VrsVariation = models.Allele | models.CopyNumberChange | models.CopyNumberCount


"""
Builds a dict in the form of `"ModelName": models.ModelName` for every class listed in the `VrsObject` type union
For example:
>>> vrs_object_class_map["Allele"] = models.Allele
"""
vrs_object_class_map: dict[str, type[VrsObject]] = {
    cls.__name__: cls for cls in get_args(VrsObject)
}


Type_VrsObject = TypeVar("Type_VrsObject", bound=VrsObject)


def recursive_identify(vrs_object: Type_VrsObject) -> Type_VrsObject:
    """Add GA4GH IDs to an object and all GA4GH-identifiable objects contained within.

    .. ATTENTION::

       This is a very hack-y solution and should not be relied upon any more than it is.
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
