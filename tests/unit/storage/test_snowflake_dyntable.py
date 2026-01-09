"""Tests Snowflake storage operations with dynamic tables enabled.
Only the functionality specific to the dynamic tables feature is tested here."""

import os

import pytest
from ga4gh.vrs import models
from sqlalchemy import text

from anyvar.storage import orm
from anyvar.storage.snowflake import SnowflakeObjectStore

pytestmark = pytest.mark.snowflake


@pytest.fixture(scope="module")
def monkeymodule():
    """A module-scoped monkeypatch fixture."""
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture(scope="module")
def snowflake_storage_with_dyn_tables(monkeymodule):
    # first create the storage connector and drop any existing db state
    storage = SnowflakeObjectStore(db_url=os.environ.get("ANYVAR_TEST_STORAGE_URI"))
    with storage.engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Annotation.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.VariationMapping.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Allele.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Location.__tablename__}"))
        conn.execute(
            text(f"DROP TABLE IF EXISTS {orm.SequenceReference.__tablename__}")
        )
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.VrsObject.__tablename__}"))

    # then re-create the storage connector with dynamic tables enabled
    monkeymodule.setenv("ANYVAR_SNOWFLAKE_STORE_USE_DYNAMIC_TABLES", "true")
    monkeymodule.setenv("ANYVAR_SNOWFLAKE_STORE_USE_JOIN_FOR_MERGE", "false")
    storage = SnowflakeObjectStore(db_url=os.environ.get("ANYVAR_TEST_STORAGE_URI"))
    yield storage

    # and finally, drop the tables again
    with storage.engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Annotation.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.VariationMapping.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Allele.__tablename__}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.Location.__tablename__}"))
        conn.execute(
            text(f"DROP TABLE IF EXISTS {orm.SequenceReference.__tablename__}")
        )
        conn.execute(text(f"DROP TABLE IF EXISTS {orm.VrsObject.__tablename__}"))


def test_add_alleles(
    snowflake_storage_with_dyn_tables: SnowflakeObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    """Test adding alleles to snowflake storage with dynamic tables enabled."""

    # add the alleles
    snowflake_storage_with_dyn_tables.add_objects(focus_alleles)

    # refresh the dynamic tables to ensure data is available for querying
    with snowflake_storage_with_dyn_tables.engine.connect() as conn:
        conn.execute(text(f"ALTER DYNAMIC TABLE {orm.Allele.__tablename__} REFRESH"))
        conn.execute(text(f"ALTER DYNAMIC TABLE {orm.Location.__tablename__} REFRESH"))
        conn.execute(
            text(f"ALTER DYNAMIC TABLE {orm.SequenceReference.__tablename__} REFRESH")
        )

    # get 1 allele
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.Allele, [focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]

    # get 2 sequence locations
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.SequenceLocation,
        [focus_alleles[1].location.id, focus_alleles[0].location.id],
    )
    assert len(result) == 2
    assert focus_alleles[0].location in result
    assert focus_alleles[1].location in result

    # get a sequence reference
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.SequenceReference,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            focus_alleles[0].location.sequenceReference.refgetAccession,
        ],
    )
    assert result == [focus_alleles[0].location.sequenceReference]

    # delete data
    snowflake_storage_with_dyn_tables.wipe_db()

    # refresh the dynamic tables to ensure data is available for querying
    with snowflake_storage_with_dyn_tables.engine.connect() as conn:
        conn.execute(text(f"ALTER DYNAMIC TABLE {orm.Allele.__tablename__} REFRESH"))
        conn.execute(text(f"ALTER DYNAMIC TABLE {orm.Location.__tablename__} REFRESH"))
        conn.execute(
            text(f"ALTER DYNAMIC TABLE {orm.SequenceReference.__tablename__} REFRESH")
        )

    # verify that the dynamic tables are empty after wipe
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.Allele, [focus_alleles[0].id]
    )
    assert result == []

    # get 2 sequence locations
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.SequenceLocation,
        [focus_alleles[1].location.id, focus_alleles[0].location.id],
    )
    assert result == []

    # get a sequence reference
    result = snowflake_storage_with_dyn_tables.get_objects(
        models.SequenceReference,
        [
            focus_alleles[0].location.sequenceReference.refgetAccession,
        ],
    )
    assert result == []
