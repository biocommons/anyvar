"""Tests for anyvar.restapi.async_utils module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response, status
from fastapi.responses import JSONResponse

from anyvar.restapi.async_utils import (
    check_async_enabled,
    resolve_async_task_status,
    validate_run_id_available,
)
from anyvar.restapi.schema import ErrorResponse, RunStatusResponse

# ---------------------------------------------------------------------------
# Tests: check_async_enabled()
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestCheckAsyncEnabled:
    def test_disabled_returns_error(self):
        """When async is disabled, returns an ErrorResponse with 400 status."""
        response = Response()
        result = check_async_enabled(False, response, "Async not available")

        assert isinstance(result, ErrorResponse)
        assert result.error == "Async not available"
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_enabled_returns_none(self):
        """When async is enabled, returns None (no error)."""
        response = Response()
        result = check_async_enabled(True, response, "Async not available")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: validate_run_id_available()
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestValidateRunIdAvailable:
    @patch("anyvar.restapi.async_utils._has_async_imports", True)
    @patch("anyvar.restapi.async_utils.AsyncResult")
    def test_available_returns_none(self, mock_async_result_cls):
        """When run_id has PENDING status (not yet used), returns None."""
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_async_result_cls.return_value = mock_result

        response = Response()
        result = validate_run_id_available("test-run-id", response)

        assert result is None

    @patch("anyvar.restapi.async_utils._has_async_imports", True)
    @patch("anyvar.restapi.async_utils.AsyncResult")
    def test_in_use_returns_error(self, mock_async_result_cls):
        """When run_id is already active (non-PENDING), returns an ErrorResponse with 400 status."""
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_async_result_cls.return_value = mock_result

        response = Response()
        result = validate_run_id_available("test-run-id", response)

        assert isinstance(result, ErrorResponse)
        assert "test-run-id" in result.error
        assert "SUCCESS" in result.error
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("anyvar.restapi.async_utils._has_async_imports", False)
    def test_no_async_imports_returns_none(self):
        """When async imports are unavailable, validation is skipped and returns None."""
        response = Response()
        result = validate_run_id_available("test-run-id", response)

        assert result is None


# ---------------------------------------------------------------------------
# Tests: resolve_async_task_status()
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestResolveAsyncTaskStatus:
    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_success_calls_callback_and_forgets(self, mock_async_result_cls):
        """On SUCCESS status, calls on_success callback, forgets the result, and returns the callback's response."""
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.result = [{"object_id": "ga4gh:VA.123"}]
        mock_async_result_cls.return_value = mock_result

        def on_success(async_result):
            return JSONResponse(
                content=async_result.result, status_code=status.HTTP_200_OK
            )

        response = Response()
        result = await resolve_async_task_status(
            "run-123",
            response,
            on_success=on_success,
            failure_status_env_var="TEST_FAILURE_CODE",
            status_path_prefix="/variations",
        )

        assert isinstance(result, JSONResponse)
        mock_result.forget.assert_called_once()

    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_success_with_async_callback(self, mock_async_result_cls):
        """On SUCCESS status with an async on_success callback, awaits the callback and returns result."""
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.result = {"data": "test"}
        mock_async_result_cls.return_value = mock_result

        async def on_success(async_result):
            return JSONResponse(
                content=async_result.result, status_code=status.HTTP_200_OK
            )

        response = Response()
        result = await resolve_async_task_status(
            "run-123",
            response,
            on_success=on_success,
            failure_status_env_var="TEST_FAILURE_CODE",
            status_path_prefix="/variations",
        )

        assert isinstance(result, JSONResponse)
        mock_result.forget.assert_called_once()

    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_failure_returns_error(self, mock_async_result_cls):
        """On FAILURE status, returns ErrorResponse with RUN_FAILURE code and error details."""
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.result = Exception("Something went wrong")
        mock_async_result_cls.return_value = mock_result

        response = Response()
        result = await resolve_async_task_status(
            "run-123",
            response,
            on_success=MagicMock(),
            failure_status_env_var="TEST_FAILURE_CODE",
            status_path_prefix="/variations",
        )

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "RUN_FAILURE"
        assert "Something went wrong" in result.error
        mock_result.forget.assert_called_once()

    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_failure_with_cleanup(self, mock_async_result_cls):
        """On FAILURE status with a cleanup callback, invokes cleanup before forgetting the result."""
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.result = Exception("Failed")
        mock_async_result_cls.return_value = mock_result

        cleanup = MagicMock()

        response = Response()
        result = await resolve_async_task_status(
            "run-123",
            response,
            on_success=MagicMock(),
            on_failure_cleanup=cleanup,
            failure_status_env_var="TEST_FAILURE_CODE",
            status_path_prefix="/variations",
        )

        assert isinstance(result, ErrorResponse)
        cleanup.assert_called_once_with(mock_result)

    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_pending_unknown_returns_404(self, mock_async_result_cls):
        """When task stays PENDING after polling, returns 404 NOT_FOUND RunStatusResponse."""
        mock_result = MagicMock()
        # Stay PENDING through all polls
        type(mock_result).status = property(lambda self: "PENDING")  # noqa: ARG005
        mock_async_result_cls.return_value = mock_result

        async def noop_sleep(_seconds):
            pass

        response = Response()
        with patch("anyvar.restapi.async_utils.asyncio.sleep", side_effect=noop_sleep):
            result = await resolve_async_task_status(
                "unknown-run",
                response,
                on_success=MagicMock(),
                failure_status_env_var="TEST_FAILURE_CODE",
                status_path_prefix="/variations",
            )

        assert isinstance(result, RunStatusResponse)
        assert result.status == "NOT_FOUND"
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("anyvar.restapi.async_utils.AsyncResult")
    async def test_sent_returns_202(self, mock_async_result_cls):
        """When task has SENT status, returns 202 ACCEPTED with Retry-After header."""
        mock_result = MagicMock()
        mock_result.status = "SENT"
        mock_async_result_cls.return_value = mock_result

        response = Response()
        result = await resolve_async_task_status(
            "run-456",
            response,
            on_success=MagicMock(),
            failure_status_env_var="TEST_FAILURE_CODE",
            status_path_prefix="/variations",
        )

        assert isinstance(result, RunStatusResponse)
        assert result.status == "PENDING"
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.headers.get("Retry-After") == "2"
