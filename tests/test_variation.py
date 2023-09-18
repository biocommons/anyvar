"""Test variation endpoints"""
from http import HTTPStatus


def test_put_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.put("/variation", json=allele["params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["_id"] == allele_id

    # confirm idempotency
    first_id, first_allele = list(alleles.items())[0]
    resp = client.put("/variation", json=first_allele["params"])
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["object"]["_id"] == first_id

    # try unsupported variation type
    resp = client.put("variation", json={"definition": "BRAF amplification"})
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["messages"] == ["Unable to translate \"BRAF amplification\""]
    assert resp_json["object"] is None
    assert resp_json["object_id"] is None


def test_put_vrs_variation(client, text_alleles):
    for allele_id, allele in text_alleles.items():
        resp = client.put("/vrs_variation", json=allele["params"])
        assert resp.status_code == HTTPStatus.OK

        assert resp.json()["object_id"] == allele_id

    resp = client.put("vrs_variation", json={
        "type": "RelativeCopyNumber",
        "subject": {
            "type": "SequenceLocation",
            "sequence_id": "ga4gh:SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
            "interval": {
                "type": "SequenceInterval",
                "start": {
                    "type": "Number",
                    "value": 140713327
                },
                "end": {
                    "type": "Number",
                    "value": 140924929
                }
            }
        },
        "relative_copy_class": "high-level gain"
    })
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_get_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.get(f"/variation/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele["allele_response"]["object"]

    bad_resp = client.get("/allele/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
