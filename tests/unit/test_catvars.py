from ga4gh.vrs.models import MoleculeType, SequenceReference

from anyvar.core.categorical_variants import is_expected_molecule_type
from anyvar.translate.vrs_python import VrsPythonTranslator


def test_is_expected_molecule_type(alleles: dict, translator: VrsPythonTranslator):
    seq_ref = SequenceReference(
        **alleles["ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb"]["variation"]["location"][
            "sequenceReference"
        ]
    )
    assert not is_expected_molecule_type(seq_ref, MoleculeType.PROTEIN, translator.dp)
    assert is_expected_molecule_type(seq_ref, MoleculeType.GENOMIC, translator.dp)

    seq_ref = SequenceReference(
        **alleles["ga4gh:VA.VrGVDMrq3BCWHIopVxMDtVpMOrxjfQJC"]["variation"]["location"][
            "sequenceReference"
        ]
    )
    assert not is_expected_molecule_type(seq_ref, MoleculeType.GENOMIC, translator.dp)
    assert is_expected_molecule_type(seq_ref, MoleculeType.PROTEIN, translator.dp)

    seq_ref = SequenceReference(
        **alleles["ga4gh:VA.pc65jiqYvcLLocEPb3msu216eBQ3R-mr"]["variation"]["location"][
            "sequenceReference"
        ]
    )
    assert not is_expected_molecule_type(seq_ref, MoleculeType.GENOMIC, translator.dp)
    assert not is_expected_molecule_type(seq_ref, MoleculeType.PROTEIN, translator.dp)
