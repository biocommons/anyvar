"""Test search functionality."""
from http import HTTPStatus


def test_search(client, alleles):
    """Test basic search functions."""
    for allele in alleles.values():
        start = allele["allele_response"]["object"]["location"]["interval"]["start"]["value"]
        end = allele["allele_response"]["object"]["location"]["interval"]["end"]["value"]
        accession = allele["allele_response"]["object"]["location"]["sequence_id"]
        resp = client.get(f"/search?accession={accession}&start={start}&end={end}")
        assert resp.status_code == HTTPStatus.OK

        resp_json = resp.json()

        assert len(resp_json["variations"]) == 1

        assert resp_json["variations"][0] == allele["allele_response"]["object"]
