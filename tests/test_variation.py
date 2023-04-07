"""Test variation endpoints"""
from http import HTTPStatus


def test_put_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.put("/variation", json=allele["params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["_id"] == allele_id


def test_put_vrs_variation(client, text_alleles):
    for allele_id, allele in text_alleles.items():
        resp = client.put("/vrs_variation", json=allele["params"])
        assert resp.status_code == HTTPStatus.OK

        assert resp.json()["object_id"] == allele_id


def test_get_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.get(f"/variation/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele["allele_response"]["object"]

    bad_resp = client.get("/allele/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
