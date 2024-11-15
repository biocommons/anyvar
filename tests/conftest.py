import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi

pytest_plugins = ("celery.contrib.pytest",)


def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test modules run in a given order."""
    module_order = [
        "test_lifespan",
        "test_variation",
        "test_general",
        "test_location",
        "test_search",
        "test_vcf",
        "test_sql_storage_mapping",
        "test_postgres",
        "test_snowflake",
    ]
    # remember to add new test modules to the order constant:
    assert len(module_order) == len(list(Path(__file__).parent.rglob("test_*.py")))
    items.sort(key=lambda i: module_order.index(i.module.__name__))


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
def alleles(test_data_dir) -> dict:
    """Provide allele fixture object."""
    with (test_data_dir / "variations.json").open() as f:
        return json.load(f)["alleles"]


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": os.environ.get("CELERY_BROKER_URL", "redis://"),
        "result_backend": os.environ.get("CELERY_BACKEND_URL", "redis://"),
        "task_default_queue": "anyvar_q",
        "event_queue_prefix": "anyvar_ev",
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["application/json"],
    }
