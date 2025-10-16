import copy

import pytest
from data.liftover_variants import test_variants
from starlette.testclient import TestClient

from anyvar.anyvar import AnyVar
from anyvar.utils import liftover_utils
from anyvar.utils.funcs import build_vrs_variant_from_dict


def extract_variants(variant_name: str) -> tuple:
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


@pytest.fixture
def allele_int_rle_grch37_variant():
    return extract_variants("allele_int_rle_grch37_variant")


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
    # "copynumber_ranged_positive_grch37_variant",  # TODO restore upon support for copy number variants
    "allele_int_rle_grch37_variant",
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
def test_liftover_success(
    request: pytest.FixtureRequest, variant_fixture_name: str, client: TestClient
):
    variant_input, expected_output = request.getfixturevalue(variant_fixture_name)
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
    )
    assert lifted_over_variant_output == expected_output


@pytest.mark.parametrize("variant_fixture_name", FAILURE_CASES)
def test_liftover_failure(request, variant_fixture_name, client):
    variant_input, expected_error = request.getfixturevalue(variant_fixture_name)
    with pytest.raises(
        type(expected_error),
        match=expected_error.args[0] if expected_error.args else None,
    ):
        liftover_utils.get_liftover_variant(
            build_vrs_variant_from_dict(variant_input), client.app.state.anyvar
        )


######################################################################################################
## Tests for `src/anyvar/utils/liftover_utils.py > 'add_liftover_mapping' ##
######################################################################################################
@pytest.mark.parametrize(
    "variant_fixture_name",
    SUCCESS_CASES,
)
def test_liftover_mapping_success(request, variant_fixture_name, client):
    variant_input = build_vrs_variant_from_dict(
        request.getfixturevalue(variant_fixture_name)[0]
    )

    # ensure input is present in DB
    av: AnyVar = client.app.state.anyvar
    av.object_store.add_objects([variant_input])

    liftover_utils.add_liftover_mapping(variant_input, av)


@pytest.mark.parametrize(
    "variant_fixture_name",
    FAILURE_CASES,
)
def test_liftover_mapping_failure(request, variant_fixture_name, client):
    variant_input, expected_error = request.getfixturevalue(variant_fixture_name)
    variant_input = build_vrs_variant_from_dict(variant_input)

    # ensure input is present in DB
    av: AnyVar = client.app.state.anyvar
    av.object_store.add_objects([variant_input])

    assert liftover_utils.add_liftover_mapping(
        variant_input, client.app.state.anyvar
    ) == [expected_error.get_error_message()]
