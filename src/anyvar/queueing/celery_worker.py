"""Define the Celery app and tasks for asynchronous request-response support"""

import datetime
import logging
import os
import threading
from pathlib import Path

import celery.signals
from celery import Celery, Task
from celery.result import AsyncResult

import anyvar
from anyvar.extras.vcf import VcfRegistrar

_logger = logging.getLogger(__name__)

# Configure the Celery app
celery_app = Celery("anyvar")
celery_app.conf.update(
    # general settings
    task_default_queue=os.environ.get("CELERY_TASK_DEFAULT_QUEUE", "anyvar_q"),
    event_queue_prefix=os.environ.get("CELERY_EVENT_QUEUE_PREFIX", "anyvar_ev"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["application/json"],
    result_backend=os.environ.get("CELERY_BACKEND_URL", None),
    result_backend_transport_options={"global_keyprefix": "anyvar_"},
    broker_url=os.environ.get("CELERY_BROKER_URL", None),
    timezone=os.environ.get("CELERY_TIMEZONE", "UTC"),
    result_expires=int(os.environ.get("CELERY_RESULT_EXPIRES", "7200")),
    # task settings
    task_ignore_result=False,
    task_acks_late=os.environ.get("CELERY_TASK_ACKS_LATE", "true").lower()
    in ["true", "yes", "1"],
    task_reject_on_worker_lost=os.environ.get(
        "CELERY_TASK_REJECT_ON_WORKER_LOST", "false"
    ).lower()
    in ["true", "yes", "1"],
    # worker settings
    worker_prefetch_multiplier=int(
        os.environ.get("CELERY_WORKER_PREFETCH_MULTIPLIER", 1)
    ),
    task_time_limit=int(os.environ.get("CELERY_TASK_TIME_LIMIT", "3900")),
    soft_time_limit=int(os.environ.get("CELERY_SOFT_TIME_LIMIT", "3600")),
    worker_send_task_events=os.environ.get(
        "CELERY_WORKER_SEND_TASK_EVENTS", "false"
    ).lower()
    in ["true", "yes", "1"],
)

# if this is a celery worker, we need an AnyVar app instance
#  and to track how many tasks are concurrently running
#  so that clean up can happen cleanly and at the right time
# For the prefork pool, this is not really needed since preforked
#   workers are single threaded; but for the threads pool, this
#   state is shared by the worker threads
_anyvar_app = None
_current_task_count = 0
_cleanup_flag = False
_shared_state_lock = threading.Lock()


def get_anyvar_app() -> anyvar.AnyVar:
    """Create AnyVar app associated with the Celery work as necessary and return it"""
    with _shared_state_lock:
        global _anyvar_app
        # create anyvar instance if necessary
        if not _anyvar_app:
            _logger.info("creating global anyvar app for worker")
            storage = anyvar.anyvar.create_storage()
            translator = anyvar.anyvar.create_translator()
            anyvar_instance = anyvar.AnyVar(object_store=storage, translator=translator)
            _anyvar_app = anyvar_instance

    return _anyvar_app


def maybe_teardown_anyvar_app() -> None:
    """Shutdown the AnyVar app if it is safe to do so"""
    global _anyvar_app
    global _shared_state_lock
    global _current_task_count
    global _cleanup_flag
    with _shared_state_lock:
        # if it is safe to do so
        if _cleanup_flag and _current_task_count == 0 and _anyvar_app:
            # cleanly shutdown the AnyVar app, waiting for background writes
            _logger.info("closing AnyVar app")
            _anyvar_app.object_store.wait_for_writes()
            _anyvar_app.object_store.close()
            _anyvar_app = None
            _cleanup_flag = False


def enter_task() -> None:
    """Increment the task counter"""
    global _shared_state_lock
    global _current_task_count
    _logger.info(
        "incrementing current task count from %s to %s",
        _current_task_count,
        _current_task_count + 1,
    )
    with _shared_state_lock:
        _current_task_count = _current_task_count + 1


def exit_task() -> None:
    """Decrement the task counter"""
    global _shared_state_lock
    global _current_task_count
    _logger.info(
        "decrementing current task count from %s to %s",
        _current_task_count,
        _current_task_count - 1,
    )
    with _shared_state_lock:
        _current_task_count = _current_task_count - 1


@celery.signals.worker_shutting_down.connect
def on_worker_shutting_down(**kwargs) -> None:  # noqa: ARG001
    """On the `worker_shutting_down` signal, set the cleanup flag and attempt tear down.
    This signal is dispatched in both the prefork and threads pool types on the main process.
    """
    _logger.info("processing signal worker_shutting_down")
    global _shared_state_lock
    global _cleanup_flag
    with _shared_state_lock:
        _cleanup_flag = True

    maybe_teardown_anyvar_app()


@celery.signals.worker_process_shutdown.connect
def on_worker_process_shutdown(**kwargs) -> None:  # noqa: ARG001
    """On the `worker_process_shutdown` signal, set the cleanup flag and attempt tear down.
    This signal is dispatched in the forked worker processes in the prefork pool.
    """
    _logger.info("processing signal worker_process_shutdown")
    global _shared_state_lock
    global _cleanup_flag
    with _shared_state_lock:
        _cleanup_flag = True

    maybe_teardown_anyvar_app()


@celery.signals.worker_shutdown.connect
def on_worker_shutdown(**kwargs) -> None:  # noqa: ARG001
    """On the `worker_shutdown` signal, set the cleanup flag and attempt tear down.
    This signal is dispatched in both the prefork and threads pool types on the main process.
    """
    _logger.info("processing signal worker_shutdown")
    global _shared_state_lock
    global _cleanup_flag
    with _shared_state_lock:
        _cleanup_flag = True

    maybe_teardown_anyvar_app()


@celery_app.task(bind=True)
def annotate_vcf(
    self: Task,
    input_file_path: str,
    assembly: str,
    for_ref: bool,
    allow_async_write: bool,
) -> str:
    """Annotate the specified VCF file and return the path to the annotated file.
    The input file is deleted when the annotation completes successfully.
    :param input_file_path: path to the VCF file to be annotated
    :param assembly: the reference assembly for the VCF
    :param for_ref: whether to compute VRS IDs for REF alleles
    :param allow_async_write: whether to allow async database writes
    :return: path to the annotated VCF file
    """
    try:
        enter_task()
        task_start = datetime.datetime.now(tz=datetime.UTC)

        # create output file path
        output_file_path = f"{input_file_path}_outputvcf"
        _logger.info(
            "%s - annotating vcf file %s, outputting to %s",
            self.request.id,
            input_file_path,
            output_file_path,
        )

        # annotate vcf with VRS IDs
        anyvar_app = get_anyvar_app()
        registrar = VcfRegistrar(anyvar_app)
        registrar.annotate(
            vcf_in=input_file_path,
            vcf_out=output_file_path,
            compute_for_ref=for_ref,
            assembly=assembly,
        )
        elapsed = datetime.datetime.now(tz=datetime.UTC) - task_start
        _logger.info(
            "%s - annotation completed in %s seconds", self.request.id, elapsed.seconds
        )

        # wait for writes if necessary
        if not allow_async_write:
            _logger.info(
                "%s - waiting for object store writes from celery worker method",
                self.request.id,
            )
            write_start = datetime.datetime.now(tz=datetime.UTC)
            anyvar_app.object_store.wait_for_writes()
            elapsed = datetime.datetime.now(tz=datetime.UTC) - write_start
            _logger.info(
                "%s - waited for object store writes for %s seconds",
                self.request.id,
                elapsed.seconds,
            )

        # remove input file
        Path(input_file_path).unlink()

        # return output file path
        return output_file_path
    except Exception:
        _logger.exception("%s - vcf annotation failed with exception", self.request.id)
        raise
    finally:
        exit_task()
        maybe_teardown_anyvar_app()


@celery.signals.after_task_publish.connect
def update_sent_state(sender: str | None, headers: dict | None, **kwargs) -> None:  # noqa: ARG001
    """On the `after_task_publish` signal, set the task status to SENT.  This enables
    the application to differentiate between task ids that are not complete and those
    that do not exist.
    :param sender: the name of the task
    :param headers: the task message headers
    """
    _logger.info("%s - after publish changing status to SENT", headers["id"])
    task = celery_app.tasks.get(sender)
    backend = task.backend if task else celery_app.backend

    result = AsyncResult(id=headers["id"])
    if result.status == "PENDING":
        backend.store_result(headers["id"], None, "SENT")
