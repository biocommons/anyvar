"""Support processing and manipulation of VCF objects."""
import logging
from typing import Dict, Optional

from ga4gh.vrs.extras.vcf_annotation import VCFAnnotator

from anyvar.anyvar import AnyVar
from anyvar.translate.translate import TranslationException

_logger = logging.getLogger(__name__)


class VcfRegistrar(VCFAnnotator):
    """Custom implementation of annotator class from VRS-Python. Rewrite some methods
    and values in order to enable use of existing AnyVar translator.
    """

    def __init__(self, av: AnyVar) -> None:
        """Initialize VCF processor.

        :param av: complete AnyVar instance
        """
        self.av = av

    def annotate(
        self,
        vcf_in: str,
        vcf_out: Optional[str] = None,
        vrs_pickle_out: Optional[str] = None,
        vrs_attributes: bool = False,
        assembly: str = "GRCh38",
        compute_for_ref: bool = True,
    ) -> None:
        """Annotates an input VCF file with VRS Allele IDs & creates a pickle file
        containing the vrs object information.

        :param vcf_in: The path for the input VCF file to annotate
        :param vcf_out: The path for the output VCF file
        :param vrs_pickle_out: The path for the output VCF pickle file
        :param vrs_attributes: If `True` will include VRS_Start, VRS_End, VRS_State
            fields in the INFO field. If `False` will not include these fields.
            Only used if `vcf_out` is provided.
        :param assembly: The assembly used in `vcf_in` data
        :param compute_for_ref: If `True`, compute VRS IDs for REF alleles
        """
        if self.av.object_store.batch_manager:
            storage = self.av.object_store
            with storage.batch_manager(storage):  # type: ignore
                return super().annotate(vcf_in, vcf_out, vrs_pickle_out, vrs_attributes, assembly, compute_for_ref)
        else:
            super().annotate(vcf_in, vcf_out, vrs_pickle_out, vrs_attributes, assembly, compute_for_ref)

    def _get_vrs_object(
        self,
        vcf_coords: str,
        vrs_data: Dict,
        vrs_field_data: Dict,
        assembly: str,
        vrs_data_key: Optional[str] = None,
        output_pickle: bool = True,
        output_vcf: bool = False,
        vrs_attributes: bool = False,
    ) -> None:
        """Get VRS Object given `vcf_coords`. `vrs_data` and `vrs_field_data` will
        be mutated. Generally, we expect AnyVar to use the output_vcf option rather than
        the pickle file.

        :param vcf_coords: Allele to get VRS object for. Format is chr-pos-ref-alt
        :param vrs_data: Dictionary containing the VRS object information for the VCF
        :param vrs_field_data: If `output_vcf`, will keys will be VRS Fields and values
            will be list of VRS data. Else, will be an empty dictionary.
        :param assembly: The assembly used in `vcf_coords`. Not used by this
            implementation -- GRCh38 is assumed.
        :param vrs_data_key: The key to update in `vrs_data`. If not provided, will use
            `vcf_coords` as the key.
        :param output_pickle: `True` if VRS pickle file will be output. `False`
            otherwise.
        :param output_vcf: `True` if annotated VCF file will be output. `False`
            otherwise.
        :param vrs_attributes: If `True` will include VRS_Start, VRS_End, VRS_State
            fields in the INFO field. If `False` will not include these fields.
            Only used if `vcf_out` is provided. Not used by this implementation.
        :return: nothing, but registers VRS objects with AnyVar storage and stashes IDs
        """
        vrs_object = self.av.translator.translate_vcf_row(vcf_coords)
        if vrs_object:
            self.av.put_object(vrs_object)
            if output_pickle:
                key = vrs_data_key if vrs_data_key else vcf_coords
                vrs_data[key] = str(vrs_object.model_dump(exclude_none=True))

            if output_vcf:
                allele_id = vrs_object.id if vrs_object else ""
                vrs_field_data[self.VRS_ALLELE_IDS_FIELD].append(allele_id)

        else:
            raise TranslationException(f"Translator returned empty VRS object for VCF coords {vcf_coords}")
