"""Test location lookup endpoint"""
from http import HTTPStatus


def test_location(client, alleles):
    """Perform basic location tests"""
    for allele in alleles.values():
        key = allele["location_id"]
        resp = client.get(f"/locations/{key}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["location"] == allele["allele_response"]["object"]["location"]

    # invalid ID
    resp = client.get("/locations/not_a_real_location")
    assert resp.status_code == HTTPStatus.OK
    assert "location" not in resp.json()
