"""Provide core typing/structure for categorical variants."""

import logging

from ga4gh.cat_vrs import models as cat_vrs_models
from ga4gh.vrs import models as vrs_models
from ga4gh.vrs.dataproxy import _DataProxy
from pydantic import Field, field_validator

_logger = logging.getLogger(__name__)


def is_expected_molecule_type(
    seq_ref: vrs_models.SequenceReference,
    expected_type: vrs_models.MoleculeType,
    dp: _DataProxy,
) -> bool:
    """Validate that the given sequence reference has the expected molecule type

    Currently only intended to support genomic and protein variants since that's what
    we have catvars for

    :param seq_ref: defining allele context's sequence reference object
    :param expected_type: desired molecule type
    :param dp: proxy for seq alias lookup
    :return: whether the sequence reference's molecule type can be validated as consistent
        with the expected molecule type
    """
    if seq_ref.moleculeType == expected_type:
        return True

    refseq_aliases = dp.translate_sequence_identifier(
        f"ga4gh:{seq_ref.refgetAccession}", "refseq"
    )
    if not refseq_aliases:
        _logger.debug(
            "Unable to translate sequence accession %s to a known namespace",
            seq_ref.refgetAccession,
        )
        return False
    raw_seq_type = dp.extract_sequence_type(refseq_aliases[0])
    if expected_type == vrs_models.MoleculeType.GENOMIC:
        return raw_seq_type == "g"
    if expected_type == vrs_models.MoleculeType.PROTEIN:
        return raw_seq_type == "p"
    _logger.debug(
        "Encountered unexpected or unknown sequence type for %s: %s",
        seq_ref.refgetAccession,
        raw_seq_type,
    )
    return False


class _SimpleAlleleCatVar(cat_vrs_models.CategoricalVariant):
    """Abstract class for a simple Defining Allele Constraint-based catvar"""

    id: str  # type: ignore[reportIncompatibleVariableOverride]
    constraints: list[cat_vrs_models.Constraint] = Field(min_length=1, max_length=1)  # type: ignore[reportIncompatibleVariableOverride]

    @field_validator("constraints")
    @classmethod
    def validate_constraints(
        cls, constraints: list[cat_vrs_models.Constraint]
    ) -> list[cat_vrs_models.Constraint]:
        """Validate constraints property

        :param constraints: Constraints property to validate
        :return: Constraints property
        :raises ValueError: If constraints property does not satisfy the requirements
        """
        constraint = constraints[0]  # guaranteed by pydantic to have exactly 1 element
        if not isinstance(constraint.root, cat_vrs_models.DefiningAlleleConstraint):
            raise ValueError("Constraint must be a DefiningAlleleConstraint")  # noqa: TRY004
        return constraints


class ProteinSequenceConsequence(_SimpleAlleleCatVar):
    """ProteinSequenceConsequence catvar

    Validates *shape* of input data, but does not validate *values*, ie that
    given defining allele is of the expected molecule type, because that
    requires external data access to SeqRepo (and that's messy to inject in a FastAPI endpoint).

    The validations performed do differ from the original Cat-VRS recipes, which is why we
    have a separate class.

    It doesn't need any additional code implemented beyond its parent class,
    but we still give it a separate class for mapping purposes in the ORM
    """


class CanonicalAllele(_SimpleAlleleCatVar):
    """CanonicalAllele catvar

    Validates *shape* of input data, but does not validate *values*, ie that
    given defining allele is of the expected molecule type, because that
    requires external data access to SeqRepo (and that's messy to inject in a FastAPI endpoint)

    The validations performed do differ from the original Cat-VRS recipes, which is why we
    have a separate class.

    It doesn't need any additional code implemented beyond its parent class,
    but we still give it a separate class for mapping purposes in the ORM
    """
