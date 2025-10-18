import os

import pytest
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.utils.funcs import build_vrs_variant_from_dict


@pytest.fixture(scope="module")
def storage():
    """Provide storage instance from factory"""
    storage_uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage


@pytest.fixture(scope="module")
def restapi_client(storage):
    translator = create_translator()
    anyvar_restapi.state.anyvar = AnyVar(object_store=storage, translator=translator)
    return TestClient(app=anyvar_restapi)


@pytest.fixture(scope="module")
def preloaded_alleles(storage, alleles):
    """Preload alleles into the database for tests that need them."""
    storage.add_objects(
        [
            build_vrs_variant_from_dict(a["allele_response"]["object"])
            for a in alleles.values()
        ]
    )
    return alleles
