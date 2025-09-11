import difflib
import json
import logging
import re
import time

logger = logging.getLogger(__name__)


class MockResult(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def fetchone(self) -> None:
        if len(self) > 0:
            retval = self[0]
            del self[0]
            return retval
        return None

    def fetchall(self):
        new_list = list(self)
        while len(self) > 0:
            del self[0]
        return new_list

    def scalar(self):
        if len(self) > 0:
            value = self[0][0]
            while len(self) > 0:
                del self[0]
            try:
                return int(value)
            except:  # noqa: E722
                return str(value) if value else None
        else:
            return None


class MockStmt:
    def __init__(self, sql: str, params, result, wait_for_secs: int = 0):
        self.sql = re.sub(r"\s+", " ", sql).strip()
        self.params = params
        self.result = (
            result
            if not result or isinstance(result, Exception)
            else MockResult(result)
        )
        self.wait_for_secs = wait_for_secs

    def matches(self, sql: str, params):
        norm_sql = re.sub(r"\s+", " ", sql).strip()
        if norm_sql == self.sql:
            if (
                self.params is True
                or (
                    (self.params is None or len(self.params) == 0)
                    and (params is None or len(params) == 0)
                )
                or self.params == params
            ):
                return True
            else:  # noqa: RET505
                # Log the mismatch for debugging
                logger.debug(
                    "Expected params: %s, Actual params: %s", self.params, params
                )
        else:
            # Log the mismatch for debugging
            diff = difflib.ndiff(self.sql.splitlines(), norm_sql.splitlines())
            logger.debug("SQL did not match MockStmt:\n%s", "\n".join(diff))
        return False


class MockStmtSequence(list):
    def __init__(self):
        self.execd = []

    def add_stmt(self, sql: str, params, result, wait_for_secs: int = 0):
        self.append(MockStmt(sql, params, result, wait_for_secs))
        return self

    def add_copy_from(self, table_name, data):
        self.append(MockStmt(f"COPY FROM fd INTO {table_name}", data, [(1,)]))
        return self

    def pop_if_matches(self, sql: str, params) -> list:
        if len(self) > 0 and self[0].matches(sql, params):
            self.execd.append(self[0])
            wait_for_secs = self[0].wait_for_secs
            result = self[0].result
            del self[0]
            if wait_for_secs > 0:
                time.sleep(wait_for_secs)
            if isinstance(result, Exception):
                raise result
            return result
        return None

    def were_all_execd(self):
        return len(self) <= 0


class MockConnection:
    def __init__(self):
        self.mock_stmt_sequences = []
        self.connection = self
        self.last_result = None

    def close(self):
        pass

    def cursor(self):
        return self

    def fetchall(self):
        return self.last_result.fetchall() if self.last_result else None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_value:
            raise exc_value
        return True

    def begin(self):
        return self

    def execute(self, cmd, params=None):
        for seq in self.mock_stmt_sequences:
            result = seq.pop_if_matches(str(cmd), params)
            if result:
                self.last_result = result
                return result

        norm_sql = re.sub(r"\s+", " ", str(cmd)).strip()
        msg = f"no mock statement found for {norm_sql} with params {params}"
        raise Exception(msg)

    def copy_from(self, fd, table_name, columns=None):
        data_as_str = str(fd.read())
        for seq in self.mock_stmt_sequences:
            result = seq.pop_if_matches(f"COPY FROM fd INTO {table_name}", data_as_str)
            if result:
                self.last_result = result
                return result

        msg = f"no mock statement found for COPY FROM fd INTO {table_name} with data {data_as_str[:10]}..."
        raise Exception(msg)


class MockEngine:
    def __init__(self):
        self.conn = MockConnection()

    def connect(self):
        return self.conn

    def dispose(self):
        pass

    def add_mock_stmt_sequence(self, stmt_seq: MockStmtSequence):
        self.conn.mock_stmt_sequences.append(stmt_seq)

    def were_all_execd(self):
        for seq in self.conn.mock_stmt_sequences:  # noqa: SIM110
            if not seq.were_all_execd():
                return False
        return True


class MockVRSObject:
    def __init__(self, id: str):
        self.id = id

    def model_dump(self, exclude_none: bool):
        return {"id": self.id}

    def to_json(self):
        return json.dumps(self.model_dump(exclude_none=True))
