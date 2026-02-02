"""Define types and classes for *metadata*, i.e. additional descriptions on top of stored objects.

This currently includes

* **Annotations**: free-text key-value descriptions of an object
* **Mappings**: directed associations between objects
"""

from enum import StrEnum

from pydantic import BaseModel, JsonValue


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


class AnnotationType(StrEnum):
    """Describe commonly used annotation types"""

    CREATION_TIMESTAMP = "creation_timestamp"


class Annotation(BaseModel):
    """Generic annotation class which attaches any object to an identifier"""

    object_id: str
    annotation_type: str
    annotation_value: JsonValue
