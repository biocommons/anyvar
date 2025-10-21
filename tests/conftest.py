import json
import os
from pathlib import Path

import pytest
from ga4gh.vrs import models
from pydantic import BaseModel

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.storage.base_storage import Storage

pytest_plugins = ("celery.contrib.pytest",)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Provide Path instance pointing to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def alleles(test_data_dir: Path):
    class _AlleleFixture(BaseModel):
        """Validate data structure in variations.json"""

        variation: models.Allele
        comment: str | None = None
        register_params: dict[str, str | int] | None = None

    with (test_data_dir / "variations.json").open() as f:
        data = json.load(f)
        alleles = data["alleles"]
        for allele in alleles.values():
            assert _AlleleFixture(**allele), f"Not a valid allele fixture: {allele}"
        return alleles


@pytest.fixture(scope="session")
def copy_number_variations(test_data_dir: Path):
    class _CopyNumberFixture(BaseModel):
        """Validate data structure in variations.json"""

        variation: models.CopyNumberChange | models.CopyNumberCount
        comment: str | None = None
        register_params: dict[str, str | int] | None = None

    with (test_data_dir / "variations.json").open() as f:
        data = json.load(f)
        cns = data["copy_numbers"]
        for cn in cns.values():
            assert _CopyNumberFixture(**cn), (
                f"Not a valid copy number variation fixture: {cn}"
            )
        return cns


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
