"""Support processing and manipulation of VCF objects."""

import logging
from contextlib import nullcontext
from pathlib import Path

import pysam
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import normalize
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

    :param vcf: file to check
    :return: None if successful
    :raise: RequiredAnnotationsError if provided VCF lacks required annotations
    """
    field_names = {name.value for name in FieldName}
    if not all(n in vcf.header.info for n in field_names):
        raise RequiredAnnotationsError(
            "VCF missing some required INFO fields: %s",
            field_names - set(vcf.header.info.keys()),
        )


def register_existing_annotations(
    av: AnyVar, file_path: Path, assembly: str, require_validation: bool = False
) -> Path | None:
    """Extract VRS allele parameters from a previously-annotated VCF and register them.

    :param av: AnyVar instance
    :param file_path: path to VCF
    :param assembly: assembly used during VCF writing and annotation. Probably one of
        ``{"GRCh37", "GRCh38"}``
    :param require_validation: whether to check that annotated ID is correct
    :return:  Path to ID conflict file, if requested, or None otherwise
    :raise: ValueError if input VCF lacks required annotations
    """
    _logger.info("Registering existing annotations from VCF at %s", file_path)
    variantfile = pysam.VariantFile(filename=str(file_path), mode="r")
    _raise_for_missing_vcf_annotations(variantfile)

    if require_validation:
        conflict_logfile_path = file_path.parent / f"{file_path.name}_conflictlog"
        cm = conflict_logfile_path.open("w")
    else:
        # conflicts will be ignored, so no need to keep track of them
        conflict_logfile_path = None
        cm = nullcontext(None)

    with cm as conflict_logfile:
        if conflict_logfile:
            conflict_logfile.write(
                "vrs_id,assembly,chrom,pos,start,end,state,new_vrs_id\n"
            )
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
                true_state = "" if state == "." else state
                seq_ref = SequenceReference(refgetAccession=refget_accession)  # pyright: ignore[reportCallIssue] - values that aren't specified default to `None`
                location = SequenceLocation(
                    sequenceReference=seq_ref, start=start, end=end
                )  # pyright: ignore[reportCallIssue]
                location_id = ga4gh_identify(location)
                location.id = location_id
                lse = LiteralSequenceExpression(sequence=true_state)  # pyright: ignore[reportCallIssue]
                allele = Allele(location=location, state=lse)  # pyright: ignore[reportCallIssue]
                allele = normalize(allele, av.translator.dp)
                new_vrs_id = ga4gh_identify(allele)
                if conflict_logfile and new_vrs_id != vrs_id:
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
                        f"{vrs_id},{assembly},{record.chrom},{record.pos},{start},{end},{true_state},{new_vrs_id}\n"
                    )
                av.put_object(allele)
    return conflict_logfile_path
