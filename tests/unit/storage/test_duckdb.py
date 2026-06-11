import pytest
from ga4gh.vrs import models

from anyvar.storage.duckdb import DuckDbObjectStore

from .storage_test_funcs import (
    run_alleles_crud,
    run_db_lifecycle,
    run_extensions_crud,
    run_incomplete_objects_error,
    run_mappings_crud,
    run_objects_raises_integrityerror,
    run_search_alleles,
    run_sequencelocations_crud,
    run_sequencereferences_crud,
)

pytestmark = pytest.mark.duckdb


@pytest.fixture
def duckdb_uri() -> str:
    return "duckdb:///:memory:"


@pytest.fixture
def duckdb_storage(duckdb_uri: str):
    """Reset storage state after each test case"""
    storage = DuckDbObjectStore(duckdb_uri)
    yield storage
    storage.wipe_db()


@pytest.mark.ci_ok
def test_db_lifecycle(duckdb_uri: str, validated_vrs_alleles: dict[str, models.Allele]):
    # set up and populate DB
    storage = DuckDbObjectStore(duckdb_uri)
    run_db_lifecycle(storage, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_alleles_crud(
    duckdb_storage: DuckDbObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_alleles_crud(duckdb_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_incomplete_objects_error(duckdb_storage: DuckDbObjectStore):
    run_incomplete_objects_error(duckdb_storage)


@pytest.mark.ci_ok
def test_objects_raises_integrityerror(
    duckdb_storage: DuckDbObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_objects_raises_integrityerror(duckdb_storage, focus_alleles)


@pytest.mark.ci_ok
def test_sequencelocations_crud(
    duckdb_storage: DuckDbObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencelocations_crud(duckdb_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_sequencereferences_crud(
    duckdb_storage: DuckDbObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_sequencereferences_crud(duckdb_storage, focus_alleles, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_mappings_crud(
    duckdb_storage: DuckDbObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_mappings_crud(duckdb_storage, validated_vrs_alleles)


@pytest.mark.ci_ok
def test_extensions_crud(
    duckdb_storage: DuckDbObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    run_extensions_crud(duckdb_storage, focus_alleles)


def test_search_alleles(
    duckdb_storage: DuckDbObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    run_search_alleles(duckdb_storage, validated_vrs_alleles)
