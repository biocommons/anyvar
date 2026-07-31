"""Support processing and manipulation of VCF objects."""

import logging
from pathlib import Path

from ga4gh.vrs import models as vrs_models
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.extras.annotator.vcf import VcfAnnotator

from anyvar import AnyVar
from anyvar.core.objects import SupportedVrsObject

_logger = logging.getLogger(__name__)


class VrsObjectRegistrationBatcher:
    """Handles bulk registration of a large number of VrsObjects in batches"""

    BATCH_SIZE = 10000
    batch_collection: list[SupportedVrsObject]
    anyvar_instance: AnyVar

    def __init__(self, anyvar_instance: AnyVar) -> None:
        """Initialize batch collection list and AnyVar instance to use for registration

        :param anyvar_instance: The AnyVar instance to use for registration
        :return: None
        """
        self.batch_collection = []
        self.anyvar_instance = anyvar_instance

    def add_to_batch(self, vrs_object: SupportedVrsObject) -> None:
        """Adds a VRS Object to the current batch. If batch size limit is now met, register the whole batch.

        :param vrs_object: The VrsObject to add to the batch
        :return: None
        """
        self.batch_collection.append(vrs_object)
        if len(self.batch_collection) >= self.BATCH_SIZE:
            self.register_batch()

    def register_batch(self) -> None:
        """Registers a batch of vrs objects and resets the collection list to prepare for the next batch"""
        if self.batch_collection:
            self.anyvar_instance.put_objects(self.batch_collection)
            _logger.debug("Wrote %s variants to DB", len(self.batch_collection))
            self.batch_collection = []


class VcfRegistrar(VcfAnnotator):
    """Custom implementation of annotator class from VRS-Python. Rewrite some methods
    and values in order to enable use of existing AnyVar translator.
    """

    vrs_object_registration_batcher: VrsObjectRegistrationBatcher

    def __init__(self, data_proxy: _DataProxy, **kwargs) -> None:  # noqa: D107
        av: AnyVar | None = kwargs.get("av")
        if av is None:
            raise ValueError
        self.av: AnyVar = av
        self.vrs_object_registration_batcher = VrsObjectRegistrationBatcher(self.av)
        super().__init__(data_proxy)
        _logger.debug("TODO remove initializing vcf registrar")

    def on_vrs_object(
        self,
        vcf_coords: str,
        vrs_allele: vrs_models.Allele,
        **kwargs,
    ) -> vrs_models.Allele | None:
        """Adds the VRS object to the batcher, which handles bulk registration"""
        self.vrs_object_registration_batcher.add_to_batch(vrs_allele)
        return vrs_allele

    def on_vrs_object_collection(  # noqa: D102
        self,
        vrs_alleles_collection: list[vrs_models.Allele] | None,
        **kwargs,
    ) -> None:
        pass

    def raise_for_output_args(self, output_vcf_path: Path | None, **kwargs) -> None:  # noqa: D102
        pass

    def annotate(
        self,
        input_vcf_path: Path,
        output_vcf_path: Path | None = None,
        vrs_attributes: bool = False,
        assembly: str = "GRCh38",
        compute_for_ref: bool = True,
        require_validation: bool = True,
        **kwargs,
    ) -> None:
        """Calls the parent 'annotate' function, then adds the final batch of VRS objects to the database"""
        super().annotate(
            input_vcf_path,
            output_vcf_path,
            vrs_attributes,
            assembly,
            compute_for_ref,
            require_validation,
            **kwargs,
        )

        # register the final batch of vrs objects (since the last batch will likely be smaller than the batch size limit)
        self.vrs_object_registration_batcher.register_batch()

    # def register_without_annotating(
    #     self,
    #     input_vcf_path: Path,
    #     output_vcf_path: Path | None = None,
    #     vrs_attributes: bool = False,
    #     assembly: str = "GRCh38",
    #     compute_for_ref: bool = True,
    #     require_validation: bool = True,
    #     **kwargs
    # ) -> None:
    #     super().annotate(
    #         input_vcf_path,
    #         output_vcf_path,
    #         vrs_attributes,
    #         assembly,
    #         compute_for_ref,
    #         require_validation,
    #         **kwargs,
    #     )
