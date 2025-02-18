"""Support processing and manipulation of VCF objects."""

from pathlib import Path

from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.extras.annotator.vcf import VcfAnnotator
from ga4gh.vrs.models import Allele

from anyvar.anyvar import AnyVar


class VcfRegistrar(VcfAnnotator):
    """Custom implementation of annotator class from VRS-Python. Rewrite some methods
    and values in order to enable use of existing AnyVar translator.
    """

    def __init__(self, data_proxy: _DataProxy, **kwargs) -> None:  # noqa: D107
        av = kwargs.get("av")
        if av is None:
            raise ValueError  # TODO more specific
        self.av: AnyVar = av
        super().__init__(data_proxy)

    def on_vrs_object(  # noqa: D102
        self,
        vcf_coords: str,  # noqa: ARG002
        vrs_allele: Allele,
        **kwargs,  # noqa: ARG002
    ) -> Allele | None:
        self.av.put_object(vrs_allele)
        return vrs_allele

    def on_vrs_object_collection(  # noqa: D102
        self, vrs_alleles_collection: list[Allele] | None, **kwargs
    ) -> None:
        pass

    def raise_for_output_args(self, output_vcf_path: Path | None, **kwargs) -> None:  # noqa: D102
        pass
