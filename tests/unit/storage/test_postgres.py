"""Tests postgres storage implementation methods directly."""

import os

import pytest
from ga4gh.vrs import models

from anyvar.storage.postgres import PostgresObjectStore

from .storage_test_funcs import (
    run_alleles_crud,
    run_annotations_crud,
    run_db_lifecycle,
    run_incomplete_objects_error,
    run_mappings_crud,
    run_objects_raises_integrityerror,
    run_query_max_rows,
    run_search_alleles,
    run_sequencelocations_crud,
    run_sequencereferences_crud,
)

pytestmark = pytest.mark.postgresql


@pytest.fixture(scope="session")
def postgres_uri():
    uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    return uri


@pytest.fixture
def postgres_storage(postgres_uri: str):
    """Reset storage state after each test case"""
    storage = PostgresObjectStore(postgres_uri)
    yield storage
    storage.wipe_db()


@pytest.mark.ci_ok
def test_db_lifecycle(
    postgres_uri: str, validated_vrs_alleles: dict[str, models.Allele]
):
    # set up and populate DB
    storage = PostgresObjectStore(postgres_uri)
    run_db_lifecycle(storage, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_query_max_rows(
    monkeypatch,
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_query_max_rows(monkeypatch, postgres_storage, focus_alleles)


@pytest.mark.ci_ok
def test_alleles_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_alleles_crud(postgres_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_incomplete_objects_error(postgres_storage: PostgresObjectStore):
    run_incomplete_objects_error(postgres_storage)


@pytest.mark.ci_ok
def test_objects_raises_integrityerror(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_objects_raises_integrityerror(postgres_storage, focus_alleles)


@pytest.mark.ci_ok
def test_sequencelocations_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencelocations_crud(postgres_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_sequencereferences_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencereferences_crud(postgres_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_mappings_crud(
    postgres_storage: PostgresObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_mappings_crud(postgres_storage, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_annotations_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_annotations_crud(postgres_storage, focus_alleles)


def test_search_alleles(
    postgres_storage: PostgresObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_search_alleles(postgres_storage, validated_vrs_alleles)
