"""Test sequence reference lookup endpoint"""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_sequence_reference(restapi_client: TestClient, preloaded_alleles: dict):
    """Perform basic sequence reference tests"""
    for allele in preloaded_alleles.values():
        key = allele["variation"]["location"]["sequenceReference"]["refgetAccession"]
        resp = restapi_client.get(f"/sequence_references/{key}")
        assert resp.status_code == HTTPStatus.OK
        assert (
            resp.json()["data"] == allele["variation"]["location"]["sequenceReference"]
        )

    # invalid ID
    bad_resp = restapi_client.get("/sequence_references/not_a_real_sequence_reference")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
