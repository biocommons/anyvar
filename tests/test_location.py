"""Test location lookup endpoint"""

def test_location(client, alleles):
    for allele in alleles.values():
        key = allele["location_id"]
        resp = client.get(f"/locations/{key}")
        assert resp.status_code == 200
        assert resp.json()["location"] == allele["allele_response"]["object"]["location"]
