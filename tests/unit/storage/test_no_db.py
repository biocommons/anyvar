"""Test storage integration methods when no database is configured"""

import json
import logging

from anyvar.anyvar import create_storage
from anyvar.storage.no_db import NoObjectStore

logger = logging.getLogger(__name__)


class MockVRSObject:
    def __init__(self, id: str):
        self.id = id

    def model_dump(self, exclude_none: bool):
        return {"id": self.id}

    def to_json(self):
        return json.dumps(self.model_dump(exclude_none=True))


def test_storage_factory():
    null_storage = create_storage("")
    assert isinstance(null_storage, NoObjectStore), (
        "Storage factory method isn't creating a no_db instance"
    )


def test_adding_stuff():
    null_storage = NoObjectStore()
    null_storage.add_objects([MockVRSObject("01"), MockVRSObject("02")])
    null_storage.wait_for_writes()
    assert len(list(null_storage.get_all_object_ids())) == 0
    null_storage.close()
