import pytest
from ga4gh.vrs.dataproxy import _DataProxy

import anyvar.utils.functions as util_funcs
from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.storage import _Storage
from anyvar.translate.translate import _Translator

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
    "ga4gh:CN.LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
)


# variation object input that can be lifted over successfully from GRCH38 > GRCH37: allele, Range start/end coordinates, negative strand
allele_ranged_negative_grch38_variant_object = (
    {
        "type": "Allele",
        "location": {
            "sequenceReference": {
                "type": "SequenceReference",
                "refgetAccession": "SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
            },
            "start": [None, 30417575],
            "end": [31394018, None],
            "type": "SequenceLocation",
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    },
    "ga4gh:VA.fdsjDZeIznBPBH7wd5mIgtMhAAeZ1zGf",
)

# variation object input that can be lifted over successfully from GRCH38 > GRCH37: allele, integer start/end coordinates, unknown positive/negative strand
allele_int_unknown_grch38_variant_object = (
    {
        "type": "Allele",
        "location": {
            "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
            "end": 87894077,
            "start": 87894076,
            "sequenceReference": {
                "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
                "type": "SequenceReference",
            },
            "type": "SequenceLocation",
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    },
    "ga4gh:VA.0viMZeimc8A0MDQviRWyqqc0RfYazQjq",
)

# - /variation input that can be lifted over successfully from GRCH37 > GRCH38
# @pytest.fixture(scope="module")
# def negative_grch37_variant_id() -> str:
#  return "NC_000007.13:g.140453136A>T"
# ^ This is GRCH37, and on the Negative strand


# FAILURES

# - /vrs_variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly
# - /variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly

# - don't need to liftover because we already have a stored liftaver annotation
# ^ Run any of the above a second time

# - case where initial registration failed and we don't have a vrs_id


# - case where the variant is on an unsupported assembly
@pytest.fixture(scope="module")
def unsupported_assembly_variant() -> dict:
    return {
        "type": "CopyNumberChange",
        "location": {
            "start": [15400349, 15414665],
            "end": [16308334, 16345666],
            "type": "SequenceLocation",
            "sequenceReference": {"type": "SequenceReference", "refgetAccession": ...},
        },
        "copyChange": "complete genomic loss",
    }


# ^ This is on GRCH36


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
        allele_ranged_negative_grch38_variant_object,
        allele_int_unknown_grch38_variant_object,
    ],
)
def test_liftover_annotation(variation_input, expected_output, seqrepo_dataproxy):
    annotation_value = util_funcs.get_liftover_annotation(
        variation_input, seqrepo_dataproxy
    )
    assert annotation_value == expected_output


# Failure cases
# def test_duplicate_liftover_annotation(client, alleles):
#     allele_id, allele_object = next(iter(alleles.items()))

#     # purposefully register the variant twice
#     response = client.put("/variation", json=allele_object["params"])
#     response = client.put("/variation", json=allele_object["params"])

#     # Check annotation store - should only have ONE 'liftover' annotation for the variant
