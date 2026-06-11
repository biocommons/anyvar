"""Provide REST API service."""


def _check_async_imports() -> bool:
    try:
        import aiofiles  # noqa: PLC0415
        from billiard.exceptions import TimeLimitExceeded  # noqa: PLC0415
        from celery.exceptions import WorkerLostError  # noqa: PLC0415
        from celery.result import AsyncResult  # noqa: PLC0415

        from anyvar.queueing import celery_worker  # noqa: PLC0415

        return True  # noqa: TRY300
    except ImportError:
        return False


has_async_imports = _check_async_imports()

__all__ = ["has_async_imports"]
