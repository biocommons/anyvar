"""Provide helpful type definitions and references."""
from typing import Union

from ga4gh.vrs import models
from ga4gh.vrsatile.pydantic import vrs_models

VrsVariation = Union[
    vrs_models.Allele, vrs_models.Haplotype, vrs_models.AbsoluteCopyNumber,
    vrs_models.RelativeCopyNumber, vrs_models.Text, vrs_models.VariationSet
]

VrsPythonVariation = Union[
    models.Allele,
    models.Haplotype,
    # models.AbsoluteCopyNumber,
    # models.RelativeCopyNumber,
    models.Text,
    models.VariationSet
]

VrsPythonObject = Union[
    models.Allele,
    models.Haplotype,
    models.Text,
    models.VariationSet,
    models.SequenceLocation,
]

# Temporary solution to issue of coupling between VRS-Python ref methods and PJS
variation_class_map = {
    vrs_models.VRSTypes.ALLELE: models.Allele,
    vrs_models.VRSTypes.TEXT: models.Text,
}
