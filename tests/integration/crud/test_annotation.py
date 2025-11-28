from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def braf_annotation_payload() -> dict:
    return {
        "annotation_type": "clinvar_somatic_classification",
        "annotation_value": "Oncogenic",
    }


def test_annotation_crud(
    restapi_client: TestClient,
    preloaded_alleles: dict,  # noqa: ARG001
    braf_annotation_payload: dict,
):
    braf_v600e_id = "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe"

    # post an annotation
    response = restapi_client.post(
        f"/object/{braf_v600e_id}/annotations", json=braf_annotation_payload
    )
    response.raise_for_status()
    assert (
        response.json()["annotation_type"] == braf_annotation_payload["annotation_type"]
    )
    assert (
        response.json()["annotation_value"]
        == braf_annotation_payload["annotation_value"]
    )

    # get an annotation
    response = restapi_client.get(
        f"/object/{braf_v600e_id}/annotations/{braf_annotation_payload['annotation_type']}"
    )
    response.raise_for_status()
    data = response.json()["annotations"]
    assert len(data) == 1
    assert data[0]["annotation_type"] == braf_annotation_payload["annotation_type"]
    assert data[0]["annotation_value"] == braf_annotation_payload["annotation_value"]


def test_get_annotation_nonexistent_var(restapi_client: TestClient):
    response = restapi_client.get(
        "/object/vrs_id_that_doesnt_exist/annotations/doesnt_matter"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "detail": "VRS Object vrs_id_that_doesnt_exist not found"
    }


def test_post_annotation_nonexistent_var(
    restapi_client: TestClient, braf_annotation_payload: dict
):
    response = restapi_client.post(
        "/object/not_a_real_vrs_id/annotations", json=braf_annotation_payload
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "VRS Object not_a_real_vrs_id not found"}
