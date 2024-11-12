"""Define the Celery app and tasks for asynchronous request-response support"""

import logging
import os
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
    result_expires=int(os.environ.get("CELERY_RESULT_EXPIRES", "3600")),
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

# if this is a worker, create/destroy the AnyVar app instance
#  on startup and shutdown
anyvar_app = None


@celery.signals.worker_process_init.connect
def init_anyvar(**kwargs) -> None:  # noqa: ARG001
    """On the `worker_process_init` signal, construct the AnyVar app instance"""
    _logger.info("processing signal worker process init")
    global anyvar_app
    # create anyvar instance
    if not anyvar_app:
        _logger.info("creating anyvar app in worker process init")
        storage = anyvar.anyvar.create_storage()
        translator = anyvar.anyvar.create_translator()
        anyvar_instance = anyvar.AnyVar(object_store=storage, translator=translator)

        # associate anyvar with the app state
        anyvar_app = anyvar_instance


@celery.signals.worker_process_shutdown.connect
def teardown_anyvar(**kwargs) -> None:  # noqa: ARG001
    """On the `worker_process_shutdown` signal, destroy the AnyVar app instance"""
    _logger.info("processing signal worker process shutdown")
    global anyvar_app
    # close storage connector on shutdown
    if anyvar_app:
        _logger.info("closing anyvar app in worker process init")
        anyvar_app.object_store.close()
        anyvar_app = None


@celery_app.task(bind=True)
def annotate_vcf(
    self: Task,
    input_file_path: str,
    assembly: str,
    for_ref: bool,
    allow_async_write: bool,
) -> str:
    """Annotate the specified VCF file and return the path to the annotated file
    :param input_file_path: path to the VCF file to be annotated
    :param assembly: the reference assembly for the VCF
    :param for_ref: whether to compute VRS IDs for REF alleles
    :param allow_async_write: whether to allow async database writes
    :return: path to the annotated VCF file
    """
    global anyvar_app
    try:
        # create output file path
        output_file_path = f"{input_file_path}_outputvcf"
        _logger.info(
            "%s - worker annotating vcf %s to %s",
            self.request.id,
            input_file_path,
            output_file_path,
        )

        # annotation vcf with VRS IDs
        registrar = VcfRegistrar(anyvar_app)
        registrar.annotate(
            vcf_in=input_file_path,
            vcf_out=output_file_path,
            compute_for_ref=for_ref,
            assembly=assembly,
        )

        # wait for writes if necessary
        if not allow_async_write:
            _logger.info(
                "%s - waiting for object store writes from API handler method",
                self.request.id,
            )
            anyvar_app.object_store.wait_for_writes()

        # remove input file
        Path(input_file_path).unlink()

        # return output file path
        return output_file_path
    except Exception:
        _logger.exception("%s - vcf annotation failed with exception", self.request.id)
        raise


# after task is published, set the status to "SENT"
#  this allows the web api to determine when a run_id is not found
@celery.signals.after_task_publish.connect
def update_sent_state(sender: str | None, headers: dict | None, **kwargs) -> None:  # noqa: ARG001
    """On the `after_task_publish` signal, set the task status to SENT.  This enables
    the application to differentiate between task ids that are not complete and those
    that do not exist.
    """
    _logger.info("%s - after publish", headers["id"])
    task = celery_app.tasks.get(sender)
    backend = task.backend if task else celery_app.backend

    result = AsyncResult(id=headers["id"])
    if result.status == "PENDING":
        backend.store_result(headers["id"], None, "SENT")
