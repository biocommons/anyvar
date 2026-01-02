"""Tests snowflake storage implementation methods directly."""

import os

import pytest
from ga4gh.vrs import models

from anyvar.storage.snowflake import SnowflakeObjectStore

from .storage_test_funcs import (
    run_alleles_crud,
    run_annotations_crud,
    run_db_lifecycle,
    run_incomplete_objects_error,
    run_mappings_crud,
    run_query_max_rows,
    run_search_alleles,
    run_sequencelocations_crud,
    run_sequencereferences_crud,
)

pytestmark = pytest.mark.snowflake


@pytest.fixture(scope="module")
def snowflake_storage():
    """Reset storage state after each test case"""
    storage = SnowflakeObjectStore(db_url=os.environ.get("ANYVAR_TEST_STORAGE_URI"))
    yield storage
    storage.wipe_db()


@pytest.fixture
def snowflake_storage_with_cleanup(snowflake_storage: SnowflakeObjectStore):
    """Reset storage state after each test case"""
    yield snowflake_storage
    snowflake_storage.wipe_db()


def test_db_lifecycle(
    snowflake_storage: SnowflakeObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_db_lifecycle(snowflake_storage, validated_vrs_alleles)


def test_query_max_rows(
    monkeypatch,
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_query_max_rows(monkeypatch, snowflake_storage_with_cleanup, focus_alleles)


def test_alleles_crud(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_alleles_crud(
        snowflake_storage_with_cleanup, focus_alleles, validated_vrs_alleles
    )


def test_incomplete_objects_error(snowflake_storage_with_cleanup: SnowflakeObjectStore):
    run_incomplete_objects_error(snowflake_storage_with_cleanup)


def test_sequencelocations_crud(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencelocations_crud(
        snowflake_storage_with_cleanup, focus_alleles, validated_vrs_alleles
    )


def test_sequencereferences_crud(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencereferences_crud(
        snowflake_storage_with_cleanup, focus_alleles, validated_vrs_alleles
    )


def test_mappings_crud(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_mappings_crud(snowflake_storage_with_cleanup, validated_vrs_alleles)


def test_annotations_crud(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_annotations_crud(snowflake_storage_with_cleanup, focus_alleles)


def test_search_alleles(
    snowflake_storage_with_cleanup: SnowflakeObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_search_alleles(snowflake_storage_with_cleanup, validated_vrs_alleles)
