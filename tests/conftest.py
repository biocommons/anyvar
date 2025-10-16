import json
import os
from pathlib import Path

import pytest

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
def alleles(test_data_dir) -> dict:
    """Provide allele object fixtures."""
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
