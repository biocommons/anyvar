"""Support processing and manipulation of VCF objects."""

import logging
from contextlib import nullcontext
from pathlib import Path

import pysam
from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models as vrs_models
from ga4gh.vrs import normalize
from ga4gh.vrs.dataproxy import _DataProxy
from ga4gh.vrs.extras.annotator.vcf import FieldName, VcfAnnotator

from anyvar.anyvar import AnyVar
from anyvar.utils.types import VrsObject

_logger = logging.getLogger(__name__)


class VrsObjectRegistrationBatcher:
    """Handles bulk registration of a large number of VrsObjects in batches"""

    BATCH_SIZE = 10000
    batch_collection: list[VrsObject]
    anyvar_instance: AnyVar

    def __init__(self, anyvar_instance: AnyVar) -> None:
        """Initialize batch collection list and AnyVar instance to use for registration

        :param anyvar_instance: The AnyVar instance to use for registration
        :return: None
        """
        self.batch_collection = []
        self.anyvar_instance: AnyVar = anyvar_instance

    def add_to_batch(self, vrs_object: VrsObject) -> None:
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
    vrs_object_registration_batcher = VrsObjectRegistrationBatcher(av)

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
                    FieldName.LENGTHS_FIELD in record.info,
                    FieldName.REPEAT_SUBUNIT_LENGTHS_FIELD in record.info,
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
            for vrs_id, start, end, state, length, repeat_subunit_length in zip(
                record.info[FieldName.IDS_FIELD],
                record.info[FieldName.STARTS_FIELD],
                record.info[FieldName.ENDS_FIELD],
                record.info[FieldName.STATES_FIELD],
                record.info[FieldName.LENGTHS_FIELD],
                record.info[FieldName.REPEAT_SUBUNIT_LENGTHS_FIELD],
                strict=True,
            ):
                if vrs_id == ".":
                    continue
                true_state = "" if state == "." else state
                if isinstance(true_state, str):
                    true_state = vrs_models.sequenceString(true_state)

                seq_ref = vrs_models.SequenceReference(refgetAccession=refget_accession)
                location = vrs_models.SequenceLocation(
                    sequenceReference=seq_ref, start=start, end=end
                )
                location_id = ga4gh_identify(location)
                location.id = location_id

                if length != "." and repeat_subunit_length != ".":
                    sequence_expression = vrs_models.ReferenceLengthExpression(
                        length=length,
                        repeatSubunitLength=repeat_subunit_length,
                        sequence=true_state,
                    )
                else:
                    sequence_expression = vrs_models.LiteralSequenceExpression(
                        sequence=true_state
                    )

                allele = vrs_models.Allele(location=location, state=sequence_expression)
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
                        sequence_expression,
                    )
                    conflict_logfile.write(
                        f"{vrs_id},{assembly},{record.chrom},{record.pos},{start},{end},{sequence_expression},{new_vrs_id}\n"
                    )
                vrs_object_registration_batcher.add_to_batch(allele)

            # register the final batch of alleles (since the last batch will likely be smaller than the batch size limit)
            vrs_object_registration_batcher.register_batch()

    return conflict_logfile_path
