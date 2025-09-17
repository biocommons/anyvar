import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.utils.funcs import build_vrs_variant_from_dict

pytest_plugins = ("celery.contrib.pytest",)


def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test modules run in a given order."""
    module_order = [
        "test_lifespan",
        "test_variation",
        "test_general",
        "test_location",
        "test_search",
        "test_annotate_vcf",
        "test_ingest_vcf",
        "test_storage_implementation",
        "test_no_db",
        "test_liftover",
    ]
    # remember to add new test modules to the order constant:
    assert len(module_order) == len(list(Path(__file__).parent.rglob("test_*.py")))
    items.sort(key=lambda i: module_order.index(i.module.__name__))


@pytest.fixture(scope="session", autouse=True)
def storage():
    """Provide API client instance as test fixture"""
    if "ANYVAR_TEST_STORAGE_URI" in os.environ:
        storage_uri = os.environ["ANYVAR_TEST_STORAGE_URI"]
    else:
        storage_uri = "postgresql://postgres:postgres@localhost:5432/anyvar_test"

    storage = create_storage(uri=storage_uri)
    storage.setup()
    storage.wipe_db()
    return storage


@pytest.fixture(scope="session")
def annotator():
    annotator = MagicMock()
    annotator.get_annotation.return_value = []
    return annotator


@pytest.fixture(scope="session")
def client(storage, annotator):
    translator = create_translator()
    anyvar_restapi.state.anyvar = AnyVar(object_store=storage, translator=translator)
    anyvar_restapi.state.anyannotation = annotator
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
def preloaded_alleles(storage, alleles):
    """Preload alleles into the database for tests that need them."""
    storage.add_objects(
        [
            build_vrs_variant_from_dict(a["allele_response"]["object"])
            for a in alleles.values()
        ]
    )
    return alleles


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
