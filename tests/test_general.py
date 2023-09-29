"""Check basic functions of general endpoint(s)"""
from http import HTTPStatus


def test_info(client):
    response = client.get("/info")
    assert response.status_code == HTTPStatus.OK
    assert "anyvar" in response.json()
    assert "ga4gh_vrs" in response.json()


def test_summary_statistics(client):
    response = client.get("/stats/all")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"variation_type": "all", "count": 2}
