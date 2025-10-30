"""Test location lookup endpoint"""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_location(restapi_client: TestClient, preloaded_alleles: dict):
    """Perform basic location tests"""
    for allele in preloaded_alleles.values():
        key = allele["variation"]["location"]["id"]
        resp = restapi_client.get(f"/locations/{key}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["location"] == allele["variation"]["location"]

    # invalid ID
    bad_resp = restapi_client.get("/locations/not_a_real_location")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
