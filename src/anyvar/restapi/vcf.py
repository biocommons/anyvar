"""Define routes for VCF annotation and ingestion."""

import asyncio
import datetime
import logging
import os
import pathlib
import tempfile
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

import anyvar
from anyvar.anyvar import AnyVar
from anyvar.extras.vcf import (
    RequiredAnnotationsError,
    VcfRegistrar,
    register_existing_annotations,
)
from anyvar.restapi.schema import EndpointTag, ErrorResponse, RunStatusResponse
from anyvar.translate.translate import TranslatorConnectionError

try:
    import aiofiles  # noqa: I001
    from anyvar.queueing import celery_worker
    from billiard.exceptions import TimeLimitExceeded
    from celery.exceptions import WorkerLostError
    from celery.result import AsyncResult
except ImportError:
    aiofiles = None
    celery_worker = None
    TimeLimitExceeded = None
    WorkerLostError = None
    AsyncResult = None

_logger = logging.getLogger(__name__)

router = APIRouter()

# high side estimate for time is 500 variants per second
_expected_vrs_ids_per_second = int(
    os.getenv("ANYVAR_EXPECTED_VRS_IDS_PER_SECOND", "500")
)


async def _annotate_vcf_async(
    response: Response,
    vcf: UploadFile,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    add_vrs_attributes: bool,
    run_id: str | None,
) -> RunStatusResponse | ErrorResponse:
    """Annotate with VRS IDs asynchronously.  See `annotate_vcf()` for parameter definitions."""
    # if run_id is provided, validate it does not already exist
    if (
        not anyvar.anyvar.has_queueing_enabled()
        or not AsyncResult
        or not aiofiles
        or not celery_worker
    ):
        _logger.warning(
            "Async VCF annotation requested but not enabled (has_queueing_enabled=%s, AsyncResult=%s, aiofiles=%s, celery_worker=%s)",
            anyvar.anyvar.has_queueing_enabled(),
            AsyncResult,
            aiofiles,
            celery_worker,
            stack_info=True,
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF annotation are missing"
        )

    if run_id:
        existing_result = AsyncResult(id=run_id)
        if existing_result.status != "PENDING":
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ErrorResponse(
                error=f"An existing run with id {run_id} is {existing_result.status}. Fetch the completed run result before submitting with the same run_id."
            )

    # write file to shared storage area with a directory for each day and a random file name
    async_work_dir = os.environ.get("ANYVAR_VCF_ASYNC_WORK_DIR", None)
    utc_now = datetime.datetime.now(tz=datetime.UTC)
    file_id = str(uuid.uuid4())
    input_file_path = pathlib.Path(
        f"{async_work_dir}/{utc_now.year}{utc_now.month}{utc_now.day}/{file_id}"
    )
    if not input_file_path.parent.exists():
        input_file_path.parent.mkdir(parents=True)
    _logger.debug(
        "writing working file for async run %s vcf to %s", run_id, input_file_path
    )

    vcf_site_count = 0
    newline_bytes = b"\n"
    async with aiofiles.open(input_file_path, mode="wb") as fd:
        while buffer := await vcf.read(1024 * 1024):
            vcf_site_count += buffer.count(newline_bytes)
            await fd.write(buffer)
    _logger.debug(
        "wrote working file for async run %s vcf to %s", run_id, input_file_path
    )
    _logger.debug("vcf site count of async run %s vcf is %s", run_id, vcf_site_count)

    # submit async job
    task_result = celery_worker.annotate_vcf.apply_async(
        kwargs={
            "input_file_path": str(input_file_path),
            "assembly": assembly,
            "for_ref": for_ref,
            "allow_async_write": allow_async_write,
            "add_vrs_attributes": add_vrs_attributes,
        },
        task_id=run_id,
    )
    _logger.info(
        "%s - async annotation run submitted for vcf with %s sites",
        task_result.id,
        vcf_site_count,
    )

    # set response headers
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = f"/vcf/{task_result.id}"
    retry_after = max(
        1,
        round(
            (vcf_site_count * (2 if for_ref else 1)) / _expected_vrs_ids_per_second, 0
        ),
    )
    _logger.debug("%s - retry after is %s", task_result.id, str(retry_after))
    response.headers["Retry-After"] = str(int(retry_after))
    return RunStatusResponse(
        run_id=task_result.id,
        status="PENDING",
        status_message=f"Run submitted. Check status at /vcf/{task_result.id}",
    )


async def _annotate_vcf_sync(
    request: Request,
    response: Response,
    bg_tasks: BackgroundTasks,
    vcf: UploadFile,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    add_vrs_attributes: bool,
) -> FileResponse | ErrorResponse:
    """Annotate with VRS IDs synchronously.  See `annotate_vcf()` for parameter definitions."""
    av: AnyVar = request.app.state.anyvar
    registrar = VcfRegistrar(data_proxy=av.translator.dp, av=av)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as temp_in:
        contents = await vcf.read()
        temp_in.write(contents)
        temp_in_path = pathlib.Path(temp_in.name)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as temp_out:
        temp_out_path = pathlib.Path(temp_out.name)

    try:
        registrar.annotate(
            input_vcf_path=temp_in_path,
            output_vcf_path=temp_out_path,
            compute_for_ref=for_ref,
            assembly=assembly,
            vrs_attributes=add_vrs_attributes,
        )
    except (TranslatorConnectionError, OSError, ValueError):
        _logger.exception(
            "Encountered error during registration of VCF file %s", vcf.filename
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(error="VCF registration failed.")

    if not allow_async_write:
        _logger.info("Waiting for object store writes from API handler method")
        av.object_store.wait_for_writes()

    bg_tasks.add_task(_working_file_cleanup, temp_in_path)
    bg_tasks.add_task(_working_file_cleanup, temp_out_path)

    return FileResponse(temp_out_path)


@router.put(
    "/vcf",
    summary="Register alleles from a VCF",
    description="Provide a valid VCF. All reference and alternate alleles will be registered with AnyVar. The file is annotated with VRS IDs and returned.",
    tags=[EndpointTag.VCF],
    response_model=None,
)
async def annotate_vcf(
    request: Request,
    response: Response,
    bg_tasks: BackgroundTasks,
    vcf: Annotated[UploadFile, File(..., description="VCF to register and annotate")],
    for_ref: Annotated[
        bool,
        Query(description="Whether to compute VRS IDs for REF alleles"),
    ] = True,
    allow_async_write: Annotated[
        bool,
        Query(
            description="Whether to allow asynchronous write of VRS objects to database",
        ),
    ] = False,
    assembly: Annotated[
        str,
        Query(
            pattern="^(GRCh38|GRCh37)$",
            description="The reference assembly for the VCF",
        ),
    ] = "GRCh38",
    add_vrs_attributes: Annotated[
        bool,
        Query(
            description="Whether to annotate with VRS attributes (start, stop, state, length, repeat subunit length) or just IDs"
        ),
    ] = False,
    run_async: Annotated[
        bool,
        Query(
            description="If true, immediately return a '202 Accepted' response and run asynchronously",
        ),
    ] = False,
    run_id: Annotated[
        str | None,
        Query(
            description="When running asynchronously, use the specified value as the run id instead generating a random uuid",
        ),
    ] = None,
) -> FileResponse | RunStatusResponse | ErrorResponse:
    """Register alleles from a VCF and return a file annotated with VRS IDs.

    :param request: FastAPI request object
    :param response: FastAPI response object
    :param bg_tasks: FastAPI background tasks object
    :param vcf: incoming VCF file object
    :param for_ref: whether to compute VRS IDs for REF alleles
    :param allow_async_write: whether to allow async database writes
    :param assembly: the reference assembly for the VCF
    :param add_vrs_attributes: Whether to annotate with VRS attributes (start, stop,
        state, length, repeat subunit length) or just IDs
    :param run_async: whether to run the VCF annotation synchronously or asynchronously
    :param run_id: user provided id for asynchronous VCF annotation
    :return: streamed annotated file or a run status response for an asynchronous run
    """
    # If async requested but not enabled, return an error
    if run_async and not anyvar.anyvar.has_queueing_enabled():
        _logger.warning(
            "Async VCF annotation requested but not enabled (run_async=%s, has_queueing_enabled=%s)",
            run_async,
            anyvar.anyvar.has_queueing_enabled(),
            stack_info=True,
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF annotation are missing"
        )

    # ensure the temporary file is flushed to disk
    vcf.file.rollover()

    try:
        # Submit asynchronous run
        if run_async:
            return await _annotate_vcf_async(
                response=response,
                vcf=vcf,
                for_ref=for_ref,
                allow_async_write=allow_async_write,
                assembly=assembly,
                add_vrs_attributes=add_vrs_attributes,
                run_id=run_id,
            )
        # Run synchronously
        else:  # noqa: RET505
            return await _annotate_vcf_sync(
                request=request,
                response=response,
                bg_tasks=bg_tasks,
                vcf=vcf,
                for_ref=for_ref,
                allow_async_write=allow_async_write,
                assembly=assembly,
                add_vrs_attributes=add_vrs_attributes,
            )
    except Exception:
        _logger.exception("Unhandled error encountered error during VCF registration")
        raise


def _working_file_cleanup(file_path: str, missing_ok: bool = False) -> None:
    """Cleanup working files after successful completion of async task.

    :param input_file_path: path to VCF file
    """
    try:
        _logger.debug("removing working file %s", file_path)
        pathlib.Path(file_path).unlink(missing_ok=missing_ok)
    except Exception as e:  # noqa: BLE001
        _logger.warning("unable to remove working file %s: %s", file_path, str(e))


async def _ingest_annotated_vcf_sync(
    request: Request,
    bg_tasks: BackgroundTasks,
    vcf: UploadFile,
    assembly: str,
    allow_async_write: bool,
    require_validation: bool,
) -> FileResponse | ErrorResponse | None:
    """Ingest annotated VCF synchronously.  See `annotated_vcf()` for parameter definitions."""
    av: AnyVar = request.app.state.anyvar

    with tempfile.NamedTemporaryFile(delete=False, suffix=".vcf") as temp_in:
        contents = await vcf.read()
        temp_in.write(contents)
        temp_in_path = pathlib.Path(temp_in.name)

    conflicts_file = register_existing_annotations(
        av, temp_in_path, assembly, require_validation
    )

    if not allow_async_write:
        _logger.info("Waiting for object store writes from API handler method")
        av.object_store.wait_for_writes()

    bg_tasks.add_task(_working_file_cleanup, temp_in_path)
    if conflicts_file:
        bg_tasks.add_task(_working_file_cleanup, conflicts_file)
        return FileResponse(conflicts_file)
    return None


async def _ingest_annotated_vcf_async(
    response: Response,
    vcf: UploadFile,
    assembly: str,
    allow_async_write: bool,
    require_validation: bool,
    run_id: str | None,
) -> RunStatusResponse | ErrorResponse:
    """Ingest annotated VCF asynchronously.  See `annotated_vcf()` for parameter definitions."""
    if not anyvar.anyvar.has_queueing_enabled() or not aiofiles:
        _logger.warning(
            "Async VCF annotation requested but not enabled (has_queueing_enabled=%s, aiofiles=%s)",
            anyvar.anyvar.has_queueing_enabled(),
            aiofiles,
            stack_info=True,
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF annotation are missing"
        )

    # if run_id is provided, validate it does not already exist
    if run_id:
        existing_result = AsyncResult(id=run_id)
        existing_result_status = existing_result.status

        # explicitly delete to limit chances of deadlocks in the Redis client
        del existing_result

        if existing_result_status != "PENDING":
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ErrorResponse(
                error=f"An existing run with id {run_id} is {existing_result_status}.  Fetch the completed run result before submitting with the same run_id."
            )

    async_work_dir = os.environ.get("ANYVAR_VCF_ASYNC_WORK_DIR", None)
    utc_now = datetime.datetime.now(tz=datetime.UTC)
    file_id = str(uuid.uuid4())
    input_file_path = pathlib.Path(
        f"{async_work_dir}/{utc_now.year}{utc_now.month}{utc_now.day}/{file_id}"
    )
    if not input_file_path.parent.exists():
        input_file_path.parent.mkdir(parents=True)
    _logger.debug("writing working file for async vcf to %s", input_file_path)

    vcf_site_count = 0
    async with aiofiles.open(input_file_path, mode="wb") as fd:
        while buffer := await vcf.read(1024 * 1024):
            vcf_site_count += buffer.count(b"\n")
            await fd.write(buffer)
    _logger.debug("wrote working file for async vcf to %s", input_file_path)
    _logger.debug("vcf site count of async vcf is %s", vcf_site_count)

    task_result = celery_worker.ingest_annotated_vcf.apply_async(
        kwargs={
            "input_file_path": str(input_file_path),
            "assembly": assembly,
            "allow_async_write": allow_async_write,
            "require_validation": require_validation,
        },
        task_id=run_id,
    )
    _logger.info(
        "%s - async annotation run submitted for vcf with %s sites",
        task_result.id,
        vcf_site_count,
    )

    # set response headers
    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = f"/vcf/{task_result.id}"
    # low side estimate for time is 333 variants per second
    retry_after = max(1, round((vcf_site_count * 2) / 333, 0))
    _logger.debug("%s - retry after is %s", task_result.id, str(retry_after))
    response.headers["Retry-After"] = str(retry_after)
    return RunStatusResponse(
        run_id=task_result.id,
        status="PENDING",
        status_message=f"Run submitted. Check status at /vcf/{task_result.id}",
    )


@router.put(
    "/annotated_vcf",
    summary="Register alleles from a VCF that has already been annotated with VRS objects.",
    description="Provide a VCF that already has VRS position and state annotations. Ingest the objects into AnyVar.",
    tags=[EndpointTag.VCF],
    response_model=None,
)
async def annotated_vcf(
    request: Request,
    response: Response,
    bg_tasks: BackgroundTasks,
    vcf: Annotated[
        UploadFile,
        File(
            ...,
            description="VCF that has already been annotated with VRS ID, start/stop, and state for all alleles",
        ),
    ],
    allow_async_write: Annotated[
        bool,
        Query(
            description="Whether to allow asynchronous write of VRS objects to database",
        ),
    ] = False,
    assembly: Annotated[
        str,
        Query(
            pattern="^(GRCh38|GRCh37)$",
            description="The reference assembly for the VCF",
        ),
    ] = "GRCh38",
    run_async: Annotated[
        bool,
        Query(
            description="If true, immediately return a '202 Accepted' response and run asynchronously",
        ),
    ] = False,
    require_validation: Annotated[
        bool,
        Query(
            description="If true, verify correctness of annotated ID and return CSV listing all validation failures"
        ),
    ] = False,
    run_id: Annotated[
        str | None,
        Query(
            description="When running asynchronously, use the specified value as the run id instead generating a random uuid",
        ),
    ] = None,
) -> FileResponse | RunStatusResponse | ErrorResponse | None:
    """Register alleles from a VCF and return a file annotated with VRS IDs.

    :param request: FastAPI request object
    :param response: FastAPI response object
    :param bg_tasks: FastAPI background tasks object
    :param vcf: incoming VCF file object
    :param allow_async_write: whether to allow async database writes
    :param assembly: the reference assembly for the VCF
    :param run_async: whether to run the VCF annotation synchronously or asynchronously
    :param require_validation:
    :param run_id: user provided id for asynchronous VCF annotation
    :return: streamed annotated file or a run status response for an asynchronous run
    """
    # If async requested but not enabled, return an error
    if (run_async and not anyvar.anyvar.has_queueing_enabled()) or not AsyncResult:
        _logger.warning(
            "Async VCF annotation requested but not enabled (run_async=%s, has_queueing_enabled=%s)",
            run_async,
            anyvar.anyvar.has_queueing_enabled(),
            stack_info=True,
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF ingest are missing"
        )

    # ensure the temporary file is flushed to disk
    vcf.file.rollover()

    if run_async:
        if run_id:
            existing_result = AsyncResult(id=run_id)
            if existing_result.status != "PENDING":
                response.status_code = status.HTTP_400_BAD_REQUEST
                return ErrorResponse(
                    error=f"An existing run with id {run_id} is {existing_result.status}.  Fetch the completed run result before submitting with the same run_id."
                )
        return await _ingest_annotated_vcf_async(
            response=response,
            vcf=vcf,
            allow_async_write=allow_async_write,
            assembly=assembly,
            require_validation=require_validation,
            run_id=run_id,
        )
    try:
        return await _ingest_annotated_vcf_sync(
            request=request,
            bg_tasks=bg_tasks,
            vcf=vcf,
            assembly=assembly,
            allow_async_write=allow_async_write,
            require_validation=require_validation,
        )
    except RequiredAnnotationsError:
        _logger.exception("%s lacks required VRS annotations", vcf.filename)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required VRS annotations are missing -- ensure INFO field has VRS_Allele_IDs, VRS_Starts, VRS_Ends, and VRS_States"
        )
    except (TranslatorConnectionError, OSError, ValueError):
        _logger.exception(
            "Encountered error during registration of VCF file %s", vcf.filename
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(error="VCF ingestion failed.")


@router.get(
    "/vcf/{run_id}",
    summary="Poll for status and/or result for asynchronous VCF ingestion",
    description="Provide a valid run id to get the status and/or result of a VCF ingestion run",
    tags=[EndpointTag.VCF],
    response_model=None,
)
async def get_vcf_run_status(
    response: Response,
    bg_tasks: BackgroundTasks,
    run_id: Annotated[
        str, Path(description="The run id to retrieve the result or status for")
    ],
) -> RunStatusResponse | FileResponse | ErrorResponse:
    """Return the status or result of an asynchronous registration of alleles from a VCF file.

    :param response: FastAPI response object
    :param bg_tasks: FastAPI background tasks object
    :param run_id: asynchronous run id
    :return: streamed annotated file or a run status response
    """
    # Asynchronous VCF annotation not enabled, return error
    if (
        not anyvar.anyvar.has_queueing_enabled()
        or not AsyncResult
        or not TimeLimitExceeded
        or not WorkerLostError
    ):
        _logger.warning(
            "Async VCF annotation requested but not enabled (has_queueing_enabled=%s, AsyncResult=%s, TimeLimitExceeded=%s, WorkerLostError=%s)",
            anyvar.anyvar.has_queueing_enabled(),
            AsyncResult,
            TimeLimitExceeded,
            WorkerLostError,
            stack_info=True,
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF annotation are missing"
        )

    # get the async result
    async_result = AsyncResult(id=run_id)
    _logger.debug("%s - status is %s", run_id, async_result.status)

    # completed successfully
    if async_result.status == "SUCCESS":
        response.status_code = status.HTTP_200_OK
        output_file_path = async_result.result
        async_result.forget()
        if output_file_path:
            _logger.debug("%s - output file path is %s", run_id, output_file_path)
            bg_tasks.add_task(_working_file_cleanup, output_file_path)
            return FileResponse(path=output_file_path)
        # for tasks that don't need to return a file, just send a success notification
        return RunStatusResponse(
            run_id=run_id,
            status="SUCCESS",
            status_message="VCF registration complete",
        )

    # failed - return an error response
    elif (  # noqa: RET505
        async_result.status == "FAILURE"
        and async_result.result
        and isinstance(async_result.result, Exception)
    ):
        # get error message and code
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

        # cleanup working files
        if async_result.kwargs:
            input_file_path_str = async_result.kwargs.get("input_file_path", None)
            if input_file_path_str:
                input_file_path = pathlib.Path(input_file_path_str)
                if input_file_path.is_file():
                    _logger.debug(
                        "%s - adding task to remove input file %s",
                        run_id,
                        str(input_file_path),
                    )
                    bg_tasks.add_task(
                        _working_file_cleanup, str(input_file_path), missing_ok=True
                    )
                output_file_path = pathlib.Path(f"{input_file_path_str}_outputvcf")
                if output_file_path.is_file():
                    _logger.debug(
                        "%s - adding task to remove output file %s",
                        run_id,
                        str(output_file_path),
                    )
                    bg_tasks.add_task(
                        _working_file_cleanup, str(output_file_path), missing_ok=True
                    )

        # forget the run and return the response
        async_result.forget()
        response.status_code = int(
            os.environ.get("ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE", "500")
        )
        return ErrorResponse(error_code=error_code, error=error_msg)

    # status here is either "SENT" or "PENDING"
    else:
        # the after_task_publish handler sets the state to "SENT"
        #  so a status of PENDING is actually unknown task
        # but there can be a race condition, so if status is pending
        #  pause half a second at a time up to 5 seconds
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

        # status is "PENDING" - unknown run id
        if async_result.status == "PENDING":
            response.status_code = status.HTTP_404_NOT_FOUND
            return RunStatusResponse(
                run_id=run_id,
                status="NOT_FOUND",
                status_message="Run not found",
            )
        # status is "SENT" - return 202
        #  with retry after 2 seconds
        else:  # noqa: RET505
            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["Retry-After"] = "2"
            return RunStatusResponse(
                run_id=run_id,
                status="PENDING",
                status_message=f"Run not completed. Check status at /vcf/{run_id}",
            )
