import copy

import pytest
from data.liftover_variants import test_variants

from anyvar.utils import liftover_utils
from anyvar.utils.funcs import build_vrs_variant_from_dict
from anyvar.utils.types import VrsVariation


def extract_variants(variant_name) -> tuple[dict, VrsVariation, str | None]:
    variant_test_case = copy.deepcopy(test_variants[variant_name])
    return (
        variant_test_case["input_variant"],
        variant_test_case["expected_liftover_output"],
        variant_test_case["expected_reverse_liftover_annotation"],
    )


# Forward Success Cases
@pytest.fixture
def copynumber_ranged_positive_grch37_variant():
    return extract_variants("copynumber_ranged_positive_grch37_variant")


@pytest.fixture
def allele_int_negative_grch38_variant():
    return extract_variants("allele_int_negative_grch38_variant")


@pytest.fixture
def allele_int_unknown_grch38_variant():
    return extract_variants("allele_int_unknown_grch38_variant")


# Forward Failure Cases
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


# Cases where forward liftover should be successful
FORWARD_SUCCESS_CASES = [
    "copynumber_ranged_positive_grch37_variant",
    "allele_int_negative_grch38_variant",
    "allele_int_unknown_grch38_variant",
]

# Cases where forward liftover should be unsuccessful
FORWARD_FAILURE_CASES = [
    "grch36_variant",
    "unconvertible_grch37_variant",
    "unconvertible_grch38_variant",
]

# Cases where forward liftover succeeds, and reversing the liftover should reproduce the original input variant.
# e.g., Variant_A on GRCh38 lifts over to Variant_B on GRCh37, which lifts back over to Variant_A again on GRCh38
REVERSE_SUCCESS_CASES = ["copynumber_ranged_positive_grch37_variant"]

# Cases where forward liftover succeeds, but attempting to reverse the liftover should NOT re-produce the original input variant.
# e.g., Variant_A on GRCh38 lifts over to Variant_B on GRCh37, which lifts back over to Variant_C on GRCh38 (instead of lifting back over to Variant_A)
REVERSE_FAILURE_CASES = [
    "allele_int_negative_grch38_variant",
    "allele_int_unknown_grch38_variant",
]

# Cases where liftover should not be attempted
NO_LIFTOVER_CASES = ["empty_variation_object", "invalid_variant"]


####################################################################################
## Tests for src/anyvar/utils/liftover_utils.py > 'get_liftover_variant' function ##
####################################################################################
@pytest.mark.parametrize("variant_fixture_name", FORWARD_SUCCESS_CASES)
def test_forward_liftover_success(request, variant_fixture_name, client):
    variant_input, expected_output, _ = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
    )
    assert lifted_over_variant_output == expected_output


@pytest.mark.parametrize("variant_fixture_name", FORWARD_FAILURE_CASES)
def test_forward_liftover_failure(request, variant_fixture_name, client):
    variant_input, expected_error, _ = request.getfixturevalue(variant_fixture_name)
    with pytest.raises(expected_error):
        liftover_utils.get_liftover_variant(
            build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
        )


@pytest.mark.parametrize("variant_fixture_name", REVERSE_SUCCESS_CASES)
def test_reverse_liftover_success(request, variant_fixture_name, client):
    variant_input, _, _ = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant = liftover_utils.get_liftover_variant(
        build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
    )
    reverse_lifted_over_variant = liftover_utils.get_liftover_variant(
        lifted_over_variant, client.app.state.anyvar
    )
    assert reverse_lifted_over_variant.id == variant_input.get("id")


@pytest.mark.parametrize("variant_fixture_name", REVERSE_FAILURE_CASES)
def test_reverse_liftover_failure(request, variant_fixture_name, client):
    variant_input, _, _ = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant = liftover_utils.get_liftover_variant(
        build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
    )
    reverse_lifted_over_variant = liftover_utils.get_liftover_variant(
        lifted_over_variant, client.app.state.anyvar
    )
    assert reverse_lifted_over_variant.id != variant_input.get("id")


##############################################################################################
## Tests for the middleware function src/anyvar/restapi/main.py > 'add_liftover_annotation' ##
##############################################################################################
@pytest.mark.parametrize(
    "variant_fixture_name",
    FORWARD_SUCCESS_CASES,
)
def test_forward_liftover_annotation_success(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_lifted_over_variant, _ = request.getfixturevalue(
        variant_fixture_name
    )
    client.put("/vrs_variation", json=variant_input)

    # Variants that can be lifted over are annotated with the id of their lifted-over equivalent
    annotator.put_annotation.assert_any_call(
        object_id=variant_input.get("id"),
        annotation_type="liftover",
        annotation={"liftover": expected_lifted_over_variant.id},
    )


@pytest.mark.parametrize(
    "variant_fixture_name",
    FORWARD_FAILURE_CASES,
)
def test_forward_liftover_annotation_failure(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_lifted_over_variant, _ = request.getfixturevalue(
        variant_fixture_name
    )
    client.put("/vrs_variation", json=variant_input)

    # Variants that can't be lifted over are annotated with an error message.
    annotator.put_annotation.assert_called_with(
        object_id=variant_input.get("id"),
        annotation_type="liftover",
        annotation={"liftover": expected_lifted_over_variant.get_error_message()},
    )


@pytest.mark.parametrize(
    "variant_fixture_name",
    [*REVERSE_SUCCESS_CASES, *REVERSE_FAILURE_CASES],
)
def test_reverse_liftover_annotation(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, expected_liftover_variant, expected_reverse_liftover_annotation = (
        request.getfixturevalue(variant_fixture_name)
    )
    client.put("/vrs_variation", json=variant_input)

    # Annotate the lifted-over variant with the id of the original variant
    # OR the appropriate error message
    annotator.put_annotation.assert_any_call(
        object_id=expected_liftover_variant.id,
        annotation_type="liftover",
        annotation={"liftover": expected_reverse_liftover_annotation},
    )


@pytest.mark.parametrize(
    "variant_fixture_name",
    NO_LIFTOVER_CASES,
)
def test_liftover_annotation_not_attempted(request, variant_fixture_name, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    variant_input, _, _ = request.getfixturevalue(variant_fixture_name)
    client.put("/vrs_variation", json=variant_input)

    # Variant was invalid, so it should not have been registered; which means
    # we shouldn't have tried to make any liftover annotations for it at all
    annotator.put_annotation.assert_not_called()
