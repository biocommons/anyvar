"""Provide core route definitions for REST service."""

import asyncio
import datetime
import logging
import logging.config
import os
import pathlib
import tempfile
import uuid
from contextlib import asynccontextmanager
from http import HTTPStatus

import ga4gh.vrs
from fastapi import (
    BackgroundTasks,
    Body,
    FastAPI,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar
from anyvar.extras.vcf import VcfRegistrar
from anyvar.restapi.schema import (
    AnyVarStatsResponse,
    EndpointTag,
    ErrorResponse,
    GetSequenceLocationResponse,
    GetVariationResponse,
    InfoResponse,
    RegisterVariationRequest,
    RegisterVariationResponse,
    RegisterVrsVariationResponse,
    RunStatusResponse,
    SearchResponse,
    VariationStatisticType,
)
from anyvar.translate.translate import (
    TranslationError,
    TranslatorConnectionError,
)
from anyvar.utils.types import VrsVariation, variation_class_map

try:
    import aiofiles  # noqa: I001
    import anyvar.queueing.celery_worker
    from billiard.exceptions import TimeLimitExceeded
    from celery.exceptions import WorkerLostError
    from celery.result import AsyncResult
except ImportError:
    pass

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(param_app: FastAPI):  # noqa: ANN201
    """Initialize AnyVar instance and associate with FastAPI app on startup
    and teardown the AnyVar instance on shutdown
    """
    # create anyvar instance
    storage = anyvar.anyvar.create_storage()
    translator = anyvar.anyvar.create_translator()
    anyvar_instance = AnyVar(object_store=storage, translator=translator)

    # associate anyvar with the app state
    param_app.state.anyvar = anyvar_instance

    yield

    # close storage connector on shutdown
    storage.close()


app = FastAPI(
    title="AnyVar",
    version=anyvar.__version__,
    docs_url="/",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"tryItOutEnabled": True},
    description="Register and retrieve VRS value objects.",
    lifespan=app_lifespan,
)


@app.get(
    "/info",
    response_model=InfoResponse,
    summary="Check system status and configurations",
    description="System status check and configurations",
    tags=[EndpointTag.GENERAL],
)
def get_info() -> dict:
    """Get system status check and configuration"""
    return {
        "anyvar": {
            "version": anyvar.__version__,
        },
        "ga4gh_vrs": {"version": ga4gh.vrs.__version__},
    }


@app.get(
    "/locations/{location_id}",
    response_model=GetSequenceLocationResponse,
    response_model_exclude_none=True,
    summary="Retrieve sequence location",
    description="Retrieve registered sequence location by ID",
    tags=[EndpointTag.LOCATIONS],
)
def get_location_by_id(
    request: Request, location_id: StrictStr = Path(..., description="Location VRS ID")
) -> dict:
    """Retrieve stored location object by ID.

    :param request: FastAPI request object
    :param location_id: VRS location identifier
    :return: complete location object if successful
    :raise HTTPException: if requested location isn't found
    """
    av: AnyVar = request.app.state.anyvar
    try:
        location = av.get_object(location_id)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
        ) from e

    if location:
        return {"location": location}
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
    )


@app.put(
    "/variation",
    response_model=RegisterVariationResponse,
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and digest is returned for later reference.",
    tags=[EndpointTag.VARIATIONS],
)
def register_variation(
    request: Request,
    variation: RegisterVariationRequest = Body(
        description="Variation description, including (at minimum) a definition property. Can provide optional input_type if the expected output representation is known. If representing copy number, provide copies or copy_change."
    ),
) -> dict:
    """Register a variation based on a provided description or reference.

    :param request: FastAPI request object
    :param variation: provided variation description
    :return: messages describing translation failure, or object and references if
        successful
    """
    av: AnyVar = request.app.state.anyvar
    definition = variation.definition
    result = {"object": None, "messages": [], "object_id": None}
    try:
        translated_variation = av.translator.translate_variation(
            definition, **variation.model_dump()
        )
    except TranslationError:
        result["messages"].append(f'Unable to translate "{definition}"')
    except NotImplementedError:
        result["messages"].append(
            f"Variation class for {definition} is currently unsupported."
        )
    else:
        if translated_variation:
            v_id = av.put_object(translated_variation)
            result["object"] = translated_variation
            result["object_id"] = v_id
        else:
            result["messages"].append(f"Translation of {definition} failed.")
    return result


@app.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. A digest is returned for later reference.",
    response_model=RegisterVrsVariationResponse,
    response_model_exclude_none=True,
    tags=[EndpointTag.VARIATIONS],
)
def register_vrs_object(
    request: Request,
    variation: VrsVariation = Body(
        description="Valid VRS object.",
        example={
            "location": {
                "id": "ga4gh:SL.aCMcqLGKClwMWEDx3QWe4XSiGDlKXdB8",
                "end": 87894077,
                "start": 87894076,
                "sequenceReference": {
                    "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
                    "type": "SequenceReference",
                },
                "type": "SequenceLocation",
            },
            "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
            "type": "Allele",
        },
    ),
) -> dict:
    """Register a complete VRS object. No additional normalization is performed.

    :param request: FastAPI request object
    :param variation: provided VRS variation object
    :return: object and references if successful
    """
    av: AnyVar = request.app.state.anyvar
    result = {
        "object": None,
        "messages": [],
    }
    variation_type = variation.type
    if variation_type not in variation_class_map:
        result["messages"].append(
            f"Registration for {variation_type} not currently supported."
        )
        return result

    variation_object = variation_class_map[variation_type](**variation.dict())
    v_id = av.put_object(variation_object)
    result["object"] = variation_object
    result["object_id"] = v_id
    return result


@app.put(
    "/vcf",
    summary="Register alleles from a VCF",
    description="Provide a valid VCF. All reference and alternate alleles will be registered with AnyVar. The file is annotated with VRS IDs and returned.",
    tags=[EndpointTag.VARIATIONS],
    response_model=None,
)
async def annotate_vcf(
    request: Request,
    response: Response,
    bg_tasks: BackgroundTasks,
    vcf: UploadFile = File(..., description="VCF to register and annotate"),
    for_ref: bool = Query(
        default=True, description="Whether to compute VRS IDs for REF alleles"
    ),
    allow_async_write: bool = Query(
        default=False,
        description="Whether to allow asynchronous write of VRS objects to database",
    ),
    assembly: str = Query(
        default="GRCh38",
        pattern="^(GRCh38|GRCh37)$",
        description="The reference assembly for the VCF",
    ),
    run_async: bool = Query(
        default=False,
        description="If true, immediately return a '202 Accepted' response and run asynchronously",
    ),
    run_id: str | None = Query(
        default=None,
        description="When running asynchronously, use the specified value as the run id instead generating a random uuid",
    ),
) -> FileResponse | RunStatusResponse | ErrorResponse:
    """Register alleles from a VCF and return a file annotated with VRS IDs.

    :param request: FastAPI request object
    :param response: FastAPI response object
    :param bg_tasks: FastAPI background tasks object
    :param vcf: incoming VCF file object
    :param for_ref: whether to compute VRS IDs for REF alleles
    :param allow_async_write: whether to allow async database writes
    :param assembly: the reference assembly for the VCF
    :param run_async: whether to run the VCF annotation synchronously or asynchronously
    :param run_id: user provided id for asynchronous VCF annotation
    :return: streamed annotated file or a run status response for an asynchronous run
    """
    # If async requested but not enabled, return an error
    if run_async and not anyvar.anyvar.has_queueing_enabled():
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ErrorResponse(
            error="Required modules and/or configurations for asynchronous VCF annotation are missing"
        )

    # ensure the temporary file is flushed to disk
    vcf.file.rollover()

    # Submit asynchronous run
    if run_async:
        return await _annotate_vcf_async(
            response=response,
            vcf=vcf,
            for_ref=for_ref,
            allow_async_write=allow_async_write,
            assembly=assembly,
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
        )


async def _annotate_vcf_async(
    response: Response,
    vcf: UploadFile,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    run_id: str | None,
) -> RunStatusResponse | ErrorResponse:
    """Annotate with VRS IDs asynchronously.  See `annotate_vcf()` for parameter definitions."""
    # if run_id is provided, validate it does not already exist
    if run_id:
        existing_result = AsyncResult(id=run_id)
        if existing_result.status != "PENDING":
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ErrorResponse(
                error=f"An existing run with id {run_id} is {existing_result.status}.  Fetch the completed run result before submitting with the same run_id."
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
    _logger.debug("writing working file for async vcf to %s", input_file_path)

    vcf_site_count = 0
    async with aiofiles.open(input_file_path, mode="wb") as fd:
        while buffer := await vcf.read(1024 * 1024):
            if ord("\n") in buffer:
                vcf_site_count = vcf_site_count + 1
            await fd.write(buffer)
    _logger.debug("wrote working file for async vcf to %s", input_file_path)
    _logger.debug("vcf site count of async vcf is %s", vcf_site_count)

    # submit async job
    task_result = anyvar.queueing.celery_worker.annotate_vcf.apply_async(
        kwargs={
            "input_file_path": str(input_file_path),
            "assembly": assembly,
            "for_ref": for_ref,
            "allow_async_write": allow_async_write,
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
    retry_after = max(1, round((vcf_site_count * (2 if for_ref else 1)) / 333, 0))
    _logger.debug("%s - retry after is %s", task_result.id, str(retry_after))
    response.headers["Retry-After"] = str(retry_after)
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
) -> FileResponse | ErrorResponse:
    """Annotate with VRS IDs synchronously.  See `annotate_vcf()` for parameter definitions."""
    av: AnyVar = request.app.state.anyvar
    registrar = VcfRegistrar(av)
    with tempfile.NamedTemporaryFile(delete=False) as temp_out_file:
        try:
            registrar.annotate(
                vcf.file.name,
                vcf_out=temp_out_file.name,
                compute_for_ref=for_ref,
                assembly=assembly,
            )
        except (TranslatorConnectionError, OSError) as e:
            _logger.error("Encountered error during VCF registration: %s", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ErrorResponse(error="VCF registration failed.")
        except ValueError as e:
            _logger.error("Encountered error during VCF registration: %s", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ErrorResponse(error="Encountered ValueError when registering VCF")

        if not allow_async_write:
            _logger.info("Waiting for object store writes from API handler method")
            av.object_store.wait_for_writes()
        bg_tasks.add_task(os.unlink, temp_out_file.name)
        return FileResponse(temp_out_file.name)


@app.get(
    "/vcf/{run_id}",
    summary="Poll for status and/or result for asynchronous VCF annotation",
    description="Provide a valid run id to get the status and/or result of a VCF annotation run",
    tags=[EndpointTag.VARIATIONS],
    response_model=None,
)
async def get_result(
    response: Response,
    bg_tasks: BackgroundTasks,
    run_id: str = Path(description="The run id to retrieve the result or status for"),
) -> RunStatusResponse | FileResponse | ErrorResponse:
    """Return the status or result of an asynchronous registration of alleles from a VCF file.
    :param response: FastAPI response object
    :param bg_tasks: FastAPI background tasks object
    :param run_id: asynchronous run id
    :return: streamed annotated file or a run status response
    """
    # Asynchronous VCF annotation not enabled, return error
    if not anyvar.anyvar.has_queueing_enabled():
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
        _logger.debug("%s - output file path is %s", run_id, output_file_path)
        bg_tasks.add_task(os.unlink, output_file_path)
        return FileResponse(path=output_file_path)

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
                    bg_tasks.add_task(input_file_path.unlink, missing_ok=True)
                output_file_path = pathlib.Path(f"{input_file_path_str}_outputvcf")
                if output_file_path.is_file():
                    _logger.debug(
                        "%s - adding task to remove output file %s",
                        run_id,
                        str(output_file_path),
                    )
                    bg_tasks.add_task(output_file_path.unlink, missing_ok=True)

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
        #  pause half a second and check again
        if async_result.status == "PENDING":
            await asyncio.sleep(0.5)
            async_result = AsyncResult(id=run_id)
            _logger.debug(
                "%s - after 0.5 second wait, status is %s", run_id, async_result.status
            )

        # status is "PENDING" - unknown run id
        if async_result.status == "PENDING":
            response.status_code = status.HTTP_404_NOT_FOUND
            return RunStatusResponse(
                run_id=run_id,
                status="NOT_FOUND",
                status_message="Run not found",
            )
        # status is "SENT" - return 202
        else:  # noqa: RET505
            response.status_code = status.HTTP_202_ACCEPTED
            return RunStatusResponse(
                run_id=run_id,
                status="PENDING",
                status_message=f"Run not completed. Check status at /vcf/{run_id}",
            )


@app.get(
    "/variation/{variation_id}",
    response_model=GetVariationResponse,
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a variation object",
    description="Gets a variation instance by ID. May return any supported type of variation.",
    tags=[EndpointTag.VARIATIONS],
)
def get_variation_by_id(
    request: Request,
    variation_id: StrictStr = Path(..., description="VRS ID for variation"),
) -> dict:
    """Get registered variation given VRS ID.

    :param request: FastAPI request object
    :param variation_id: ID to look up
    :return: VRS variation if successful
    :raise HTTPException: if no variation matches provided ID
    """
    av: AnyVar = request.app.state.anyvar
    try:
        variation = av.get_object(variation_id, deref=True)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Variation {variation_id} not found",
        ) from e

    if variation:
        return {"messages": [], "data": variation}
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND,
        detail=f"Variation {variation_id} not found",
    )


@app.get(
    "/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Fetch all registered variations within the provided genomic coordinates",
    tags=[EndpointTag.SEARCH],
)
def search_variations(
    request: Request,
    accession: str = Query(..., description="Sequence accession identifier"),
    start: int = Query(..., description="Start position for genomic region"),
    end: int = Query(..., description="End position for genomic region"),
) -> dict:
    """Fetch all registered variations within the provided genomic coordinates.

    :param request: FastAPI request object
    :param accession: sequence accession
    :param start: start position for genomic region
    :param end: end position for genomic region
    :return: list (possibly empty) of variations in the given region
    """
    av: AnyVar = request.app.state.anyvar
    try:
        ga4gh_id = av.translator.get_sequence_id(accession)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Unable to dereference provided accession ID",
        ) from e

    alleles = []
    if ga4gh_id:
        try:
            refget_accession = ga4gh_id.split("ga4gh:")[-1]
            alleles = av.object_store.search_variations(refget_accession, start, end)
        except NotImplementedError as e:
            raise HTTPException(
                status_code=HTTPStatus.NOT_IMPLEMENTED,
                detail="Search not implemented for current storage backend",
            ) from e

    inline_alleles = []
    if alleles:
        for allele in alleles:
            var_object = av.get_object(allele["id"], deref=True)
            if not var_object:
                continue
            inline_alleles.append(var_object)

    return {"variations": inline_alleles}


@app.get(
    "/stats/{variation_type}",
    response_model=AnyVarStatsResponse,
    operation_id="getStats",
    summary="Summary statistics for registered variations",
    description="Retrieve summary statistics for registered variation objects.",
    tags=[EndpointTag.GENERAL],
)
def get_stats(
    request: Request,
    variation_type: VariationStatisticType = Path(
        ..., description="category of variation"
    ),
) -> dict:
    """Get summary statistics for registered variants. Currently just returns totals.

    :param request: FastAPI request object
    :param variation_type: type of variation to summarize
    :return: total number of matching variants
    :raise HTTPException: if invalid variation type is requested, although FastAPI
        should block the request from going through in that case
    """
    av: AnyVar = request.app.state.anyvar
    try:
        count = av.object_store.get_variation_count(variation_type)
    except NotImplementedError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Stats not available for current storage backend",
        ) from e
    return {"variation_type": variation_type, "count": count}
