"""Check basic functions of general endpoint(s)"""

def test_info(client):
    response = client.get("/info")
    assert response.status_code == 200
    assert "anyvar" in response.json
    assert "ga4gh.vrs" in response.json


# TODO: this feature is only implemented for the postgres backend
# def test_summary_statistics(client):
#     response = client.get("/summary_statistics/all")
#     assert response.status_code == 200
#     assert response.json == 2
