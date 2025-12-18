import contextlib
import os
import shutil

import pytest
from celery.contrib.testing.worker import start_worker
from celery.result import AsyncResult
from pytest_mock import MockerFixture
from tests.conftest import build_vrs_variant_from_dict

import anyvar.anyvar
from anyvar.queueing.celery_worker import celery_app
from anyvar.storage.base_storage import Storage


@pytest.fixture
def preloaded_alleles(storage: Storage, alleles: dict):
    """Provide alleles that have been loaded into the storage instance for this scope.

    Utilizing this fixture means that everything in the alleles fixture will be preloaded
    into the storage instance that the test function ultimately receives.
    """
    storage.wipe_db()
    storage.add_objects(
        [build_vrs_variant_from_dict(a["variation"]) for a in alleles.values()]
    )
    return alleles


@pytest.fixture(scope="session")
def vcf_run_id() -> str:
    """Static run ID to use in VCF tests"""
    return "1234"


@pytest.fixture
def celery_context(mocker: MockerFixture, vcf_run_id: str, storage_uri: str):
    """Provide setup/teardown for test cases that use celery workers for VCF operations

    Because the Celery worker doesn't currently take an injectable storage class instance,
    we have to mock the `ANYVAR_STORAGE_URI` connection string to use the test database
    """
    assert anyvar.anyvar.has_queueing_enabled(), "async VCF queueing is not enabled"
    mocker.patch.dict(
        os.environ,
        {
            "ANYVAR_STORAGE_URI": storage_uri,
            "ANYVAR_VCF_ASYNC_WORK_DIR": "tests/tmp_async_work_dir",
        },
    )
    context_manager = start_worker(
        celery_app,
        pool="solo",
        loglevel="info",
        perform_ping_check=False,
        shutdown_timeout=30,
    )
    context_manager.__enter__()
    celery_app.control.purge()
    AsyncResult(vcf_run_id).forget()

    yield

    context_manager.__exit__(None, None, None)
    with contextlib.suppress(FileNotFoundError):
        # a test probably failed early
        shutil.rmtree("tests/tmp_async_work_dir")
