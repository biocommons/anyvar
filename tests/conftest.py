import json
import os
from pathlib import Path

import pytest

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.storage.base_storage import Storage

pytest_plugins = ("celery.contrib.pytest",)


# TODO add back
# def pytest_collection_modifyitems(items):
#     """Modify test items in place to ensure test modules run in a given order."""
#     module_order = [
#         "test_lifespan",
#         "test_variation",
#         "test_general",
#         "test_location",
#         "test_search",
#         "test_annotate_vcf",
#         "test_ingest_vcf",
#         "test_storage_implementation",
#         "test_no_db",
#         "test_liftover",
#     ]
#     # remember to add new test modules to the order constant:
#     assert len(module_order) == len(list(Path(__file__).parent.rglob("test_*.py")))
#     items.sort(key=lambda i: module_order.index(i.module.__name__))


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide Path instance pointing to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def alleles(test_data_dir: Path):
    with (test_data_dir / "variations.json").open() as f:
        data = json.load(f)
        return data["alleles"]


@pytest.fixture(scope="session")
def copy_number_variations(test_data_dir: Path):
    with (test_data_dir / "variations.json").open() as f:
        data = json.load(f)
        return data["copy_numbers"]


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


@pytest.fixture(scope="module")
def storage():
    """Provide live storage instance from factory.

    Configures from env var ``ANYVAR_TEST_STORAGE_URI``. Defaults to a Postgres DB
    named ``anyvar_test``
    """
    storage_uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage


@pytest.fixture(scope="module")
def anyvar_instance(storage: Storage):
    """Provide a test AnyVar instance"""
    translator = create_translator()
    return AnyVar(object_store=storage, translator=translator)
