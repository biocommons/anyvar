"""Test storage integration methods when no database is configured"""

from sqlalchemy_mocks import MockEngine, MockStmtSequence, MockVRSObject

from anyvar.anyvar import create_storage
from anyvar.storage.no_db import NoObjectStore


def test_create_storage():
    sf = create_storage('null')
    assert isinstance(sf, NoObjectStore)


def test_add_one_item():
    sf = NoObjectStore()
    sf["ga4gh:VA.01"] = MockVRSObject("01")
    sf.close()
    assert len(sf) == 1
    assert sf["ga4gh:VA.01"].id == "01"

    sf.wipe_db()
    assert len(sf) == 0


def test_add_many_items():
    vrs_id_object_pairs = [
        ("ga4gh:VA.01", MockVRSObject("01")),
        ("ga4gh:VA.02", MockVRSObject("02")),
        ("ga4gh:VA.03", MockVRSObject("03")),
        ("ga4gh:VA.04", MockVRSObject("04")),
        ("ga4gh:VA.05", MockVRSObject("05")),
        ("ga4gh:VA.06", MockVRSObject("06")),
        ("ga4gh:VA.07", MockVRSObject("07")),
        ("ga4gh:VA.08", MockVRSObject("08")),
        ("ga4gh:VA.09", MockVRSObject("09")),
        ("ga4gh:VA.10", MockVRSObject("10")),
        ("ga4gh:VA.11", MockVRSObject("11")),
    ]
    sf = NoObjectStore()
    with sf.batch_manager(sf):
        for vrs_id, obj in vrs_id_object_pairs:
            sf[vrs_id] = obj
    sf.wait_for_writes()
    assert len(sf) == 0
