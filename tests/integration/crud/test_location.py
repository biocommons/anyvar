"""Test location lookup endpoint"""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_location(restapi_client: TestClient, preloaded_alleles: dict):
    """Perform basic location tests"""
    for allele in preloaded_alleles.values():
        key = allele["variation"]["location"]["id"]
        resp = restapi_client.get(f"/object/{key}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele["variation"]["location"]

    # invalid ID
    bad_resp = restapi_client.get("/object/not_a_real_location")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
