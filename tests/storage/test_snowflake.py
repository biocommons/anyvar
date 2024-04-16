"""
Test Snowflake specific storage integration methods
and the async batch insertion
"""
from sqlalchemy_mocks import MockEngine, MockStmtSequence, MockVRSObject

from anyvar.restapi.schema import VariationStatisticType
from anyvar.storage.sql_storage import SqlBatchAddMode
from anyvar.storage.snowflake import SnowflakeObjectStore

def test_create_schema(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(0,)])
        .add_stmt("CREATE TABLE vrs_objects ( vrs_id VARCHAR(500) PRIMARY KEY, vrs_object VARIANT )", None, [("Table created",)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()

def test_create_schema_exists(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    sf.close()
    assert mock_eng.were_all_execd()

def test_add_one_item(mocker):
    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
               AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
        .add_stmt(
            """
            MERGE INTO vrs_objects t USING (SELECT :vrs_id AS vrs_id, :vrs_object AS vrs_object) s ON t.vrs_id = s.vrs_id 
            WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
            """, 
            {"vrs_id": "ga4gh:VA.01", "vrs_object": MockVRSObject('01').to_json()}, [(1,)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    sf["ga4gh:VA.01"] = MockVRSObject('01')
    sf.close()
    assert mock_eng.were_all_execd()

def test_add_many_items(mocker):
    tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500), vrs_object VARCHAR)"
    insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object)"
    merge_statement = f"""
        MERGE INTO vrs_objects2 v USING tmp_vrs_objects s ON v.vrs_id = s.vrs_id 
        WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object))
        """
    drop_statement = "DROP TABLE tmp_vrs_objects"

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
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects2')", None, [(1,)])
        # Batch 1
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[0:2]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 2
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[2:4]), [(2,)], 4)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 3
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[4:6]), [(2,)], 3)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 4
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[6:8]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        # Batch 5
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[8:10]), [(2,)], 3)
        .add_stmt(merge_statement, None, Exception("query timeout"))
        # Batch 6
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[10:11]), [(2,)], 2)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value", 2, "vrs_objects2", SqlBatchAddMode.merge, 4, False)
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

def test_batch_add_mode_insert_notin(mocker):
    tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500), vrs_object VARCHAR)"
    insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object)"
    merge_statement = f"""
        INSERT INTO vrs_objects2 (vrs_id, vrs_object)
        SELECT t.vrs_id, PARSE_JSON(t.vrs_object)
          FROM tmp_vrs_objects t
          LEFT OUTER JOIN vrs_objects2 v ON v.vrs_id = t.vrs_id
         WHERE v.vrs_id IS NULL
        """
    drop_statement = "DROP TABLE tmp_vrs_objects"

    vrs_id_object_pairs = [
        ("ga4gh:VA.01", MockVRSObject('01')),
        ("ga4gh:VA.02", MockVRSObject('02')),
    ]

    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects2')", None, [(1,)])
        # Batch 1
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[0:2]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value", 2, "vrs_objects2", SqlBatchAddMode.insert_notin)
    with sf.batch_manager(sf):
        sf[vrs_id_object_pairs[0][0]] = vrs_id_object_pairs[0][1]
        sf[vrs_id_object_pairs[1][0]] = vrs_id_object_pairs[1][1]

    sf.close()
    assert mock_eng.return_value.were_all_execd()

def test_batch_add_mode_insert(mocker):
    tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500), vrs_object VARCHAR)"
    insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (:vrs_id, :vrs_object)"
    merge_statement = f"""
        INSERT INO vrs_objects2 (vrs_id, vrs_object)
        SELECT vrs_id, PARSE_JSON(vrs_object) FROM tmp_vrs_objects
        """
    drop_statement = "DROP TABLE tmp_vrs_objects"

    vrs_id_object_pairs = [
        ("ga4gh:VA.01", MockVRSObject('01')),
        ("ga4gh:VA.02", MockVRSObject('02')),
    ]

    mocker.patch("ga4gh.core.is_pydantic_instance", return_value=True)
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects2')", None, [(1,)])
        # Batch 1
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list(({ "vrs_id": pair[0], "vrs_object": pair[1].to_json() }) for pair in vrs_id_object_pairs[0:2]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value", 2, "vrs_objects2", SqlBatchAddMode.insert)
    with sf.batch_manager(sf):
        sf[vrs_id_object_pairs[0][0]] = vrs_id_object_pairs[0][1]
        sf[vrs_id_object_pairs[1][0]] = vrs_id_object_pairs[1][1]

    sf.close()
    assert mock_eng.return_value.were_all_execd()

def test_insertion_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
        .add_stmt(
            """
            SELECT COUNT(*) 
              FROM vrs_objects
             WHERE LENGTH(vrs_object:state:sequence) > 1
            """,
            None, [(12,)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.INSERTION) == 12
    sf.close()
    assert mock_eng.were_all_execd()

def test_substitution_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
        .add_stmt(
            """
            SELECT COUNT(*) 
              FROM vrs_objects
             WHERE LENGTH(vrs_object:state:sequence) = 1
            """,
            None, [(13,)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.SUBSTITUTION) == 13
    sf.close()
    assert mock_eng.were_all_execd()

def test_deletion_count(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
        .add_stmt(
            """
            SELECT COUNT(*) 
              FROM vrs_objects
             WHERE LENGTH(vrs_object:state:sequence) = 0
            """,
            None, [(14,)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    assert sf.get_variation_count(VariationStatisticType.DELETION) == 14
    sf.close()
    assert mock_eng.were_all_execd()

def test_search_vrs_objects(mocker):
    mock_eng = mocker.patch("anyvar.storage.sql_storage.create_engine")
    mock_eng.return_value = MockEngine()
    mock_eng.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt(
            """
            SELECT COUNT(*) FROM information_schema.tables 
             WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() 
             AND UPPER(table_name) = UPPER('vrs_objects')
            """, 
            None, [(1,)])
        .add_stmt(
            """
            SELECT vrs_object 
              FROM vrs_objects
             WHERE vrs_object:type = :type 
               AND vrs_object:location IN (
                SELECT vrs_id FROM vrs_objects
                 WHERE vrs_object:start::INTEGER >= :start
                   AND vrs_object:end::INTEGER <= :end
                   AND vrs_object:sequenceReference:refgetAccession = :refgetAccession)
            """,
            { "type": "Allele", "start": 123456, "end": 123457, "refgetAccession": "MySQAccId"}, [("{\"id\": 1}",), ("{\"id\": 2}",)])
    )
    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    vars = sf.search_variations("MySQAccId", 123456, 123457)
    sf.close()
    assert len(vars) == 2
    assert "id" in vars[0] and vars[0]["id"] == 1
    assert "id" in vars[1] and vars[1]["id"] == 2
    assert mock_eng.were_all_execd()