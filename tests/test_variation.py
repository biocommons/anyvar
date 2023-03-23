"""Test variation endpoints"""

def test_put_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.put("/variation", json=allele["params"])
        assert resp.status_code == 200
        assert resp.json()["object"]["_id"] == allele_id


def test_put_text(client, text_alleles):
    for allele_id, allele in text_alleles.items():
        resp = client.put("/variation", json=allele["params"])
        assert resp.status_code == 200
        assert resp.json()["object"]["_id"] == allele_id


def test_get_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.get(f"/variation/{allele_id}")
        assert resp.status_code == 200
        assert resp.json()["data"] == allele["allele_response"]["object"]

    bad_resp = client.get("/allele/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == 404


def test_get_text(client, text_alleles):
    for text_allele_id, allele in text_alleles.items():
        resp = client.get(f"/variation/{text_allele_id}")
        assert resp.status_code == 200
        assert resp.json()["data"] == allele["response"]["object"]

    bad_resp = client.get("/text/ga4gh:VT.invalidto2X0cRI1RfWhYG5roEacUbWJ")
    assert bad_resp.status_code == 404
