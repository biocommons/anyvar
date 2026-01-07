"""Test variation endpoints"""

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from anyvar.restapi.main import (
    PUT_VRS_VARIATION_EXAMPLE_PAYLOAD,
    VARIATION_EXAMPLE_PAYLOAD,
)
from anyvar.restapi.schema import RegisterVariationResponse, VariationRequest
from anyvar.storage.base_storage import Storage
from anyvar.utils.liftover_utils import ReferenceAssembly


def test_put_allele(restapi_client: TestClient, alleles: dict):
    def assert_put_ok(client, payload, object_id):
        resp = client.put("/variation", json=payload)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["id"] == object_id

    for allele_id, allele in alleles.items():
        register_params = allele.get("register_params")

        if not register_params:
            continue

        assert_put_ok(restapi_client, register_params, allele_id)

        if register_params.get("assembly_name") == ReferenceAssembly.GRCH38.value:
            register_params.pop("assembly_name")
            assert_put_ok(restapi_client, register_params, allele_id)

    # confirm idempotency
    test_allele_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"
    test_allele_fixture = alleles[test_allele_id]
    assert_put_ok(
        restapi_client, test_allele_fixture["register_params"], test_allele_id
    )


@pytest.mark.parametrize(
    ("definition", "err_msg"),
    [
        (
            "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1",
            'Unable to translate "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1"',
        ),
        (
            "NC_000007.13:g.36561662_36561663deletion",
            'Unable to parse HGVS expression "NC_000007.13:g.36561662_36561663deletion"',
        ),
        (
            "19-44908822-A-T",
            "Reference mismatch at GRCh38:19 position 44908821-44908822 (input gave 'A' but correct ref is 'C')",
        ),
    ],
)
def test_put_allele_invalid_request(
    restapi_client: TestClient, definition: str, err_msg: str
):
    resp = restapi_client.post("/variation", json={"definition": definition})
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json() == {"detail": err_msg}


def test_put_variation_example(restapi_client: TestClient, alleles: dict):
    resp = restapi_client.put("/variation", json=VARIATION_EXAMPLE_PAYLOAD)
    assert resp.status_code == HTTPStatus.OK
    expected_id = "ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb"
    assert resp.json()["object_id"] == expected_id
    assert resp.json()["object"] == alleles[expected_id]["variation"]
    assert resp.json()["messages"] == []


def test_put_variations(restapi_client: TestClient, alleles: dict):
    alleles_to_use = {k: v for k, v in alleles.items() if "register_params" in v}

    # add example where translation fails
    alleles_to_use["failure_example"] = {
        "register_params": {
            "definition": "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1",
        },
        "expected_messages": [
            'Unable to translate "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1"'
        ],
    }
    variation_payloads = [
        allele_fixture["register_params"] for allele_fixture in alleles_to_use.values()
    ]

    resp = restapi_client.put("/variations", json=variation_payloads)
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert len(resp_json) == len(variation_payloads)

    for (allele_id, allele_fixture), response_item in zip(
        alleles_to_use.items(), resp_json, strict=True
    ):
        response = RegisterVariationResponse(**response_item)
        assert response.input_variation.model_dump(
            mode="json", exclude_none=True
        ) == VariationRequest(**allele_fixture["register_params"]).model_dump(
            mode="json", exclude_none=True
        ), allele_id

        assert response.messages == allele_fixture.get("expected_messages", []), (
            allele_id
        )
        if allele_id == "failure_example":
            assert response.object is None
            assert response.object_id is None
        else:
            assert response.object is not None
            assert (
                response.object.model_dump(exclude_none=True)
                == allele_fixture["variation"]
            ), allele_id
            assert response.object_id == allele_id, allele_id


def test_put_vrs_variation_allele(restapi_client: TestClient, alleles: dict):
    for allele_id, allele_fixture in alleles.items():
        resp = restapi_client.put("/vrs_variation", json=allele_fixture["variation"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object_id"] == allele_id


def test_put_vrs_variation_example(restapi_client: TestClient, alleles: dict):
    resp = restapi_client.put("/vrs_variation", json=PUT_VRS_VARIATION_EXAMPLE_PAYLOAD)
    assert resp.status_code == HTTPStatus.OK
    expected_id = "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"
    assert resp.json()["object"] == alleles[expected_id]["variation"]
    assert resp.json()["messages"] == []


def test_get_allele(restapi_client: TestClient, preloaded_alleles):
    for allele_id, allele_fixture in preloaded_alleles.items():
        resp = restapi_client.get(f"/object/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele_fixture["variation"]

    bad_resp = restapi_client.get("/object/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND


def test_post_variation_registered(restapi_client: TestClient, preloaded_alleles):
    """Test POST method when variation has already been registered"""
    for allele_fixture in preloaded_alleles.values():
        if "register_params" not in allele_fixture:
            continue

        resp = restapi_client.post("/variation", json=allele_fixture["register_params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == {"data": allele_fixture["variation"], "messages": []}


def test_post_variation_not_registered(
    restapi_client: TestClient, alleles: dict, storage: Storage
):
    """Test POST method when variation has not been registered"""
    storage.wipe_db()
    for allele_id, allele_fixture in alleles.items():
        if "register_params" not in allele_fixture:
            continue

        resp = restapi_client.post("/variation", json=allele_fixture["register_params"])
        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json() == {"detail": f"VRS Object {allele_id} not found"}


@pytest.mark.parametrize(
    ("definition", "err_msg"),
    [
        (
            "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1",
            'Unable to translate "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1"',
        ),
        (
            "NC_000007.13:g.36561662_36561663deletion",
            'Unable to parse HGVS expression "NC_000007.13:g.36561662_36561663deletion"',
        ),
        (
            "19-44908822-A-T",
            "Reference mismatch at GRCh38:19 position 44908821-44908822 (input gave 'A' but correct ref is 'C')",
        ),
    ],
)
def test_post_variation_invalid_request(
    restapi_client: TestClient, definition: str, err_msg: str
):
    """Test POST method with invalid requests"""
    resp = restapi_client.post("/variation", json={"definition": definition})
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json() == {"detail": err_msg}
