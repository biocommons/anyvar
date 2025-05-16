import logging
import os
from datetime import datetime, timedelta

import pytest

from anyvar.storage.duckdb import DuckdbAnnotationObjectStore
from anyvar.utils.types import Annotation, AnnotationKey

logger = logging.getLogger(__name__)


@pytest.fixture
def db_uri():
    return os.environ.get("ANYVAR_TEST_DUCKDB_URI") or "duckdb:///anyvar-test.duckdb"


def test_add_one(db_uri):
    try:
        sqlstore = DuckdbAnnotationObjectStore(db_url=db_uri, table_name="annotations")
        sqlstore.wipe_db()

        keys = [
            AnnotationKey(object_id=str(i), annotation_type="created_time")
            for i in range(4)
        ]
        first_datetime = datetime.fromisoformat("2025-01-01T00:00:00Z")
        values = [
            {"timestamp": (first_datetime + timedelta(minutes=i)).isoformat()}
            for i in range(4)
        ]

        for key, value in zip(keys, values, strict=True):
            sqlstore[key] = value

        assert len(sqlstore) == len(keys)

        for key, value in zip(keys, values, strict=True):
            assert [a.annotation for a in sqlstore[key]] == [value]

    finally:
        if sqlstore is not None:
            sqlstore.close()


def test_one_to_many(db_uri):
    try:
        sqlstore = DuckdbAnnotationObjectStore(db_url=db_uri, table_name="annotations")
        sqlstore.wipe_db()
        assert len(sqlstore) == 0

        input_annotations = [
            # Two same id and type and value
            Annotation(
                object_id="1",
                annotation_type="created_time",
                annotation={"value": "VALUE0"},
            ),
            Annotation(
                object_id="1",
                annotation_type="created_time",
                annotation={"value": "VALUE0"},
            ),
            # Two same id, same type, different value
            Annotation(
                object_id="2",
                annotation_type="created_time",
                annotation={"value": "VALUE1"},
            ),
            Annotation(
                object_id="2",
                annotation_type="created_time",
                annotation={"value": "VALUE2"},
            ),
            # Same id, different type, different value
            Annotation(
                object_id="3",
                annotation_type="type3",
                annotation={"value": "VALUE1"},
            ),
            Annotation(
                object_id="3",
                annotation_type="type4",
                annotation={"value": "VALUE2"},
            ),
        ]

        for ann in input_annotations:
            sqlstore.push(ann)

        assert len(sqlstore) == len(input_annotations)

        # "1" "created_time" -> "VALUE0" (x2)
        results = sqlstore[input_annotations[0].key()]
        assert len(results) == 2
        assert results[0].annotation == {"value": "VALUE0"}
        assert results[1].annotation == {"value": "VALUE0"}

        # "2" "created_time" -> "VALUE1" "VALUE2"
        results = sqlstore[input_annotations[2].key()]
        assert len(results) == 2
        assert results[0].annotation == {"value": "VALUE1"}
        assert results[1].annotation == {"value": "VALUE2"}

        # "3" "type3" -> "VALUE1"
        # "3" "type4" -> "VALUE2"
        results = sqlstore[input_annotations[4].key()]
        assert len(results) == 1
        assert results[0].annotation == {"value": "VALUE1"}
        results = sqlstore[input_annotations[5].key()]
        assert len(results) == 1
        assert results[0].annotation == {"value": "VALUE2"}

        # check keys
        assert list(sqlstore.keys()) == [a.key() for a in input_annotations]

    finally:
        if sqlstore is not None:
            sqlstore.close()


def test_batch_insert(db_uri):
    sqlstore = None
    try:
        batch_limit = 10
        half_batch_limit = 5
        sqlstore = DuckdbAnnotationObjectStore(
            db_url=db_uri,
            table_name="annotations",
            batch_limit=batch_limit,
            max_pending_batches=1,
        )
        sqlstore.wipe_db()
        assert len(sqlstore) == 0

        with sqlstore.batch_manager(sqlstore):
            values = [
                Annotation(
                    object_id=str(i),
                    annotation_type="created_time",
                    annotation={"value": f"VALUE{i}"},
                )
                for i in range(batch_limit * 2)
            ]
            for value in values[:half_batch_limit]:
                sqlstore.push(value)

            # Not flushed yet so values should not be there
            assert len(sqlstore) == 0
            assert values[0].key() not in sqlstore
            assert len(sqlstore.batch_insert_values) == half_batch_limit

            # Push second half of batch
            for value in values[half_batch_limit:]:
                sqlstore.push(value)

            # Wait for flush
            assert sqlstore.num_pending_batches() > 0
            sqlstore.wait_for_writes()

            assert len(sqlstore) == len(values)

            # Values should be there now
            for value in values:
                assert value.key() in sqlstore
                assert sqlstore[value.key()][0].annotation == value.annotation

            # Add everything again, should have double the count
            for value in values:
                sqlstore.push(value)

            # Wait for flush
            if sqlstore.num_pending_batches() > 0:
                logger.info("Waiting for writes")
                sqlstore.wait_for_writes()

            assert len(sqlstore) == 2 * len(values)
    finally:
        if sqlstore is not None:
            sqlstore.close()


def test_batch_insert_backpressure(db_uri):
    """Test that the batch insert backpressure works as expected.
    Inserts batches of size 1, 1 at a time."""
    sqlstore = None
    try:
        insert_count = 10
        batch_limit = 1
        sqlstore = DuckdbAnnotationObjectStore(
            db_url=db_uri,
            table_name="annotations",
            batch_limit=batch_limit,
            max_pending_batches=1,
        )
        sqlstore.wipe_db()
        assert len(sqlstore) == 0
        with sqlstore.batch_manager(sqlstore):
            for i in range(insert_count):
                sqlstore.push(
                    Annotation(
                        object_id=str(i),
                        annotation_type="created_time",
                        annotation={"value": f"VALUE{i}"},
                    )
                )
            if sqlstore.num_pending_batches() > 0:
                sqlstore.wait_for_writes()
            assert len(sqlstore) == insert_count
    finally:
        if sqlstore is not None:
            sqlstore.close()


def test_batch_ctx_mgr(db_uri):
    sqlstore = None
    try:
        batch_limit = 100
        half_batch_limit = 50
        sqlstore = DuckdbAnnotationObjectStore(
            db_url=db_uri,
            table_name="annotations",
            batch_limit=batch_limit,
            max_pending_batches=0,
        )
        sqlstore.wipe_db()
        assert len(sqlstore) == 0

        with sqlstore.batch_manager(sqlstore):
            values = [
                Annotation(
                    object_id=str(i),
                    annotation_type="created_time",
                    annotation={"value": f"VALUE{i}"},
                )
                for i in range(batch_limit)
            ]
            for value in values[:half_batch_limit]:
                sqlstore.push(value)

            # Wrote fewer than batch limit, so nothing should be flushed
            assert len(sqlstore) == 0
            assert values[0].key() not in sqlstore

        # Context manager exited. Values should be there now
        assert len(sqlstore) == half_batch_limit
        for value in values[:half_batch_limit]:
            assert value.key() in sqlstore
            assert sqlstore[value.key()][0].annotation == value.annotation

    finally:
        if sqlstore is not None:
            sqlstore.close()
