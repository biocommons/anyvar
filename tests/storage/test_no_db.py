"""Test storage integration methods when no database is configured"""

from sqlalchemy_mocks import MockVRSObject

from anyvar.anyvar import create_storage
from anyvar.storage.no_db import NoObjectStore


def test_create_storage():
    assert True
    sf = create_storage("")
    assert isinstance(sf, NoObjectStore)


def test_adding_stuff():
    sf = NoObjectStore()
    sf.add_objects([MockVRSObject("01"), MockVRSObject("02")])
    sf.wait_for_writes()
    assert len(list(sf.get_all_object_ids())) == 0
    sf.close()
