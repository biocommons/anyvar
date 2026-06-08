"""Test VRS-Python stateless translation endpoints."""

from copy import deepcopy
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from ga4gh.vrs.models import Allele

from anyvar.anyvar import AnyVar, create_storage
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.restapi.schema import ServiceInfo
from anyvar.storage.base import Storage
from anyvar.translate.base import Translator

PREFIX = "/translate"
TRANSLATE_TO_ENDPOINT = f"{PREFIX}/vrs_to_identifiers"
TRANSLATE_FROM_ENDPOINT = f"{PREFIX}/identifier_to_vrs"

HGVS_G = "NC_000007.14:g.140753336A>T"
HGVS_G_ALLELE = {
    "type": "Allele",
    "location": {
        "type": "SequenceLocation",
        "sequenceReference": {
            "type": "SequenceReference",
            "refgetAccession": "SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul",
        },
        "start": 140753335,
        "end": 140753336,
    },
    "state": {"type": "LiteralSequenceExpression", "sequence": "T"},
}

HGVS_G_ALLELE_WITH_IDS = deepcopy(HGVS_G_ALLELE)
HGVS_G_ALLELE_WITH_IDS.update(
    {
        "id": "ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe",
        "digest": "Otc5ovrw906Ack087o1fhegB4jDRqCAe",
    }
)
HGVS_G_ALLELE_WITH_IDS["location"].update(
    {
        "id": "ga4gh:SL.nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
        "digest": "nhul5x5P_fKjGEpY9PEkMIekJfZaKom2",
    }
)


@pytest.fixture
def clean_storage(storage_uri: str):
    """Storage with no objects."""
    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage


@pytest.fixture
def stateless_anyvar(clean_storage: Storage, translator: Translator):
    """AnyVar instance with no objects in storage."""
    return AnyVar(object_store=clean_storage, translator=translator)


@pytest.fixture
def stateless_client(stateless_anyvar: AnyVar):
    """REST API client with no objects in storage."""
    anyvar_restapi.state.anyvar = stateless_anyvar
    anyvar_restapi.state.service_info = ServiceInfo()
    return TestClient(app=anyvar_restapi)


def test_translate_to(
    stateless_client: TestClient,
    clean_storage: Storage,
):
    """Test that translate_to works as expected."""
    response = stateless_client.post(
        TRANSLATE_TO_ENDPOINT,
        json={"allele": deepcopy(HGVS_G_ALLELE)},
    )
    assert response.status_code == HTTPStatus.OK
    response_json = response.json()

    assert response_json == {
        "identifiers": {
            "hgvs": [HGVS_G],
            "spdi": ["NC_000007.14:140753335:1:T"],
        }
    }

    # confirm object not in storage
    assert clean_storage.get_objects(Allele, HGVS_G_ALLELE_WITH_IDS["id"]) == []


def test_translate_to_unknown_identifier(
    stateless_client: TestClient,
):
    """Test that translate_to returns 422 for an Allele with unknown identifier"""
    dummy_allele = deepcopy(HGVS_G_ALLELE)
    dummy_refget_ac = "SQ.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    dummy_allele["location"]["sequenceReference"]["refgetAccession"] = dummy_refget_ac
    response = stateless_client.post(
        TRANSLATE_TO_ENDPOINT,
        json={"allele": dummy_allele},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": f"Identifier not found: 'ga4gh:{dummy_refget_ac}'"
    }


def test_translate_to_protein_allele(
    stateless_client: TestClient,
):
    """Test that translate_to returns 422 for a protein Allele"""
    response = stateless_client.post(
        TRANSLATE_TO_ENDPOINT,
        json={
            "allele": {
                "type": "Allele",
                "location": {
                    "type": "SequenceLocation",
                    "sequenceReference": {
                        "type": "SequenceReference",
                        "refgetAccession": "SQ.cQvw4UsHHRRlogxbWCB8W-mKD4AraM9y",
                    },
                    "start": 599,
                    "end": 600,
                    "sequence": "V",
                },
                "state": {"type": "LiteralSequenceExpression", "sequence": "E"},
            }
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": 'Unable to translate allele to "hgvs": Only nucleic acid variation is currently supported'
    }


def test_translate_to_invalid_allele(
    stateless_client: TestClient,
):
    """Test that translate_to returns 422 for an invalid VRS Allele."""
    response = stateless_client.post(
        TRANSLATE_TO_ENDPOINT,
        json={
            "allele": {
                "type": "Allele",
                "location": None,
                "state": None,
            }
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["detail"]


def test_translate_from(
    stateless_client: TestClient,
    clean_storage: Storage,
):
    """Test that translate_from works as expected."""
    response = stateless_client.get(
        f"{TRANSLATE_FROM_ENDPOINT}/{HGVS_G}",
        params={"fmt": "hgvs"},
    )

    assert response.status_code == HTTPStatus.OK
    response_json = response.json()

    assert response_json == {
        "variation": HGVS_G_ALLELE_WITH_IDS,
    }

    # confirm object not in storage
    vrs_id = response_json["variation"]["id"]
    assert vrs_id == HGVS_G_ALLELE_WITH_IDS["id"]
    assert clean_storage.get_objects(Allele, vrs_id) == []


def test_translate_from_invalid_identifier(
    stateless_client: TestClient,
):
    """Test that translate_from returns 422 for an invalid identifier."""
    response = stateless_client.get(
        f"{TRANSLATE_FROM_ENDPOINT}/dummy",
        params={"fmt": "hgvs"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {"detail": "Unable to parse data as hgvs variation"}


def test_translate_from_invalid_hgvs(
    stateless_client: TestClient,
):
    """Test that translate_from returns 422 for an invalid HGVS expression."""
    invalid_hgvs = "NC_000007.14:g.140753336AT"  # no >
    response = stateless_client.get(
        f"{TRANSLATE_FROM_ENDPOINT}/{invalid_hgvs}",
        params={"fmt": "hgvs"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": f'Unable to parse HGVS expression "{invalid_hgvs}"'
    }


def test_translate_from_unsupported_format(
    stateless_client: TestClient,
):
    """Test that translate_from returns 422 for an unsupported identifier format."""
    response = stateless_client.get(
        f"{TRANSLATE_FROM_ENDPOINT}/7-140753336-A-T",
        params={"fmt": "unsupported"},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": 'Variation class for "7-140753336-A-T" is currently unsupported.'
    }


def test_translate_from_reference_sequence_mismatch(stateless_client):
    """Test that translate_from returns 422 for reference sequence mismatch"""
    response = stateless_client.get(
        f"{TRANSLATE_FROM_ENDPOINT}/7-141053535-A-T",
        params={"fmt": "gnomad", "assembly_name": "GRCh37", "require_validation": True},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": "Reference mismatch at GRCh37:7 position 141053534-141053535 (input gave 'A' but correct ref is 'T')"
    }
