"""Test the `store_input_payload_annotation` function"""

import pytest

variation_endpoint_input = {
    "definition": "NC_000007.13:g.36561662_36561663del",
    "input_type": "Allele",
    "copies": 0,
    "copy_change": "complete genomic loss",
}

vrs_variation_endpoint_input = {
    "location": {
        "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
        "end": 87894077,
        "start": 87894076,
        "sequenceReference": {
            "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
            "type": "SequenceReference",
        },
        "type": "SequenceLocation",
    },
    "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
    "type": "Allele",
}


@pytest.mark.parametrize(
    ("input_payload", "endpoint"),
    [
        (variation_endpoint_input, "/variation"),
        (vrs_variation_endpoint_input, "/vrs_variation"),
    ],
)
def test_input_annotation(input_payload, endpoint, client):
    # Ensure we have a clean slate for each test case
    annotator = client.app.state.anyannotation
    annotator.reset_mock()

    # 1. Register variant and assert that registration was successful
    response = client.put(endpoint, json=input_payload)
    assert response.status_code == 200

    vrs_id = response.json().get("object_id")
    assert vrs_id is not None

    # 2. Assert 'put_annotation' was called (and with the correct params)
    annotator.put_annotation.assert_any_call(
        object_id=vrs_id,
        annotation_type="input_payload",
        annotation={"input_payload": input_payload},
    )
