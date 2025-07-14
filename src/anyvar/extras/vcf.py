"""Support processing and manipulation of VCF objects."""

import logging
from contextlib import nullcontext
from pathlib import Path
from typing import NamedTuple

import pysam
from ga4gh.vrs import vrs_enref
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


class RequiredAnnotationsError(Exception):
    """Raise when encountering incomplete or invalid VRS annotations"""


def _raise_for_missing_vcf_annotations(vcf: pysam.VariantFile) -> None:
    """Check whether all required VRS annotations are present on a provided VCF

    :vcf: file to check
    :return: None if successful
    :raise: RequiredAnnotationsError if provided VCF lacks required annotations
    """
    field_names = {name.value for name in FieldName}
    if not all(n in vcf.header.info for n in field_names):
        raise RequiredAnnotationsError(
            "VCF missing some required INFO fields: %s",
            field_names - set(vcf.header.info.keys()),
        )


class ConflictingIdRecord(NamedTuple):
    """Describe relevant data for a conflict between an existing VRS ID annotation and
    a newly-calculated ID.
    """

    annotated_vrs_id: str
    assembly: str
    chrom: str
    start: int
    end: int
    state: str
    new_vrs_id: str


def register_existing_annotations(
    av: AnyVar, file_path: Path, assembly: str, require_validation: bool = False
) -> Path | None:
    """Extract VRS allele parameters from a previously-annotated VCF and register them.

    :param av: AnyVar instance
    :param file_path: path to VCF
    :param assembly: assembly used during VCF writing and annotation. Probably one of
        ``{"GRCh37", "GRCh38"}``
    :param require_validation: TODO
    :return:  TODO
    :raise: ValueError if input VCF lacks required annotations
    """
    _logger.info("Registering existing annotations from VCF at %s", file_path)
    variantfile = pysam.VariantFile(filename=str(file_path), mode="r")
    _raise_for_missing_vcf_annotations(variantfile)

    if require_validation:
        conflict_logfile_path = file_path.parent / f"{file_path.name}_conflictlog"
        cm = conflict_logfile_path.open("w")
    else:
        conflict_logfile_path = None
        cm = nullcontext(None)

    with cm as conflict_logfile:
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
                location = SequenceLocation(
                    sequenceReference=seq_ref, start=start, end=end
                )
                lse = LiteralSequenceExpression(sequence=state)
                allele = Allele(location=location, state=lse)
                if conflict_logfile:
                    new_vrs_id, allele = vrs_enref(allele)
                    if new_vrs_id != vrs_id:
                        _logger.debug(
                            "Annotated ID %s conflicts with newly-calculated ID %s for variation %s:%s %s-%s (state: %s)",
                            vrs_id,
                            new_vrs_id,
                            assembly,
                            record.chrom,
                            start,
                            end,
                            state,
                        )
                        conflict_logfile.write(
                            f"{vrs_id},{assembly},{record.chrom},{start},{end},{state},{new_vrs_id}"
                        )
                av.put_object(allele)
    return conflict_logfile_path
