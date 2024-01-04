import json
import os
from pathlib import Path
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi


def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test modules run in a given order."""
    MODULE_ORDER = ["test_variation", "test_general", "test_location", "test_search", "test_vcf", "test_storage_mapping", "test_snowflake"]
    # remember to add new test modules to the order constant:
    assert len(MODULE_ORDER) == len(list(Path(__file__).parent.rglob("test_*.py")))
    items.sort(key=lambda i: MODULE_ORDER.index(i.module.__name__))

@pytest.fixture(scope="session")
def storage():
    """Provide API client instance as test fixture"""
    if "ANYVAR_TEST_STORAGE_URI" in os.environ:
        storage_uri = os.environ["ANYVAR_TEST_STORAGE_URI"]
    else:
        storage_uri = "postgresql://postgres@localhost:5432/anyvar_test"

    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage

@pytest.fixture(scope="session")
def client(storage):
    translator = create_translator()
    anyvar_restapi.state.anyvar = AnyVar(object_store=storage, translator=translator)
    return TestClient(app=anyvar_restapi)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide Path instance pointing to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def alleles(test_data_dir) -> Dict:
    """Provide allele fixture object."""
    with open(test_data_dir / "variations.json", "r") as f:
        return json.load(f)["alleles"]
