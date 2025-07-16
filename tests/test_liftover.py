import copy

import pytest
from data.liftover_variants import test_variants
from ga4gh.vrs.dataproxy import _DataProxy

import anyvar.utils.liftover_utils as liftover_utils
from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.storage import _Storage
from anyvar.translate.translate import _Translator


def extract_variant(variant_name):
    variant_test_case = copy.deepcopy(test_variants[variant_name])
    return (variant_test_case["variant_input"], variant_test_case["expected_output"])


@pytest.fixture
def copynumber_ranged_positive_grch37_variant():
    return extract_variant("copynumber_ranged_positive_grch37_variant")


@pytest.fixture
def allele_int_negative_grch38_variant():
    return extract_variant("allele_int_negative_grch38_variant")


@pytest.fixture
def allele_int_unknown_grch38_variant():
    return extract_variant("allele_int_unknown_grch38_variant")


@pytest.fixture
def grch36_variant():
    return extract_variant("grch36_variant")


@pytest.fixture
def unconvertible_grch37_variant():
    return extract_variant("unconvertible_grch37_variant")


@pytest.fixture
def empty_variation_object():
    return extract_variant("empty_variation_object")


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
        "type": "UNSUPPORTED",
    }


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
    "variant_fixture_name",
    [
        "copynumber_ranged_positive_grch37_variant",
        "allele_int_negative_grch38_variant",
        "allele_int_unknown_grch38_variant",
    ],
)
def test_liftover_annotation_success(request, variant_fixture_name, seqrepo_dataproxy):
    variant_input, expected_output = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        variant_input, seqrepo_dataproxy
    )
    assert lifted_over_variant_output == expected_output


@pytest.mark.parametrize(
    "variant_fixture_name",
    [
        "grch36_variant",
        "unconvertible_grch37_variant",
        "empty_variation_object",
    ],
)
def test_liftover_annotation_failure(request, variant_fixture_name, seqrepo_dataproxy):
    variant_input, expected_error = request.getfixturevalue(variant_fixture_name)
    with pytest.raises(expected_error):
        liftover_utils.get_liftover_variant(variant_input, seqrepo_dataproxy)


####################################################################################################
# Tests for the middleware function src/anyvar/restapi/main.py > 'add_genomic_liftover_annotation' #
####################################################################################################


def test_valid_vrs_variant_liftover_annotation(
    client, allele_int_negative_grch38_variant
):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_lifted_over_variant = allele_int_negative_grch38_variant
    client.put("/vrs_variation", json=variant_input)

    annotator.put_annotation.assert_any_call(
        object_id=variant_input.get("id"),
        annotation_type="liftover",
        annotation={"liftover": expected_lifted_over_variant.model_dump().get("id")},
    )

    # TODO: will need to update this when we implement logic to verify that the liftover is reversible
    # prior to adding this annotation for the lifted-over variant that links back to the original
    annotator.put_annotation.assert_any_call(
        object_id=expected_lifted_over_variant.model_dump().get("id"),
        annotation_type="liftover",
        annotation={"liftover": variant_input.get("id")},
    )


def test_invalid_vrs_variant_liftover_annotation(client, invalid_variant):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    client.put("/vrs_variation", json=invalid_variant)

    # Variant was invalid, so it should not have been registered, and therefore shouldn't have an ID;
    # so we shouldn't have tried to make a liftover annotation for it at all
    annotator.put_annotation.assert_not_called()
