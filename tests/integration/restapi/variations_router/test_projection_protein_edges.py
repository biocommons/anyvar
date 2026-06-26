"""Protein projection edge-case integration tests through the REST g->c->p path."""

from http import HTTPStatus

import pytest

from anyvar.core import metadata
from anyvar.translate.base import Translator


def _refget(translator: Translator, refseq: str) -> str:
    aliases = translator.dp.translate_sequence_identifier(refseq, "ga4gh")
    assert aliases
    return aliases[0].removeprefix("ga4gh:")


def _put_variation(client, spdi: str):
    response = client.put("/variation", json={"definition": spdi})
    assert response.status_code == HTTPStatus.OK
    return response.json()


def _single_mapping(
    client, source_id: str, mapping_type: metadata.VariationMappingType
):
    response = client.get(f"/object/{source_id}/mappings/{mapping_type}")
    assert response.status_code == HTTPStatus.OK
    mappings = response.json()["mappings"]
    assert len(mappings) == 1
    return mappings[0]["dest_id"]


def _no_mapping(client, source_id: str, mapping_type: metadata.VariationMappingType):
    response = client.get(f"/object/{source_id}/mappings/{mapping_type}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"mappings": []}


def _get_object(client, object_id: str):
    response = client.get(f"/object/{object_id}")
    assert response.status_code == HTTPStatus.OK
    return response.json()["data"]


def _sequence(allele) -> str:
    return allele["state"]["sequence"]


# ClinVar labels these SELENON variants against NM_020451.3, but MANE v1.5
# currently selects NM_206926.2 / NP_996809.1. These cases enter as genomic
# SPDI and assert the same Sec effects after transcript and protein projection.
SELENOCYSTEINE_CASES = [
    pytest.param(
        {
            "clinvar_id": "4490",
            "spdi": "NC_000001.11:25812789:G:A",
            "transcript_refseq": "NM_206926.2",
            "transcript_state": "A",
            "protein_refseq": "NP_996809.1",
            "protein_start": 427,
            "protein_state": "*",
        },
        id="4490-u462-star",
    ),
    pytest.param(
        {
            "clinvar_id": "4495",
            "spdi": "NC_000001.11:25812788:T:G",
            "transcript_refseq": "NM_206926.2",
            "transcript_state": "G",
            "protein_refseq": "NP_996809.1",
            "protein_start": 427,
            "protein_state": "G",
        },
        id="4495-u462g",
    ),
]


@pytest.mark.parametrize("case", SELENOCYSTEINE_CASES)
def test_selenocysteine_projection_edge_cases(
    projected_restapi_client,
    translator: Translator,
    case,
):
    """Project genomic SELENON variants through transcript to Sec protein states."""
    payload = _put_variation(projected_restapi_client, case["spdi"])

    assert payload["messages"] == []
    transcript_id = _single_mapping(
        projected_restapi_client,
        payload["object_id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
    )
    transcript = _get_object(projected_restapi_client, transcript_id)
    assert transcript["location"]["sequenceReference"]["refgetAccession"] == _refget(
        translator, case["transcript_refseq"]
    )
    assert _sequence(transcript) == case["transcript_state"]

    protein_id = _single_mapping(
        projected_restapi_client,
        transcript_id,
        metadata.VariationMappingType.TRANSLATE_TO,
    )
    protein = _get_object(projected_restapi_client, protein_id)
    assert protein["location"]["sequenceReference"]["refgetAccession"] == _refget(
        translator, case["protein_refseq"]
    )
    assert protein["location"]["start"] == case["protein_start"]
    assert protein["location"]["end"] == case["protein_start"] + 1
    assert _sequence(protein) == case["protein_state"]


def test_standard_stop_gain_projects_to_stop(
    projected_restapi_client,
    translator: Translator,
):
    payload = _put_variation(
        projected_restapi_client,
        "NC_000002.12:29073502:C:T",
    )

    assert payload["messages"] == []
    transcript_id = _single_mapping(
        projected_restapi_client,
        payload["object_id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
    )
    transcript = _get_object(projected_restapi_client, transcript_id)
    assert transcript["location"]["sequenceReference"]["refgetAccession"] == _refget(
        translator, "NM_001029883.3"
    )
    assert _sequence(transcript) == "A"

    protein_id = _single_mapping(
        projected_restapi_client,
        transcript_id,
        metadata.VariationMappingType.TRANSLATE_TO,
    )
    protein = _get_object(projected_restapi_client, protein_id)
    assert protein["location"]["sequenceReference"]["refgetAccession"] == _refget(
        translator, "NP_001025054.1"
    )
    assert protein["location"]["start"] == 252
    assert protein["location"]["end"] == 253
    assert _sequence(protein) == "*"


def test_multiresidue_protein_effect_is_skipped(
    projected_restapi_client,
    translator: Translator,
):
    payload = _put_variation(
        projected_restapi_client,
        "NC_000003.12:98592995:ACCTGTGCCAGAGCCTGGCACACCTG:ACCTG",
    )

    assert payload["messages"] == [
        "Projection skipped: could not derive alternate protein state for NP_000088.3"
    ]
    transcript_id = _single_mapping(
        projected_restapi_client,
        payload["object_id"],
        metadata.VariationMappingType.TRANSCRIBE_TO,
    )
    transcript = _get_object(projected_restapi_client, transcript_id)
    assert transcript["location"]["sequenceReference"]["refgetAccession"] == _refget(
        translator, "NM_000097.7"
    )
    _no_mapping(
        projected_restapi_client,
        transcript_id,
        metadata.VariationMappingType.TRANSLATE_TO,
    )
