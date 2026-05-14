from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def braf_extension_payload() -> dict:
    return {
        "name": "clinvar_somatic_classification",
        "value": "Oncogenic",
    }


def test_extension_crud(
    restapi_client: TestClient,
    preloaded_alleles: dict,  # noqa: ARG001
    braf_extension_payload: dict,
):
    braf_v600e_id = "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe"

    # post an extension
    response = restapi_client.post(
        f"/object/{braf_v600e_id}/extensions", json=braf_extension_payload
    )
    response.raise_for_status()
    assert response.json()["extension_name"] == braf_extension_payload["name"]
    assert response.json()["extension_value"] == braf_extension_payload["value"]

    # get an extension
    response = restapi_client.get(
        f"/object/{braf_v600e_id}/extensions/{braf_extension_payload['name']}"
    )
    response.raise_for_status()
    data = response.json()["extensions"]
    assert len(data) == 1
    assert data[0]["name"] == braf_extension_payload["name"]
    assert data[0]["value"] == braf_extension_payload["value"]


def test_get_extension_nonexistent_var(restapi_client: TestClient):
    response = restapi_client.get(
        "/object/vrs_id_that_doesnt_exist/extensions/doesnt_matter"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "detail": "VRS Object vrs_id_that_doesnt_exist not found"
    }


def test_post_extension_nonexistent_var(
    restapi_client: TestClient, braf_extension_payload: dict
):
    response = restapi_client.post(
        "/object/not_a_real_vrs_id/extensions", json=braf_extension_payload
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "VRS Object not_a_real_vrs_id not found"}
