import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from ga4gh.vrs import models
from pydantic import BaseModel

from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.storage.base_storage import Storage
from anyvar.translate.translate import Translator
from anyvar.utils.types import VrsVariation

pytest_plugins = ("celery.contrib.pytest",)


def pytest_runtest_setup(item):
    """Skip tests not compatible with the current test database backend"""
    all_dbs = {"postgresql", "snowflake"}
    supported_dbs = all_dbs.intersection(mark.name for mark in item.iter_markers())
    current_db = (
        os.environ.get(
            "ANYVAR_TEST_STORAGE_URI",
            "postgresql://postgres:postgres@localhost:5432/anyvar_test",
        )
        .split("+")[0]
        .split(":")[0]
    )
    if supported_dbs and current_db not in supported_dbs:
        pytest.skip(
            f"Skipping test for {supported_dbs} when current test db is {current_db}"
        )


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load `.env` file.

    Must set `autouse=True` to run before other fixtures or test cases.
    """
    load_dotenv()


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


@pytest.fixture(scope="session")
def storage_uri() -> str:
    """Define test storage URI to employ for all storage instance fixtures

    Uses `ANYVAR_TEST_STORAGE_URI` env var
    """
    return os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )


@pytest.fixture(scope="module")
def storage(storage_uri: str):
    """Provide live storage instance from factory.

    Configures from env var ``ANYVAR_TEST_STORAGE_URI``. Defaults to a Postgres DB
    named ``anyvar_test``
    """
    storage = create_storage(uri=storage_uri)
    storage.wipe_db()
    return storage


@pytest.fixture(scope="session")
def translator():
    return create_translator()


@pytest.fixture(scope="module")
def anyvar_instance(storage: Storage, translator: Translator):
    """Provide a test AnyVar instance"""
    return AnyVar(object_store=storage, translator=translator)


@pytest.fixture(scope="module")
def restapi_client(anyvar_instance: AnyVar):
    anyvar_restapi.state.anyvar = anyvar_instance
    return TestClient(app=anyvar_restapi)


# variation type: VRS-Python model
variation_class_map: dict[str, type[VrsVariation]] = {
    "Allele": models.Allele,
    "CopyNumberCount": models.CopyNumberCount,
    "CopyNumberChange": models.CopyNumberChange,
}


def build_vrs_variant_from_dict(variant_dict: dict) -> VrsVariation:
    """Construct a `VrsVariation` class instance from a dictionary representation of one

    :param variant_dict: a dictionary representation of a `VrsVariation` object
    :return: a `VrsVariation` object
    """
    variant_type = variant_dict.get("type", "")
    return variation_class_map[variant_type](**variant_dict)


@pytest.fixture
def build_vrs_variant_from_dict_function():
    return build_vrs_variant_from_dict
