"""Test Duckdb specific storage integration methods
and the async batch insertion

Uses mocks for database integration
"""

import os

from sqlalchemy_mocks import MockEngine, MockStmtSequence, MockVRSObject

from anyvar.restapi.schema import VariationStatisticType
from anyvar.storage.duckdb import DuckdbObjectStore

vrs_object_table_name = os.environ.get("ANYVAR_SQL_STORE_TABLE_NAME", "vrs_objects")


def test_create_schema(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(False,)],
        )
        .add_stmt(
            f"CREATE TABLE {vrs_object_table_name} ( vrs_id TEXT PRIMARY KEY, vrs_object JSON )",
            None,
            [(None,)],
        )
    )
    sf = DuckdbObjectStore("duckdb:///somefile/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()


def test_create_schema_exists(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence().add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
    )
    sf = DuckdbObjectStore("postgres://account/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()


def test_add_one_item(mocker):
    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        .add_stmt(
            f"""
            INSERT INTO {vrs_object_table_name} (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object) ON CONFLICT (vrs_id) DO NOTHING
            """,
            {"vrs_id": "ga4gh:VA.01", "vrs_object": MockVRSObject("01").to_json()},
            [(1,)],
        )
    )
    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value", table_name=vrs_object_table_name
    )
    sf["ga4gh:VA.01"] = MockVRSObject("01")
    sf.close()
    assert mock_eng.were_all_execd()


def test_add_many_items(mocker):
    tmp_table_name = f"tmp_{vrs_object_table_name}"
    create_tmp_statement = f"""
        CREATE TEMP TABLE {tmp_table_name}
        AS FROM {vrs_object_table_name} LIMIT 0
    """
    insert_tmp_statement = f"""
        INSERT INTO {tmp_table_name} (vrs_id, vrs_object)
        VALUES (:vrs_id, :vrs_object)
    """
    insert_final_statement = f"""
        INSERT INTO {vrs_object_table_name}
        SELECT * FROM {tmp_table_name}
        ON CONFLICT (vrs_id) DO NOTHING"""
    drop_statement = f"DROP TABLE {tmp_table_name}"
    insert_sleep_time = 2

    vrs_id_object_pairs = [
        ("ga4gh:VA.01", MockVRSObject("01")),
        ("ga4gh:VA.02", MockVRSObject("02")),
        ("ga4gh:VA.03", MockVRSObject("03")),
        ("ga4gh:VA.04", MockVRSObject("04")),
        ("ga4gh:VA.05", MockVRSObject("05")),
        ("ga4gh:VA.06", MockVRSObject("06")),
        ("ga4gh:VA.07", MockVRSObject("07")),
        ("ga4gh:VA.08", MockVRSObject("08")),
        ("ga4gh:VA.09", MockVRSObject("09")),
        ("ga4gh:VA.10", MockVRSObject("10")),
        ("ga4gh:VA.11", MockVRSObject("11")),
    ]
    print(f"{insert_tmp_statement=}")
    params_0_1 = [
        {"vrs_id": name, "vrs_object": value.to_json()}
        for name, value in vrs_id_object_pairs[0:2]
    ]
    print(f"{params_0_1=}")

    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        # Batch 1
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[0:2]
            ],
            [(2,)],  # Not used, just can't be None
            insert_sleep_time,  # Sleep time to allow background thread to run
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 2
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[2:4]
            ],
            [(2,)],
            insert_sleep_time,
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 3
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[4:6]
            ],
            [(2,)],
            insert_sleep_time,
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 4
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[6:8]
            ],
            [(2,)],
            insert_sleep_time,
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 5
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[8:10]
            ],
            [(2,)],
            insert_sleep_time,
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 6
        .add_stmt(create_tmp_statement, None, [("Table created",)])
        .add_stmt(
            insert_tmp_statement,
            [
                {"vrs_id": name, "vrs_object": value.to_json()}
                for name, value in vrs_id_object_pairs[10:12]
            ],
            [(2,)],
            insert_sleep_time,
        )
        .add_stmt(insert_final_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
    )

    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value",
        batch_limit=2,
        table_name=vrs_object_table_name,
        max_pending_batches=4,
        flush_on_batchctx_exit=False,
    )
    with sf.batch_manager(sf):
        sf.wait_for_writes()
        assert sf.num_pending_batches() == 0
        sf[vrs_id_object_pairs[0][0]] = vrs_id_object_pairs[0][1]
        sf[vrs_id_object_pairs[1][0]] = vrs_id_object_pairs[1][1]
        assert sf.num_pending_batches() > 0
        sf.wait_for_writes()
        assert sf.num_pending_batches() == 0
        sf[vrs_id_object_pairs[2][0]] = vrs_id_object_pairs[2][1]
        sf[vrs_id_object_pairs[3][0]] = vrs_id_object_pairs[3][1]
        sf[vrs_id_object_pairs[4][0]] = vrs_id_object_pairs[4][1]
        sf[vrs_id_object_pairs[5][0]] = vrs_id_object_pairs[5][1]
        sf[vrs_id_object_pairs[6][0]] = vrs_id_object_pairs[6][1]
        sf[vrs_id_object_pairs[7][0]] = vrs_id_object_pairs[7][1]
        sf[vrs_id_object_pairs[8][0]] = vrs_id_object_pairs[8][1]
        sf[vrs_id_object_pairs[9][0]] = vrs_id_object_pairs[9][1]
        sf[vrs_id_object_pairs[10][0]] = vrs_id_object_pairs[10][1]

    assert sf.num_pending_batches() > 0
    sf.close()
    assert sf.num_pending_batches() == 0
    assert mock_eng.return_value.were_all_execd()


def test_insertion_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        .add_stmt(
            f"""
            SELECT COUNT(*) AS c
              FROM {vrs_object_table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') > 1
            """,
            None,
            [(12,)],
        )
    )
    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value",
        table_name=vrs_object_table_name,
    )
    assert sf.get_variation_count(VariationStatisticType.INSERTION) == 12
    sf.close()
    assert mock_eng.were_all_execd()


def test_substitution_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        .add_stmt(
            f"""
            SELECT COUNT(*) AS c
              FROM {vrs_object_table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 1
            """,
            None,
            [(13,)],
        )
    )
    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value",
        table_name=vrs_object_table_name,
    )
    assert sf.get_variation_count(VariationStatisticType.SUBSTITUTION) == 13
    sf.close()
    assert mock_eng.were_all_execd()


def test_deletion_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        .add_stmt(
            f"""
            SELECT COUNT(*) AS c
              FROM {vrs_object_table_name}
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 0
            """,
            None,
            [(14,)],
        )
    )
    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value",
        table_name=vrs_object_table_name,
    )
    assert sf.get_variation_count(VariationStatisticType.DELETION) == 14
    sf.close()
    assert mock_eng.were_all_execd()


def test_search_vrs_objects(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(
        MockStmtSequence()
        .add_stmt(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{vrs_object_table_name}')",
            None,
            [(True,)],
        )
        .add_stmt(
            f"""
            SELECT vrs_object
            FROM {vrs_object_table_name}
            WHERE (vrs_object->>'type' = :type)
                AND (vrs_object->>'location' IN (
                    SELECT vrs_id FROM {vrs_object_table_name}
                    WHERE (CAST (vrs_object->>'start' AS INTEGER) >= :start)
                        AND (CAST (vrs_object->>'end' AS INTEGER) <= :end)
                        AND (vrs_object->'sequenceReference'->>'refgetAccession' = :refgetAccession)
                ))
            """,  # noqa: S608
            {
                "type": "Allele",
                "start": 123456,
                "end": 123457,
                "refgetAccession": "MySQAccId",
            },
            [({"id": 1},), ({"id": 2},)],
        )
    )
    sf = DuckdbObjectStore(
        "duckdb:///somefile/?param=value",
        table_name=vrs_object_table_name,
    )
    variations = sf.search_variations("MySQAccId", 123456, 123457)
    sf.close()
    assert len(variations) == 2
    assert "id" in variations[0] and variations[0]["id"] == 1  # noqa: PT018
    assert "id" in variations[1] and variations[1]["id"] == 2  # noqa: PT018
    assert mock_eng.were_all_execd()
