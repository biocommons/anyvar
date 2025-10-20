import pytest
from ga4gh.vrs import models

from anyvar.anyvar import AnyVar
from anyvar.storage.base_storage import StoredObjectType
from anyvar.utils import liftover_utils
from anyvar.utils.types import VariationMappingType


# Success Cases
@pytest.fixture(scope="session")
def copynumber_ranged_positive_grch37_variant(alleles: dict):
    return {
        "grch37": models.Allele(
            **alleles["ga4gh:CN.CTCgVehH0FEqrlaOMhUsDjKwzavnQegk"]["variation"]
        ),
        "grch38": models.Allele(
            **alleles["ga4gh:CN.fmrn873tRhAiNLybjHlftgHjcAEExPKQ"]["variation"]
        ),
    }


@pytest.fixture(scope="session")
def allele_int_negative_grch38_variant(alleles: dict):
    return {
        "grch37": models.Allele(
            **alleles["ga4gh:VA.nmp-bzYpO00NYIqr3CaVF0ZH2ZpSj1ly"]["variation"]
        ),
        "grch38": models.Allele(
            **alleles["ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe"]["variation"]
        ),
    }


@pytest.fixture
def allele_int_unknown_grch38_variant(alleles: dict):
    return {
        "grch37": models.Allele(
            **alleles["ga4gh:VA.J-gW7La8EblIdT1MfqZzhzbO26lkEH7D"]["variation"]
        ),
        "grch38": models.Allele(
            **alleles["ga4gh:VA.9gW_iJbQAIO3SIxJ9ACyAZA1X2lEgO39"]["variation"]
        ),
    }


@pytest.fixture
def allele_int_rle_grch37_variant(alleles: dict):
    return {
        "grch37": models.Allele(
            **alleles["ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb"]["variation"]
        ),
        "grch38": models.Allele(
            **alleles["ga4gh:VA.QiKnpRR8S7SPoUE-RMUJJbT-RS1akuHA"]["variation"]
        ),
    }


# Failure Cases
@pytest.fixture
def grch36_variant(alleles: dict):
    return {
        "variant": models.Allele(
            **alleles["ga4gh:VA.4dEsVNR2JC_ZiHsYSGZgariIUOfYl6a0"]["variation"]
        ),
        "error": liftover_utils.UnsupportedReferenceAssemblyError(
            "Unable to get reference sequence ID for ga4gh:SQ.JY7UegcaYT-M0PYn1yDGQ_4XJsa-DsXq",
        ),
    }


@pytest.fixture
def unconvertible_grch37_variant(alleles: dict):
    return {
        "variant": models.Allele(
            **alleles["ga4gh:VA.qP-qtMJqKhTEJfpTdAZN9CoIFCRKv4kg"]["variation"]
        ),
        "error": liftover_utils.CoordinateConversionFailureError(),
    }


@pytest.fixture
def unconvertible_grch38_variant(alleles: dict):
    return {
        "variant": models.Allele(
            **alleles["ga4gh:VA.5-m9wM6WTY5osPxLFg1_bITsOwSoMFui"]["variation"]
        ),
        "error": liftover_utils.CoordinateConversionFailureError(),
    }


# Cases where liftover should not be attempted
@pytest.fixture
def empty_variation_object():
    return {
        "variant": {},
        "error": None,
    }


@pytest.fixture
def invalid_variant():
    return {
        "variant": {
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
        },
        "error": None,
    }


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
    request: pytest.FixtureRequest, variant_fixture_name: str, anyvar_instance: AnyVar
):
    fixture = request.getfixturevalue(variant_fixture_name)
    grch37 = fixture["grch37"]
    grch38 = fixture["grch38"]

    # 37 to 38
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        grch37, anyvar_instance
    )
    assert lifted_over_variant_output == grch38

    # 38 to 37
    lifted_over_variant_output = liftover_utils.get_liftover_variant(
        grch38, anyvar_instance
    )
    assert lifted_over_variant_output == grch37


@pytest.mark.parametrize("variant_fixture_name", FAILURE_CASES)
def test_liftover_failure(request, variant_fixture_name, anyvar_instance: AnyVar):
    fixture = request.getfixturevalue(variant_fixture_name)
    variant_input = fixture["variant"]
    expected_error = fixture["error"]
    with pytest.raises(
        type(expected_error),
        match=expected_error.args[0] if expected_error.args else None,
    ):
        liftover_utils.get_liftover_variant(variant_input, anyvar_instance)


######################################################################################################
## Tests for `src/anyvar/utils/liftover_utils.py > 'add_liftover_mapping' ##
######################################################################################################
@pytest.mark.parametrize(
    "variant_fixture_name",
    SUCCESS_CASES,
)
@pytest.mark.parametrize(
    ("src_key", "dst_key"),
    [("grch37", "grch38"), ("grch38", "grch37")],
    ids=["37->38", "38->37"],
)
@pytest.mark.ci_ok
def test_liftover_mapping_success(
    request, variant_fixture_name, src_key: str, dst_key: str, anyvar_instance: AnyVar
):
    fixture = request.getfixturevalue(variant_fixture_name)
    src = fixture[src_key]
    dst = fixture[dst_key]

    # ensure input is present in DB
    anyvar_instance.object_store.add_objects([src])
    liftover_utils.add_liftover_mapping(src, anyvar_instance)

    # mapping and lifted-over variant should be present
    mappings = list(
        anyvar_instance.object_store.get_mappings(src.id, VariationMappingType.LIFTOVER)
    )
    assert len(mappings) == 1
    assert mappings[0].dest_id == dst.id

    result = list(
        anyvar_instance.object_store.get_objects(StoredObjectType.ALLELE, [dst.id])
    )
    assert len(result) == 1


@pytest.mark.parametrize(
    "variant_fixture_name",
    FAILURE_CASES,
)
def test_liftover_mapping_failure(
    request, variant_fixture_name, anyvar_instance: AnyVar
):
    fixture = request.getfixturevalue(variant_fixture_name)
    variant_input = fixture["variant"]
    expected_error = fixture["error"]

    # ensure input is present in DB
    anyvar_instance.object_store.add_objects([variant_input])

    assert liftover_utils.add_liftover_mapping(variant_input, anyvar_instance) == [
        expected_error.get_error_message()
    ]
