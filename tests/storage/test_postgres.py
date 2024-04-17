"""
Test Postgres specific storage integration methods
and the async batch insertion
"""
import os
from sqlalchemy_mocks import MockEngine, MockStmtSequence, MockVRSObject

from anyvar.restapi.schema import VariationStatisticType
from anyvar.storage.postgres import PostgresObjectStore

def test_create_schema(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(False,)])
        .add_stmt("CREATE TABLE vrs_objects ( vrs_id TEXT PRIMARY KEY, vrs_object JSONB )", None, [("Table created",)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()

def test_create_schema_exists(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()

def test_add_one_item(mocker):
    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
        .add_stmt(
            """
            INSERT INTO vrs_objects (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object) ON CONFLICT DO NOTHING
            """, 
            {"vrs_id": "ga4gh:VA.01", "vrs_object": MockVRSObject('01').to_json()}, [(1,)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    sf["ga4gh:VA.01"] = MockVRSObject('01')
    sf.close()
    assert mock_eng.were_all_execd()

def test_add_many_items(mocker):
    tmp_statement = "CREATE TEMP TABLE tmp_table (LIKE vrs_objects2 INCLUDING DEFAULTS)"
    insert_statement = "INSERT INTO vrs_objects2 SELECT * FROM tmp_table ON CONFLICT DO NOTHING"
    drop_statement = "DROP TABLE tmp_table"

    vrs_id_object_pairs = [
        ("ga4gh:VA.01", MockVRSObject('01')),
        ("ga4gh:VA.02", MockVRSObject('02')),
        ("ga4gh:VA.03", MockVRSObject('03')),
        ("ga4gh:VA.04", MockVRSObject('04')),
        ("ga4gh:VA.05", MockVRSObject('05')),
        ("ga4gh:VA.06", MockVRSObject('06')),
        ("ga4gh:VA.07", MockVRSObject('07')),
        ("ga4gh:VA.08", MockVRSObject('08')),
        ("ga4gh:VA.09", MockVRSObject('09')),
        ("ga4gh:VA.10", MockVRSObject('10')),
        ("ga4gh:VA.11", MockVRSObject('11')),
    ]

    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects2')", None, [(True,)])
        # Batch 1
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[0:2]]))
        .add_stmt(insert_statement, None, [(2,)], 5)
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 2
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[2:4]]))
        .add_stmt(insert_statement, None, [(2,)], 4)
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 3
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[4:6]]))
        .add_stmt(insert_statement, None, [(2,)], 3)
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 4
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[6:8]]))
        .add_stmt(insert_statement, None, [(2,)], 5)
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 5
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[8:10]]))
        .add_stmt(insert_statement, None, Exception("query timeout"))
        # Batch 6
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_copy_from("tmp_table", "\n".join([f"{pair[0]}\t{pair[1].to_json()}" for pair in vrs_id_object_pairs[10:11]]))
        .add_stmt(insert_statement, None, [(2,)], 2)
        .add_stmt(drop_statement, None, [("Table dropped",)])
    )

    sf = PostgresObjectStore("postgres://account/?param=value", 2, "vrs_objects2", 4, False)
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
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
        .add_stmt(
            """
            SELECT COUNT(*) AS c 
              FROM vrs_objects
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') > 1
            """,
            None, [(12,)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.INSERTION) == 12
    sf.close()
    assert mock_eng.were_all_execd()

def test_substitution_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
        .add_stmt(
            """
            SELECT COUNT(*) AS c 
              FROM vrs_objects
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 1
            """,
            None, [(13,)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.SUBSTITUTION) == 13
    sf.close()
    assert mock_eng.were_all_execd()

def test_deletion_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
        .add_stmt(
            """
            SELECT COUNT(*) AS c 
              FROM vrs_objects
             WHERE LENGTH(vrs_object -> 'state' ->> 'sequence') = 0
            """,
            None, [(14,)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.DELETION) == 14
    sf.close()
    assert mock_eng.were_all_execd()

def test_search_vrs_objects(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE tablename = 'vrs_objects')", None, [(True,)])
        .add_stmt(
            """
            SELECT vrs_object 
              FROM vrs_objects
             WHERE vrs_object->>'type' = %s 
               AND vrs_object->>'location' IN (
                SELECT vrs_id FROM vrs_objects
                 WHERE CAST (vrs_object->>'start' AS INTEGER) >= %s
                   AND CAST (vrs_object->>'end' AS INTEGER) <= %s
                   AND vrs_object->'sequenceReference'->>'refgetAccession' = %s)
            """,
            [ "Allele", 123456, 123457, "MySQAccId" ], [({"id": 1},), ({"id": 2},)])
    )
    sf = PostgresObjectStore("postgres://account/?param=value")
    vars = sf.search_variations("MySQAccId", 123456, 123457)
    sf.close()
    assert len(vars) == 2
    assert "id" in vars[0] and vars[0]["id"] == 1
    assert "id" in vars[1] and vars[1]["id"] == 2
    assert mock_eng.were_all_execd()