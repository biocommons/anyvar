import pytest
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar, create_translator
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.storage.base_storage import Storage
from anyvar.utils.funcs import build_vrs_variant_from_dict


@pytest.fixture(scope="module")
def restapi_client(storage: Storage):
    translator = create_translator()
    anyvar_restapi.state.anyvar = AnyVar(object_store=storage, translator=translator)
    return TestClient(app=anyvar_restapi)


@pytest.fixture
def preloaded_alleles(storage: Storage, alleles: dict):
    """Provide alleles that have been loaded into the storage instance for this scope"""
    storage.wipe_db()
    storage.add_objects(
        [build_vrs_variant_from_dict(a["variation"]) for a in alleles.values()]
    )
    return alleles
