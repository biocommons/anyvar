"""Test search functionality."""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_search(restapi_client: TestClient, preloaded_alleles: dict):
    """Test basic search functions."""
    for allele in preloaded_alleles.values():
        start = allele["variation"]["location"]["start"]
        end = allele["variation"]["location"]["end"]
        refget_ac = allele["variation"]["location"]["sequenceReference"][
            "refgetAccession"
        ]
        accession = f"ga4gh:{refget_ac}"
        resp = restapi_client.get(
            f"/search?accession={accession}&start={start}&end={end}"
        )
        assert resp.status_code == HTTPStatus.OK

        resp_json = resp.json()

        assert len(resp_json["variations"]) == 1

        assert resp_json["variations"][0] == allele["variation"]
