"""Test variation endpoints"""
import json
from typing import Dict
from http import HTTPStatus
from copy import deepcopy

import pytest


@pytest.fixture(scope="module")
def copy_numbers(test_data_dir) -> Dict:
    """Provide copy_numbers fixture object."""
    with open(test_data_dir / "variations.json", "r") as f:
        return json.load(f)["copy_numbers"]


def test_put_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.put("/variation", json=allele["params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["id"] == allele_id

    # confirm idempotency
    first_id, first_allele = list(alleles.items())[0]
    resp = client.put("/variation", json=first_allele["params"])
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["object"]["id"] == first_id

    # try unsupported variation type
    resp = client.put("/variation", json={"definition": "BRAF amplification"})
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["messages"] == ['Unable to translate "BRAF amplification"']
    assert "object" not in resp_json
    assert "object_id" not in resp_json


def test_put_copy_number(client, copy_numbers):
    for copy_number_id, copy_number in copy_numbers.items():
        resp = client.put("/variation", json=copy_number["params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["id"] == copy_number_id

    # try unsupported variation type
    resp = client.put("/variation", json={"definition": "BRAF amplification"})
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["messages"] == ['Unable to translate "BRAF amplification"']
    assert "object" not in resp_json


def test_put_vrs_variation(client, alleles, copy_numbers):
    for allele_id, allele in alleles.items():
        params = deepcopy(allele["allele_response"]["object"])
        resp = client.put("/vrs_variation", json=params)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object_id"] == allele_id

    for copy_number_id, copy_number in copy_numbers.items():
        params = deepcopy(copy_number["copy_number_response"]["object"])
        resp = client.put("/vrs_variation", json=params)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object_id"] == copy_number_id


def test_get_allele(client, alleles):
    for allele_id, allele in alleles.items():
        resp = client.get(f"/variation/{allele_id}")
        resp_json = resp.json()
        assert resp.status_code == HTTPStatus.OK
        assert resp_json["data"] == allele["allele_response"]["object"]

    bad_resp = client.get("/variation/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND


def test_get_copy_numbers(client, copy_numbers):
    for copy_number_id, copy_number in copy_numbers.items():
        resp = client.get(f"/variation/{copy_number_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == copy_number["copy_number_response"]["object"]

    bad_resp = client.get("/allele/ga4gh:CX.invalid")
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND
