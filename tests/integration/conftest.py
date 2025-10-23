import pytest

from anyvar.storage.base_storage import Storage
from anyvar.utils.funcs import build_vrs_variant_from_dict


@pytest.fixture
def preloaded_alleles(storage: Storage, alleles: dict):
    """Provide alleles that have been loaded into the storage instance for this scope"""
    storage.wipe_db()
    storage.add_objects(
        [build_vrs_variant_from_dict(a["variation"]) for a in alleles.values()]
    )
    return alleles
