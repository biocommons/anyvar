from http import HTTPStatus

from fastapi.testclient import TestClient


def test_get_allele(restapi_client: TestClient, preloaded_alleles: dict[str, str]):
    for allele_id, allele_fixture in preloaded_alleles.items():
        resp = restapi_client.get(f"/object/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele_fixture["variation"]

    bad_resp = restapi_client.get("/object/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
