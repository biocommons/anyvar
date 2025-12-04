"""Test mapping endpoints"""

from http import HTTPStatus

import pytest

from anyvar.storage.base_storage import Storage
from anyvar.utils import types

DEFAULT_MAPPING_TYPE = types.VariationMappingType.LIFTOVER


@pytest.fixture
def preloaded_allele_pairs(preloaded_alleles: dict):
    """Get preloaded allele pairs"""
    preloaded_alleles_l = [allele["variation"] for allele in preloaded_alleles.values()]
    preloaded_allele_pairs = []
    for i in range(0, len(preloaded_alleles_l), 2):
        try:
            preloaded_allele_pairs.append(preloaded_alleles_l[i : i + 2])
        except ValueError:
            break

    return preloaded_allele_pairs


@pytest.fixture
def stored_variation_mappings(storage: Storage, preloaded_allele_pairs: list):
    """Store variation mappings and return preloaded pairs"""
    for source_vrs_object, dest_vrs_object in preloaded_allele_pairs:
        storage.add_mapping(
            types.VariationMapping(
                source_id=source_vrs_object["id"],
                dest_id=dest_vrs_object["id"],
                mapping_type=DEFAULT_MAPPING_TYPE,
            )
        )

    return preloaded_allele_pairs


@pytest.mark.parametrize("mapping_type", list(types.VariationMappingType))
def test_put_mapping_valid_request(
    restapi_client, preloaded_allele_pairs, mapping_type
):
    """Test valid request for PUT method"""
    for allele_pair in preloaded_allele_pairs:
        source_vrs_object, dest_vrs_object = allele_pair
        source_vrs_id = source_vrs_object["id"]
        dest_vrs_id = dest_vrs_object["id"]

        resp = restapi_client.put(
            f"/object/{source_vrs_id}/mappings",
            json={"dest_id": dest_vrs_id, "mapping_type": mapping_type},
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == {
            "dest_object": dest_vrs_object,
            "dest_object_id": dest_vrs_id,
            "mapping_type": mapping_type,
            "source_object": source_vrs_object,
            "source_object_id": source_vrs_id,
        }


def test_put_mapping_idempotency(restapi_client, preloaded_allele_pairs):
    """Test idempotency for PUT method"""
    source_vrs_object, dest_vrs_object = preloaded_allele_pairs[0]
    source_vrs_id = source_vrs_object["id"]
    dest_vrs_id = dest_vrs_object["id"]
    payload = {"dest_id": dest_vrs_id, "mapping_type": DEFAULT_MAPPING_TYPE}

    # First request
    first_resp = restapi_client.put(f"/object/{source_vrs_id}/mappings", json=payload)
    assert first_resp.status_code == HTTPStatus.OK
    first_data = first_resp.json()

    # Second identical request
    second_resp = restapi_client.put(f"/object/{source_vrs_id}/mappings", json=payload)
    assert second_resp.status_code == HTTPStatus.OK
    second_data = second_resp.json()

    assert second_data == first_data


def test_put_mapping_same_source_and_dest(restapi_client, preloaded_allele_pairs):
    """Test when the source ID and dest ID are the same for PUT method"""
    source_vrs_object, _ = preloaded_allele_pairs[0]
    source_vrs_id = source_vrs_object["id"]

    resp = restapi_client.put(
        f"/object/{source_vrs_id}/mappings",
        json={"dest_id": source_vrs_id, "mapping_type": DEFAULT_MAPPING_TYPE},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        resp.json()["detail"]
        == f"Failed to add annotation: dest_id='{source_vrs_id}' mapping_type='liftover'. source_id cannot equal dest_id: {source_vrs_id}"
    )


def test_put_mapping_invalid_source(restapi_client, preloaded_allele_pairs):
    """Test when an invalid source VRS ID is provided for PUT method"""
    source_vrs_object, _ = preloaded_allele_pairs[0]
    source_vrs_id = source_vrs_object["id"]

    resp = restapi_client.put(
        "/object/ga4gh:VA.invalidsource/mappings",
        json={"dest_id": source_vrs_id, "mapping_type": DEFAULT_MAPPING_TYPE},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {"detail": "VRS Object ga4gh:VA.invalidsource not found"}


def test_put_mapping_invalid_dest(restapi_client, preloaded_allele_pairs):
    """Test when an invalid dest VRS ID is provided for PUT method"""
    source_vrs_object, _ = preloaded_allele_pairs[0]
    source_vrs_id = source_vrs_object["id"]

    resp = restapi_client.put(
        f"/object/{source_vrs_id}/mappings",
        json={"dest_id": "ga4gh:VA.invaliddest", "mapping_type": DEFAULT_MAPPING_TYPE},
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {"detail": "VRS Object ga4gh:VA.invaliddest not found"}


def test_put_mapping_invalid_mapping(restapi_client, preloaded_allele_pairs):
    """Test when an invalid mapping type is provided for PUT method"""
    source_vrs_object, dest_vrs_object = preloaded_allele_pairs[0]
    source_vrs_id = source_vrs_object["id"]
    dest_vrs_id = dest_vrs_object["id"]

    resp = restapi_client.put(
        f"/object/{source_vrs_id}/mappings",
        json={"dest_id": dest_vrs_id, "mapping_type": "invalid_mapping_type"},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        resp.json()["detail"][0]["msg"]
        == "Input should be 'liftover', 'transcription' or 'translation'"
    )


def test_get_mapping_valid_request_found(restapi_client, stored_variation_mappings):
    """Test valid request where result is found for GET method"""
    source_vrs_obj, dest_vrs_obj = stored_variation_mappings[0]
    source_vrs_id = source_vrs_obj["id"]

    resp = restapi_client.get(
        f"/object/{source_vrs_id}/mappings/{DEFAULT_MAPPING_TYPE}"
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        "mappings": [
            {
                "source_id": source_vrs_id,
                "dest_id": dest_vrs_obj["id"],
                "mapping_type": DEFAULT_MAPPING_TYPE,
            }
        ]
    }


def test_get_mapping_valid_request_not_found(restapi_client, stored_variation_mappings):
    """Test valid request where result is not found for GET method"""
    source_vrs_obj, _ = stored_variation_mappings[0]
    source_vrs_id = source_vrs_obj["id"]

    resp = restapi_client.get(f"/object/{source_vrs_id}/mappings/transcription")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {"mappings": []}


def test_get_mapping_invalid_source(restapi_client):
    """Test when an invalid source VRS ID is provided for GET method"""
    resp = restapi_client.get(
        f"/object/ga4gh.VA:invalidsource/mappings/{DEFAULT_MAPPING_TYPE}"
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {"detail": "VRS Object ga4gh.VA:invalidsource not found"}


def test_get_mapping_invalid_mapping(restapi_client, stored_variation_mappings):
    """Test when an invalid mapping type is provided for GET method"""
    source_vrs_obj, _ = stored_variation_mappings[0]
    source_vrs_id = source_vrs_obj["id"]

    resp = restapi_client.get(f"/object/{source_vrs_id}/mappings/invalid_mapping_type")
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        resp.json()["detail"][0]["msg"]
        == "Input should be 'liftover', 'transcription' or 'translation'"
    )
