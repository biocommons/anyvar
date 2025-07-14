"""Support processing and manipulation of VCF objects."""

import logging
from pathlib import Path

import pysam
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.extras.annotator.vcf import FieldName, VcfAnnotator
from ga4gh.vrs.models import (
    Allele,
    LiteralSequenceExpression,
    SequenceLocation,
    SequenceReference,
)

from anyvar.anyvar import AnyVar

_logger = logging.getLogger(__name__)


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


def _raise_for_missing_vcf_annotations(vcf: pysam.VariantFile) -> None:
    """Check whether all required VRS annotations are present on a provided VCF

    :vcf: file to check
    :return: None if successful
    :raise: ValueError if provided VCF lacks required annotations
    """
    field_names = {name.value for name in FieldName}
    if not all(n in vcf.header.info for n in field_names):
        raise ValueError(
            "VCF missing some required INFO fields: %s",
            field_names - set(vcf.header.info.keys()),
        )


def register_existing_annotations(
    av: AnyVar, file_path: Path | str, assembly: str
) -> None:
    """Pass"""
    variantfile = pysam.VariantFile(filename=str(file_path), mode="r")
    _raise_for_missing_vcf_annotations(variantfile)
    for record in variantfile:
        if not all(
            [
                FieldName.IDS_FIELD in record.info,
                FieldName.STARTS_FIELD in record.info,
                FieldName.ENDS_FIELD in record.info,
                FieldName.STATES_FIELD in record.info,
            ]
        ):
            continue
        sequence = f"{assembly}:{record.chrom}"
        refget_accession = av.translator.dp.derive_refget_accession(sequence)
        if not refget_accession:
            _logger.warning(
                "Unable to acquire refget accession for constructed sequence identifier %s at pos %s",
                sequence,
                record.pos,
            )
            continue
        for vrs_id, start, end, state in zip(
            record.info[FieldName.IDS_FIELD],
            record.info[FieldName.STARTS_FIELD],
            record.info[FieldName.ENDS_FIELD],
            record.info[FieldName.STATES_FIELD],
            strict=True,
        ):
            if vrs_id == ".":
                continue
            if state == ".":
                state = ""
            seq_ref = SequenceReference(refgetAccession=refget_accession)
            location = SequenceLocation(sequenceReference=seq_ref, start=start, end=end)
            state = LiteralSequenceExpression(sequence=state)
            allele = Allele(location=location, state=state)
            av.put_object(allele)
            # TODO validate ID?
