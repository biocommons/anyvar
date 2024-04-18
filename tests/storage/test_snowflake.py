"""
Test Snowflake storage async batch management and write feature

To run an integration test with a real Snowflake connection, run all
  the tests with the ANYVAR_TEST_STORAGE_URI env variable set to 
  a Snowflake URI
"""
import json
import logging
import re
import time

from anyvar.storage.snowflake import SnowflakeObjectStore

class MockStmt:
    def __init__(self, sql: str, params: list, result: list, wait_for_secs: int = 0):
        self.sql = re.sub(r'\s+', ' ', sql).strip()
        self.params = params
        self.result = result
        self.wait_for_secs = wait_for_secs

    def matches(self, sql: str, params: list):
        norm_sql = re.sub(r'\s+', ' ', sql).strip()
        if norm_sql == self.sql:
            if self.params == True:
                return True
            elif (self.params is None or len(self.params) == 0) and (params is None or len(params) == 0):
                return True
            elif self.params == params:
                return True
        return False

class MockStmtSequence(list):
    def __init__(self):
        self.execd = []

    def add_stmt(self, sql: str, params: list, result: list, wait_for_secs: int = 0):
        self.append(MockStmt(sql, params, result, wait_for_secs))
        return self

    def pop_if_matches(self, sql: str, params: list) -> list:
        if len(self) > 0 and self[0].matches(sql, params):
            self.execd.append(self[0])
            wait_for_secs = self[0].wait_for_secs
            result = self[0].result
            del self[0]
            if wait_for_secs > 0:
                time.sleep(wait_for_secs)
            if isinstance(result, Exception):
                raise result
            else:
                return result
        return None
    
    def were_all_execd(self):
        return len(self) <= 0

class MockConnectionCursor:
    def __init__(self):
        self.mock_stmt_sequences = []
        self.current_result = None
        self.closed = False

    def close(self):
        self.closed = True

    def cursor(self):
        if self.closed:
            raise Exception("connection is closed")
        return self
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_value:
            raise exc_value
        return True

    def execute(self, cmd: str, params: list = None):
        if self.closed:
            raise Exception("connection is closed")
        self.current_result = None
        for seq in self.mock_stmt_sequences:
            result = seq.pop_if_matches(cmd, params)
            if result:
                self.current_result = result
        if not self.current_result:
            raise Exception(f"no mock statement found for {cmd} with params {params}")

    def executemany(self, cmd: str, params: list = None):
        self.execute(cmd, params)

    def fetchone(self):
        if self.closed:
            raise Exception("connection is closed")
        return self.current_result[0] if self.current_result and len(self.current_result) > 0 else None
    
    def commit(self):
        self.execute("COMMIT;", None)

    def rollback(self):
        self.execute("ROLLBACK;", None)

    def add_mock_stmt_sequence(self, stmt_seq: MockStmtSequence):
        self.mock_stmt_sequences.append(stmt_seq)
    
    def were_all_execd(self):
        for seq in self.mock_stmt_sequences:
            if not seq.were_all_execd():
                return False
        return True

class MockVRSObject:
    def __init__(self, id: str):
        self.id = id

    def model_dump(self, exclude_none: bool):
        return { "id": self.id }
    
    def to_json(self):
        return json.dumps(self.model_dump(exclude_none=True))

def test_create_schema(caplog, mocker):
    caplog.set_level(logging.DEBUG)
    sf_conn = mocker.patch('snowflake.connector.connect')
    sf_conn.return_value = MockConnectionCursor()
    sf_conn.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects');", None, [(0,)])
        .add_stmt("CREATE TABLE vrs_objects ( vrs_id VARCHAR(500) PRIMARY KEY COLLATE 'utf8', vrs_object VARIANT );", None, [("Table created",)])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    sf.close()
    assert sf_conn.return_value.were_all_execd()


def test_schema_exists(mocker):
    sf_conn = mocker.patch('snowflake.connector.connect')
    sf_conn.return_value = MockConnectionCursor()
    sf_conn.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects');", None, [(1,)])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value")
    sf.close()
    assert sf_conn.return_value.were_all_execd()


def test_batch_mgmt_and_async_write_single_thread(mocker):
    tmp_statement = "CREATE TEMP TABLE IF NOT EXISTS tmp_vrs_objects (vrs_id VARCHAR(500) COLLATE 'utf8', vrs_object VARCHAR);"
    insert_statement = "INSERT INTO tmp_vrs_objects (vrs_id, vrs_object) VALUES (?, ?);"
    merge_statement = f"""
        MERGE INTO vrs_objects2 v USING tmp_vrs_objects s ON v.vrs_id = s.vrs_id 
        WHEN NOT MATCHED THEN INSERT (vrs_id, vrs_object) VALUES (s.vrs_id, PARSE_JSON(s.vrs_object));
        """
    drop_statement = "DROP TABLE tmp_vrs_objects;"

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

    mocker.patch('ga4gh.core.is_pydantic_instance', return_value=True)
    sf_conn = mocker.patch('snowflake.connector.connect')
    sf_conn.return_value = MockConnectionCursor()
    sf_conn.return_value.add_mock_stmt_sequence(MockStmtSequence()
        .add_stmt("SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog = CURRENT_DATABASE() AND table_schema = CURRENT_SCHEMA() AND UPPER(table_name) = UPPER('vrs_objects2');", None, [(1,)])
        # Batch 1
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[0:2]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        .add_stmt("COMMIT;", None, [("Committed", )])
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
        # Batch 2
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[2:4]), [(2,)], 4)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        .add_stmt("COMMIT;", None, [("Committed", )])
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
        # Batch 3
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[4:6]), [(2,)], 3)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        .add_stmt("COMMIT;", None, [("Committed", )])
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
        # Batch 4
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[6:8]), [(2,)], 5)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        .add_stmt("COMMIT;", None, [("Committed", )])
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
        # Batch 5
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[8:10]), [(2,)], 3)
        .add_stmt(merge_statement, None, Exception("query timeout"))
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
        # Batch 6
        .add_stmt(tmp_statement, None, [("Table created",)])
        .add_stmt(insert_statement, list((pair[0], pair[1].to_json()) for pair in vrs_id_object_pairs[10:11]), [(2,)], 2)
        .add_stmt(merge_statement, None, [(2,)])
        .add_stmt(drop_statement, None, [("Table dropped",)])
        .add_stmt("COMMIT;", None, [("Committed", )])
        .add_stmt("ROLLBACK;", None, [("Rolled back", )])
    )

    sf = SnowflakeObjectStore("snowflake://account/?param=value", 2, "vrs_objects2", 4)
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
    assert sf_conn.return_value.were_all_execd()