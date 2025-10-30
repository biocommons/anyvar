"""Test variation endpoints"""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_put_allele(restapi_client: TestClient, alleles: dict):
    for allele_id, allele in alleles.items():
        if "register_params" not in allele:
            continue
        resp = restapi_client.put("/variation", json=allele["register_params"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object"]["id"] == allele_id

    # confirm idempotency
    test_allele_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"
    test_allele_fixture = alleles[test_allele_id]
    resp = restapi_client.put("/variation", json=test_allele_fixture["register_params"])
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["object"]["id"] == test_allele_id

    # try unsupported variation type
    resp = restapi_client.put("/variation", json={"definition": "BRAF amplification"})
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["messages"] == ['Unable to translate "BRAF amplification"']
    assert "object" not in resp_json
    assert "object_id" not in resp_json


def test_put_vrs_variation_allele(restapi_client: TestClient, alleles: dict):
    for allele_id, allele_fixture in alleles.items():
        resp = restapi_client.put("/vrs_variation", json=allele_fixture["variation"])
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["object_id"] == allele_id


def test_get_allele(restapi_client: TestClient, preloaded_alleles):
    for allele_id, allele_fixture in preloaded_alleles.items():
        resp = restapi_client.get(f"/variation/{allele_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"] == allele_fixture["variation"]

    bad_resp = restapi_client.get(
        "/variation/ga4gh:VA.invalid7DSM9KE3Z0LntAukLqm0K2ENn"
    )
    assert bad_resp.status_code == HTTPStatus.NOT_FOUND


# @pytest.fixture(scope="module")
# def copy_numbers(test_data_dir) -> dict:
#     """Provide copy_numbers fixture object."""
#     with (test_data_dir / "variations.json").open() as f:
#         return json.load(f)["copy_numbers"]

# def test_get_copy_numbers(restapi_client, copy_numbers):
#     for copy_number_id, copy_number in copy_numbers.items():
#         resp = restapi_client.get(f"/variation/{copy_number_id}")
#         assert resp.status_code == HTTPStatus.OK
#         assert resp.json()["data"] == copy_number["copy_number_response"]["object"]

#     bad_resp = restapi_client.get("/allele/ga4gh:CX.invalid")
#     assert bad_resp.status_code == HTTPStatus.NOT_FOUND

# def test_put_copy_number(restapi_client, copy_numbers):
#     for copy_number_id, copy_number in copy_numbers.items():
#         resp = restapi_client.put("/variation", json=copy_number["params"])
#         assert resp.status_code == HTTPStatus.OK
#         assert resp.json()["object"]["id"] == copy_number_id

#     # try unsupported variation type
#     resp = restapi_client.put("/variation", json={"definition": "BRAF amplification"})
#     assert resp.status_code == HTTPStatus.OK
#     resp_json = resp.json()
#     assert resp_json["messages"] == ['Unable to translate "BRAF amplification"']
#     assert "object" not in resp_json

# def test_put_vrs_copy_number(restapi_client, copy_numbers):
#     for copy_number_id, copy_number in copy_numbers.items():
#         params = deepcopy(copy_number["copy_number_response"]["object"])
#         resp = restapi_client.put("/vrs_variation", json=params)
#         assert resp.status_code == HTTPStatus.OK
#         assert resp.json()["object_id"] == copy_number_id
