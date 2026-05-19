"""Shared helpers for asynchronous request-response endpoints."""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from fastapi import Response, status
from fastapi.responses import FileResponse, JSONResponse

from anyvar.restapi.schema import ErrorResponse, RunStatusResponse

_has_async_imports = True
try:
    from billiard.exceptions import TimeLimitExceeded
    from celery.exceptions import WorkerLostError
    from celery.result import AsyncResult
except ImportError:
    _has_async_imports = False

_logger = logging.getLogger(__name__)


def check_async_enabled(
    enabled: bool,
    response: Response,
    error_msg: str,
) -> ErrorResponse | None:
    """Return an ErrorResponse if async is not enabled, else None.

    :param enabled: whether the required queueing and imports are available
    :param response: FastAPI response object to set status code on
    :param error_msg: message to include in the error response
    :return: ErrorResponse if not enabled, None otherwise
    """
    if not enabled:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(error=error_msg)
    return None


def validate_run_id_available(run_id: str, response: Response) -> ErrorResponse | None:
    """Check that a given run_id is not already active in Celery.

    :param run_id: task ID to validate
    :param response: FastAPI response object to set status code on
    :return: ErrorResponse if run_id is already in use, None otherwise
    """
    if not _has_async_imports:
        return None
    existing_result = AsyncResult(id=run_id)
    existing_status = existing_result.status
    # explicitly delete to limit chances of deadlocks in the Redis client
    del existing_result
    if existing_status != "PENDING":
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error=f"An existing run with id {run_id} is {existing_status}. Fetch the completed run result before submitting with the same run_id."
        )
    return None


async def resolve_async_task_status(
    run_id: str,
    response: Response,
    *,
    on_success: Callable[
        [AsyncResult],
        FileResponse
        | RunStatusResponse
        | JSONResponse
        | Awaitable[FileResponse | RunStatusResponse | JSONResponse],
    ],
    on_failure_cleanup: Callable[[AsyncResult], None] | None = None,
    failure_status_env_var: str,
    status_path_prefix: str,
) -> RunStatusResponse | ErrorResponse | FileResponse | JSONResponse:
    """Resolve the status of an async Celery task and return the appropriate response.

    This encapsulates the shared state-machine logic:
      - SUCCESS: call on_success callback with the AsyncResult, forget, return result
      - FAILURE: extract error code, optionally run cleanup, forget, return ErrorResponse
      - PENDING: poll up to 5s; if still PENDING -> 404 NOT_FOUND; if SENT -> 202

    :param run_id: Celery task ID
    :param response: FastAPI Response object for setting status codes/headers
    :param on_success: callback receiving the AsyncResult, returns the endpoint's success response
    :param on_failure_cleanup: optional callback receiving the AsyncResult for cleanup before forget
    :param failure_status_env_var: env var name for overriding failure HTTP status code
    :param status_path_prefix: URL path prefix for status messages (e.g. "/vcf" or "/variations")
    :return: appropriate response object
    """
    async_result = AsyncResult(id=run_id)
    _logger.debug("%s - status is %s", run_id, async_result.status)

    # completed successfully
    if async_result.status == "SUCCESS":
        result = on_success(async_result)
        if asyncio.iscoroutine(result):
            result = await result
        async_result.forget()
        return result

    # failed
    if (
        async_result.status == "FAILURE"
        and async_result.result
        and isinstance(async_result.result, Exception)
    ):
        error_msg = str(async_result.result)
        error_code = (
            "TIME_LIMIT_EXCEEDED"
            if isinstance(async_result.result, TimeLimitExceeded)
            else (
                "WORKER_LOST_ERROR"
                if isinstance(async_result.result, WorkerLostError)
                else "RUN_FAILURE"
            )
        )
        _logger.debug("%s - failed with error %s", run_id, error_msg)

        if on_failure_cleanup:
            on_failure_cleanup(async_result)

        async_result.forget()
        response.status_code = int(os.environ.get(failure_status_env_var, "500"))
        return ErrorResponse(error_code=error_code, error=error_msg)

    # PENDING or SENT
    # The after_task_publish handler sets state to "SENT", so PENDING means unknown task.
    # But there can be a race condition, so poll up to 5 seconds.
    if async_result.status == "PENDING":
        for _ in range(10):
            await asyncio.sleep(0.5)
            _logger.debug(
                "%s - after 0.5 second wait, status is %s",
                run_id,
                async_result.status,
            )
            if async_result.status != "PENDING":
                break

    # still PENDING - unknown run id
    if async_result.status == "PENDING":
        response.status_code = status.HTTP_404_NOT_FOUND
        return RunStatusResponse(
            run_id=run_id,
            status="NOT_FOUND",
            status_message="Run not found",
        )

    # SENT or other active state - return 202
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Retry-After"] = "2"
    return RunStatusResponse(
        run_id=run_id,
        status="PENDING",
        status_message=f"Run not completed. Check status at {status_path_prefix}/{run_id}",
    )
