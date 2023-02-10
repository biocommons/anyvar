import json
import os
from pathlib import Path
from typing import Dict

import pytest

from anyvar.restapi.webapp import create_app


def pytest_collection_modifyitems(items):
    """Modify test items in place to ensure test modules run in a given order.

    """
    MODULE_ORDER = [
        "test_variation",
        "test_general",
        "test_location",
        "test_sequence",
        "test_find"
    ]
    # remember to add new test modules to the order constant:
    assert len(MODULE_ORDER) == len(list(Path(__file__).parent.rglob("test_*.py")))
    items.sort(key=lambda i: MODULE_ORDER.index(i.module.__name__))


@pytest.fixture(scope="session")
def app():
    """Create app client fixture.

    Uses in-memory store for now. Ideally, CI should be able to set variables
    to test other major storage options.
    """
    if "ANYVAR_TEST_STORAGE_URI" in os.environ:
        os.environ["ANYVAR_STORAGE_URI"] = os.environ["ANYVAR_TEST_STORAGE_URI"]
    else:
        os.environ["ANYVAR_STORAGE_URI"] = "memory:"
    app = create_app()
    app.config.update({"TESTING": True})

    yield app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide Path instance pointing to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def alleles(test_data_dir) -> Dict:
    """Provide allele fixture object."""
    with open(test_data_dir / "alleles.json", "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def text_alleles(test_data_dir) -> Dict:
    """Provide allele fixture object."""
    with open(test_data_dir / "text_alleles.json", "r") as f:
        return json.load(f)
