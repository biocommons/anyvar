import pytest
from ga4gh.vrs.dataproxy import _DataProxy

import anyvar.utils.functions as util_funcs
from anyvar.anyvar import AnyAnnotation, AnyVar, create_storage, create_translator
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
    {
        "id": "ga4gh:CN.LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",  # verified externally
        "type": "CopyNumberCount",
        "name": None,
        "description": None,
        "aliases": None,
        "extensions": None,
        "digest": "LQAMim_Q7_sXVRLX2UFVsHNOolDsK4Bo",
        "expressions": None,
        "location": {
            "id": "ga4gh:SL.7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
            "type": "SequenceLocation",
            "name": None,
            "description": None,
            "aliases": None,
            "extensions": None,
            "digest": "7HsIbSybxJRfiRNr2r0gz1JNsV-wJJfQ",
            "sequenceReference": {
                "id": None,
                "type": "SequenceReference",
                "name": None,
                "description": None,
                "aliases": None,
                "extensions": None,
                "refgetAccession": "SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
                "residueAlphabet": None,
                "circular": None,
                "sequence": None,
                "moleculeType": None,
            },
            "start": [None, 30417575],
            "end": [31394018, None],
            "sequence": None,
        },
        "copies": 3,
    },
)

allele_int_unknown_grch38_variant = (
    {
        "id": "ga4gh: VA.9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
        "digest": "9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39",
        "type": "Allele",
        "location": {
            "id": "ga4gh: SL.sK161kPiQBsm-qOErlsNRXeT3nvoTLLn",
            "digest": "sK161kPiQBsm-qOErlsNRXeT3nvoTLLn",
            "sequenceReference": {
                "refgetAccession": "SQ.Zu7h9AggXxhTaGVsy7h_EZSChSZGcmgX",
                "type": "SequenceReference",
            },
            "start": 179203760,
            "end": 179203761,
            "type": "SequenceLocation",
        },
        "state": {"sequence": "G", "type": "LiteralSequenceExpression"},
    },
    {
        "aliases": None,
        "description": None,
        "digest": "FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
        "expressions": None,
        "extensions": None,
        "id": "ga4gh:VA.FTRS8BT4hXgVVOnbq4rGPqQo5tZInhoP",
        "location": {
            "aliases": None,
            "description": None,
            "digest": "yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
            "end": 178921549,
            "extensions": None,
            "id": "ga4gh:SL.yuqVJ7v6Q1h7-oXiyVToQn0AsukMMRb8",
            "name": None,
            "sequence": None,
            "sequenceReference": {
                "aliases": None,
                "circular": None,
                "description": None,
                "extensions": None,
                "id": None,
                "moleculeType": None,
                "name": None,
                "refgetAccession": "SQ.VNBualIltAyi2AI_uXcKU7M9XUOuA7MS",
                "residueAlphabet": None,
                "sequence": None,
                "type": "SequenceReference",
            },
            "start": 178921548,
            "type": "SequenceLocation",
        },
        "name": None,
        "state": {
            "aliases": None,
            "description": None,
            "extensions": None,
            "id": None,
            "name": None,
            "sequence": "G",
            "type": "LiteralSequenceExpression",
        },
        "type": "Allele",
    },  # externally verified
)


# FAILURES

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

# Welp my code converts this just fine???
unconvertible_grch37_variant = (
    {
        "id": "ga4gh:VA.gB6yzqX61iGXwY_sJ9B1YzGkolw_NnWX",
        "digest": "gB6yzqX61iGXwY_sJ9B1YzGkolw_NnWX",
        "type": "Allele",
        "location": {
            "id": "ga4gh:SL.RAqMKUTTt3pLnD5HclaY-a6CyZVzENUi",
            "digest": "RAqMKUTTt3pLnD5HclaY-a6CyZVzENUi",
            "type": "SequenceLocation",
            "start": 40411758,
            "end": 40411759,
            "sequenceReference": {
                "refgetAccession": "SQ.ItRDD47aMoioDCNW_occY5fWKZBKlxCX",
                "type": "SequenceReference",
            },
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    },
    LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.COORDINATE_CONVERSION_ERROR],
)

# STILL NEED:
# unconvertible_grch38_variant = (
# )

empty_variation_object = ({}, LIFTOVER_ERROR_ANNOTATIONS[LiftoverError.INPUT_ERROR])


@pytest.fixture(scope="module")
def invalid_variant() -> dict:
    return {
        "location": {
            "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
            "end": 0,
            "start": -1,
            "sequenceReference": {
                "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
                "type": "SequenceReference",
            },
            "type": "SequenceLocation",
        },
        "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
        "type": "Allele",
    }


# STILL NEED:
# - A variant that exists on GRCh38 but not GRCH37
# - A variant with a "location" type that's not "SequenceLocation"
# - A variant where the chromosome can't be determined?? (Is this even a thing?)
# - A variant where the accession can't be converted (not sure if this case would ever get hit, as the coordinate conversion error would probably trigger first?)


@pytest.fixture(scope="module")
def seqrepo_dataproxy() -> _DataProxy:
    storage: _Storage = create_storage()
    translator: _Translator = create_translator()
    anyvar_instance: AnyVar = AnyVar(object_store=storage, translator=translator)
    return anyvar_instance.translator.dp


################################################################################
# Tests for src/anyvar/utils/functions.py > 'get_liftover_annotation' function #
################################################################################
@pytest.mark.parametrize(
    ("variation_input", "expected_output"),
    [
        copynumber_ranged_positive_grch37_variant_object,
        allele_int_unknown_grch38_variant,
        grch36_variant,
        # unconvertible_grch37_variant,
        empty_variation_object,
    ],
)
def test_liftover_annotation(variation_input, expected_output, seqrepo_dataproxy):
    annotation_value = util_funcs.get_liftover_annotation(
        variation_input, seqrepo_dataproxy
    )
    # print("\nannotation_value:", annotation_value)
    # print("expected_output:", expected_output)
    assert annotation_value == expected_output


####################################################################################################
# Tests for the middleware function src/anyvar/restapi/main.py > 'add_genomic_liftover_annotation' #
####################################################################################################
def test_valid_vrs_variant_liftover_annotation(client, alleles):
    allele_id, allele_object = next(iter(alleles.items()))
    client.put("/variation", json=allele_object)

    annotator: AnyAnnotation | None = getattr(client.app.state, "anyannotation", None)
    assert annotator is not None

    liftover_annotations = annotator.get_annotation(allele_id, "liftover")
    assert len(liftover_annotations) > 0


def test_invalid_vrs_variant_liftover_annotation(client, invalid_variant):
    response = client.put("/variation", json=invalid_variant)
    response_object = response.json()
    vrs_id = response_object.get("id", "")

    annotator: AnyAnnotation | None = getattr(client.app.state, "anyannotation", None)
    assert annotator is not None

    # Variant was invalid, so it should not have been registered, and therefore shouldn't have an ID,
    # so we shouldn't make an annotation for it
    liftover_annotations = annotator.get_annotation(vrs_id, "liftover")
    assert len(liftover_annotations) == 0


def test_duplicate_liftover_annotation(client, alleles):
    allele_id, allele_object = next(iter(alleles.items()))

    # purposefully register the variant twice
    client.put("/variation", json=allele_object["params"])
    client.put("/variation", json=allele_object["params"])

    annotator: AnyAnnotation | None = getattr(client.app.state, "anyannotation", None)
    assert annotator is not None

    # Check annotation store - should only have ONE 'liftover' annotation for the variant
    liftover_annotations = annotator.get_annotation(allele_id, "liftover")
    assert len(liftover_annotations) == 1
