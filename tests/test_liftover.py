import copy

import pytest
from data.liftover_variants import test_variants

import anyvar.utils.liftover_utils as liftover_utils
from anyvar.utils.funcs import build_vrs_variant_from_dict


def extract_variants(variant_name):
    variant_test_case = copy.deepcopy(test_variants[variant_name])
    return (variant_test_case["variant_input"], variant_test_case["expected_output"])


# Success Cases
@pytest.fixture
def copynumber_ranged_positive_grch37_variant():
    return extract_variants("copynumber_ranged_positive_grch37_variant")


@pytest.fixture
def allele_int_negative_grch38_variant():
    return extract_variants("allele_int_negative_grch38_variant")


@pytest.fixture
def allele_int_unknown_grch38_variant():
    return extract_variants("allele_int_unknown_grch38_variant")


# Failure Cases
@pytest.fixture
def grch36_variant():
    return extract_variants("grch36_variant")


@pytest.fixture
def unconvertible_grch37_variant():
    return extract_variants("unconvertible_grch37_variant")


@pytest.fixture
def unconvertible_grch38_variant():
    return extract_variants("unconvertible_grch38_variant")


# Cases where liftover should not be attempted
@pytest.fixture
def empty_variation_object():
    return extract_variants("empty_variation_object")


@pytest.fixture
def invalid_variant():
    return extract_variants("invalid_variant")


# Cases where liftover should be successful
SUCCESS_CASES = [
    "copynumber_ranged_positive_grch37_variant",
    "allele_int_negative_grch38_variant",
    "allele_int_unknown_grch38_variant",
]

# Cases where liftover should be unsuccessful
FAILURE_CASES = [
    "grch36_variant",
    "unconvertible_grch37_variant",
    "unconvertible_grch38_variant",
]

# Cases where liftover should not be attempted
NO_LIFTOVER_CASES = ["empty_variation_object", "invalid_variant"]


####################################################################################
## Tests for src/anyvar/utils/liftover_utils.py > 'get_liftover_variant' function ##
####################################################################################
@pytest.mark.parametrize("variant_fixture_name", SUCCESS_CASES)
def test_liftover_success(request, variant_fixture_name, client):
    variant_input, expected_output = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
    )
    assert lifted_over_variant_output == expected_output


@pytest.mark.parametrize("variant_fixture_name", FAILURE_CASES)
def test_liftover_failure(request, variant_fixture_name, client):
    variant_input, expected_error = request.getfixturevalue(variant_fixture_name)
    with pytest.raises(expected_error):
        liftover_utils.get_liftover_variant(
            build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
        )


######################################################################################################
## Tests for the middleware function src/anyvar/restapi/main.py > 'add_liftover_annotation' ##
######################################################################################################
@pytest.mark.parametrize(
    "variant_fixture_name",
    SUCCESS_CASES,
)
def test_liftover_annotation_success(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_lifted_over_variant = request.getfixturevalue(
        variant_fixture_name
    )
    client.put("/vrs_variation", json=variant_input)

    annotator.put_annotation.assert_any_call(
        object_id=variant_input.get("id"),
        annotation_type="liftover",
        annotation={"liftover": expected_lifted_over_variant.model_dump().get("id")},
    )

    # TODO: we'll need to update this when we implement logic to verify that the liftover is reversible,
    # because then if the liftover is NOT reversible, this `put_annotation` call won't trigger. See Issue # 195.
    annotator.put_annotation.assert_any_call(
        object_id=expected_lifted_over_variant.model_dump().get("id"),
        annotation_type="liftover",
        annotation={"liftover": variant_input.get("id")},
    )


@pytest.mark.parametrize(
    "variant_fixture_name",
    FAILURE_CASES,
)
def test_liftover_annotation_failure(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_lifted_over_variant = request.getfixturevalue(
        variant_fixture_name
    )
    client.put("/vrs_variation", json=variant_input)

    # Variants that can be registered successfully but are unable to be lifted over are annotated with an error message.
    annotator.put_annotation.assert_called_with(
        object_id=variant_input.get("id"),
        annotation_type="liftover",
        annotation={"liftover": expected_lifted_over_variant.get_error_message()},
    )


@pytest.mark.parametrize(
    "variant_fixture_name",
    NO_LIFTOVER_CASES,
)
def test_liftover_annotation_not_attempted(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, _ = request.getfixturevalue(variant_fixture_name)
    client.put("/vrs_variation", json=variant_input)

    # Variant was invalid, so it should not have been registered; which means
    # we shouldn't have tried to make any liftover annotations for it at all
    annotator.put_annotation.assert_not_called()
