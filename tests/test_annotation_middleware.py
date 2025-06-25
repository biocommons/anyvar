# tests/test_annotation_middleware.py

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from anyvar.restapi.main import app


def test_variation_input_annotation():
    """Should store input payload for /variation if not already annotated."""
    mock_annotator = MagicMock()
    mock_annotator.get_annotation.return_value = []
    app.state.anyannotation = mock_annotator

    mock_anyvar = MagicMock()
    fake_variation = {
        "id": "ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        "type": "Allele",
        "digest": "d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        "location": {
            "id": "ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
            "type": "SequenceLocation",
            "digest": "JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
            "sequenceReference": {
                "type": "SequenceReference",
                "refgetAccession": "SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
            },
            "start": 36561661,
            "end": 36561663,
        },
        "state": {
            "type": "ReferenceLengthExpression",
            "length": 0,
            "sequence": "",
            "repeatSubunitLength": 2,
        },
    }
    mock_anyvar.translator.translate_variation.return_value = fake_variation
    mock_anyvar.put_object.return_value = fake_variation["id"]
    app.state.anyvar = mock_anyvar

    variation_input = {
        "definition": "NC_000007.13:g.36561662_36561663del",
        "input_type": "Allele",
        "copies": 0,
        "copy_change": "complete genomic loss",
    }

    client = TestClient(app)
    response = client.put("/variation", json=variation_input)

    assert response.status_code == 200
    vrs_id = response.json()["object"]["id"]

    mock_annotator.put_annotation.assert_any_call(
        object_id=vrs_id, annotation_type="input_payload", annotation=variation_input
    )


def test_vrs_variation_output_annotation():
    """Should store object_id for /vrs_variation if not already annotated."""
