"""Test variation endpoints"""

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

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

    # try unsupported variation type
    resp = restapi_client.put("/variation", json={"definition": "BRAF amplification"})
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["messages"] == ['Unable to translate "BRAF amplification"']
    assert "object" not in resp_json
    assert "object_id" not in resp_json


def test_put_vrs_variation_allele(restapi_client: TestClient, alleles: dict):
    for allele_id, allele_fixture in alleles.items():
        resp = restapi_client.put("/vrs_variation", json=allele_fixture["variation"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object_id"] == allele_id


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


def test_post_variation_not_registered(storage, restapi_client: TestClient, alleles):
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
            "Unable to translate 'GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1'",
        ),
        (
            "NC_000007.13:g.36561662_36561663deletion",
            "Unsupported HGVS 'NC_000007.13:g.36561662_36561663deletion'",
        ),
        ("19-44908822-A-T", "Invalid definition '19-44908822-A-T'"),
    ],
)
def test_post_variation_invalid_request(
    restapi_client: TestClient, definition, err_msg
):
    """Test POST method with invalid requests"""
    resp = restapi_client.post("/variation", json={"definition": definition})
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"messages": [err_msg]}
