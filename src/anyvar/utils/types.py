"""Provide helpful type definitions and references."""
from typing import Union

from ga4gh.vrs import models
from ga4gh.vrsatile.pydantic import vrs_models

VrsVariation = Union[
    vrs_models.Allele,
    vrs_models.Text,
]

VrsPythonVariation = Union[
    models.Allele,
    models.Text,
]

# should include all supported VRS Python variation types + location types
VrsPythonObject = Union[
    models.Allele,
    models.Text,
    models.SequenceLocation,
]

# Temporary solution to issue of coupling between VRS-Python ref methods and PJS
variation_class_map = {
    vrs_models.VRSTypes.ALLELE: models.Allele,
    vrs_models.VRSTypes.TEXT: models.Text,
}
