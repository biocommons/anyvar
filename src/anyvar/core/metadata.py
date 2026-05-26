"""Define types and classes for *metadata*, i.e. additional descriptions on top of stored objects.

This currently includes

* **Extensions**: free-text key-value descriptions of an object
* **Mappings**: directed associations between objects
"""

from enum import StrEnum

from pydantic import BaseModel, JsonValue


class VariationMappingType(StrEnum):
    """Supported mapping types between VRS Variations.

    .. warning::

       Currently, use of mappings outside of the liftover relation are experimental,
       and these parameters are subject to change. The following describes current intentions,
       and may or may not be validated within AnyVar.

    * ``LIFTOVER_TO``: Genomic-to-genomic coordinate transformation. Use when mapping
      a variation between two reference sequences of the same molecule type, typically
      genomic DNA.
    * ``TRANSCRIBE_TO``: Genomic-to-transcript (RNA/cDNA) projection. Use when projecting
      a genomic DNA object onto a transcript sequence (RNA or cDNA). This accounts for
      splicing, transcript strand orientation, and transcript-specific exon structure.
    * ``TRANSLATE_TO``: Transcript-to-protein projection. This entails codon interpretation,
      amino acid substitution/insertion/deletion/extension, and protein coordinate changes.
    """

    LIFTOVER_TO = "liftover_to"
    TRANSCRIBE_TO = "transcribe_to"
    TRANSLATE_TO = "translate_to"


class VariationMapping(BaseModel):
    """Describe a mapping between two variations."""

    source_id: str
    dest_id: str
    mapping_type: VariationMappingType


class ExtensionName(StrEnum):
    """Describe commonly used extension names"""

    CREATION_TIMESTAMP = "creation_timestamp"


class Extension(BaseModel):
    """Generic extension class which attaches any object to an identifier

    This is implemented in addition to the ``Extension`` defined in ``gks-core`` because
    AnyVar needs additional metadata (like a reference ID) to manage it, but conceptually,
    they're quite close.
    """

    object_id: str
    name: str
    value: JsonValue
