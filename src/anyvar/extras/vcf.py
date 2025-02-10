"""Support processing and manipulation of VCF objects."""

import logging
from pathlib import Path

from ga4gh.vrs.extras.annotator.vcf import VcfAnnotator
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.models import Allele

from anyvar.anyvar import AnyVar
from anyvar.translate.translate import TranslationError

_logger = logging.getLogger(__name__)


class VcfRegistrar(VcfAnnotator):
    """Custom implementation of annotator class from VRS-Python. Rewrite some methods
    and values in order to enable use of existing AnyVar translator.
    """
    def __init__(self, data_proxy: _DataProxy, **kwargs) -> None:
        av = kwargs.get("av")
        if av is None:
            raise ValueError  # TODO more specific
        self.av: AnyVar = av
        super().__init__(data_proxy)


    def annotate(self, input_vcf_path: Path, output_vcf_path: Path | None = None, vrs_attributes: bool = False, assembly: str = "GRCh38", compute_for_ref: bool = True, require_validation: bool = True, **kwargs) -> None:
        if self.av.object_store.batch_manager:
            storage = self.av.object_store
            with self.av.object_store.batch_manager(storage):
                super().annotate(input_vcf_path, output_vcf_path, vrs_attributes, assembly, compute_for_ref, require_validation, **kwargs)
        else:
            super().annotate(input_vcf_path, output_vcf_path, vrs_attributes, assembly, compute_for_ref, require_validation, **kwargs)

    def on_vrs_object(self, vcf_coords: str, vrs_allele: Allele, **kwargs) -> Allele | None:
        av = kwargs.get("av")
        if av is None:
            raise ValueError  # TODO ??
        av.put_object(vrs_allele)

    def on_vrs_object_collection(self, vrs_alleles_collection: list[Allele] | None, **kwargs) -> None:
        pass

    def raise_for_output_args(self, output_vcf_path: Path | None, **kwargs) -> None:
        pass
