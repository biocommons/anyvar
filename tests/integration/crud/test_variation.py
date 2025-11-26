"""Test variation endpoints"""

from http import HTTPStatus

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
        resp = restapi_client.get(f"/variation/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele_fixture["variation"]

    bad_resp = restapi_client.get(
        "/variation/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn"
    )
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
