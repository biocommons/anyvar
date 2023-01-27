"""Test sequence lookup and metadata endpoints."""
import json
import pytest


@pytest.fixture(scope="module")
def vhl(test_data_dir):
    with open(test_data_dir / "sequence.json", "r") as f:
        return json.load(f)["vhl"]


@pytest.fixture(scope="module")
def chr_1(test_data_dir):
    with open(test_data_dir / "sequence.json", "r") as f:
        return json.load(f)["chr1"]


def test_sequence_metadata(client, chr_1, vhl):
    resp = client.get("/sequence-metadata/GRCh38%3A1")
    assert resp.status_code == 200
    assert resp.json == chr_1["metadata"]

    resp = client.get("/sequence-metadata/NM_000551.3")
    assert resp.status_code == 200
    assert resp.json == vhl["metadata"]

    # TODO should handle here: https://github.com/biocommons/anyvar/issues/30
    # resp = client.get("/sequence-metadata/not_real_id")
    # assert resp.status_code == 404


def test_sequence(client, chr_1, vhl):
    resp = client.get("/sequence/GRCh38%3A1?start=10000&end=10010")
    assert resp.status_code == 200
    assert resp.text == chr_1["sequence_10000_10010"]

    resp = client.get("/sequence/refseq%3ANM_000551.3")
    assert resp.status_code == 200
    assert resp.text == vhl["sequence"]

    # TODO 500 error if incorrect casing -- should fix
    # resp = client.get("/sequence/grch38%3a1?start=10000&end=10010")
    # assert resp.status_code == 200
    # assert resp.text == vhl["sequence"]

    # TODO 500 error if unrecognized sequence ID -- should fix
    # resp = client.get("/sequence/not_a_real_seq?start=10000")
    # assert resp.status_code == 200
    # assert resp.text == vhl["sequence"]
