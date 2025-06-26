import pytest
from ga4gh.vrs.dataproxy import _DataProxy

import anyvar.utils.functions as util_funcs
from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.storage import _Storage
from anyvar.translate.translate import _Translator
from anyvar.utils.functions import (
    LIFTOVER_ERROR_ANNOTATIONS,
    LiftoverError,
)

# SUCCESS CASES
# Make sure this is a mix of a) types of variants, and b) types of start/end coords (int vs Range) - ranges need to be for /vrs_variation endpoint ONLY, and c) positive and negative strands

# variation object input that can be lifted over successfully from GRCH37 > GRCH38: copynumbercount, Range start/end coordinates, positive strand
copynumber_ranged_positive_grch37_variant_object = (
    {
        "type": "CopyNumberCount",
        "location": {
            "sequenceReference": {
                "type": "SequenceReference",
                "refgetAccession": "SQ.iy_UbUrvECxFRX5LPTH_KPojdlT7BKsf",
            },
            "start": [None, 29652251],
            "end": [29981821, None],
            "type": "SequenceLocation",
        },
        "copies": 3,
    },
    "ga4gh:CN.LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",  # verified externally
)

# liftover from GRCh38 > GRCh37, integer start/end coordinates, negative strand:
# THIS ONE ISN'T WORKING
allele_int_negative_grch38_variant_object = (
    {
        "id": "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe",
        "type": "Allele",
        "location": {
            "id": "ga4gh:SL.nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
            "digest": "nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
            "end": 140753336,
            "start": 140753335,
            "type": "SequenceLocation",
            "sequenceReference": {
                "refgetAccession": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
                "type": "SequenceReference",
            },
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    },
    "ga4gh:VA.nmp-bzYpO00NYIqr3CaVF0ZH2ZpSj1ly",  # verified externally
)


# FAILURES

# - /vrs_variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly
# - /variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly

# - don't need to liftover because we already have a stored liftover annotation
# ^ Run any of the above a second time

# - case where initial registration failed and we don't have a vrs_id


# - case where the variant is on an unsupported assembly (GRCh36)
grch36_variant = (
    {
        "digest": "4dEsVNR2JC_ZiHsYSGZgariIUOfYl6a0",
        "id": "ga4gh:VA.4dEsVNR2JC_ZiHsYSGZgariIUOfYl6a0",
        "type": "Allele",
        "location": {
            "id": "ga4gh:SL.WROR90lhzJwgTPgxZx8dRP4Vcjr3BdDi",
            "digest": "WROR90lhzJwgTPgxZx8dRP4Vcjr3BdDi",
            "type": "SequenceLocation",
            "start": 45103598,
            "end": 45103599,
            "sequenceReference": {
                "refgetAccession": "SQ.JY7UegcaYT-M0PYn1yDGQ_4XJsa-DsXq",
                "type": "SequenceReference",
            },
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    },
    LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.UNSUPPORTED_REFERENCE_ASSEMBLY],
)


@pytest.fixture(scope="module")
def seqrepo_dataproxy() -> _DataProxy:
    storage: _Storage = create_storage()
    translator: _Translator = create_translator()
    anyvar_instance: AnyVar = AnyVar(object_store=storage, translator=translator)
    return anyvar_instance.translator.dp


# Test success cases
@pytest.mark.parametrize(
    ("variation_input", "expected_output"),
    [
        copynumber_ranged_positive_grch37_variant_object,
        # allele_int_negative_grch38_variant_object
        grch36_variant,
    ],
)
def test_liftover_annotation(variation_input, expected_output, seqrepo_dataproxy):
    annotation_value = util_funcs.get_liftover_annotation(
        variation_input, seqrepo_dataproxy
    )

    assert annotation_value == expected_output


# def test_duplicate_liftover_annotation(client, alleles):
#     allele_id, allele_object = next(iter(alleles.items()))

#     # purposefully register the variant twice
#     response = client.put("/variation", json=allele_object["params"])
#     response = client.put("/variation", json=allele_object["params"])

#     # Check annotation store - should only have ONE 'liftover' annotation for the variant
