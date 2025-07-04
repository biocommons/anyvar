"""Provide core route definitions for REST service."""

import asyncio
import datetime
import json
import logging
import os
import pathlib
import tempfile
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated

import ga4gh.vrs
from dotenv import load_dotenv
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
from fastapi.responses import FileResponse, JSONResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyAnnotation, AnyVar
from anyvar.extras.vcf import VcfRegistrar
from anyvar.restapi.schema import (
    AddAnnotationRequest,
    AddAnnotationResponse,
    AnyVarStatsResponse,
    DependencyInfo,
    EndpointTag,
    ErrorResponse,
    GetAnnotationResponse,
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

load_dotenv()
_logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(param_app: FastAPI):  # noqa: ANN201
    """Initialize AnyVar instance and associate with FastAPI app on startup
    and teardown the AnyVar instance on shutdown
    """
    # initialize logs
    name = __name__.split(".")[0]
    logging.basicConfig(
        filename=f"{name}.log",
        format="[%(asctime)s] - %(name)s - %(levelname)s : %(message)s",
    )
    logging.getLogger(name).setLevel(logging.DEBUG)

    # create anyvar instance
    storage = anyvar.anyvar.create_storage()
    translator = anyvar.anyvar.create_translator()
    anyvar_instance = AnyVar(object_store=storage, translator=translator)

    # associate anyvar with the app state
    param_app.state.anyvar = anyvar_instance

    # create annotation instance if configured
    annotation_storage = None
    if "ANYVAR_ANNOTATION_STORAGE_URI" in os.environ:
        if "ANYVAR_ANNOTATION_TABLE_NAME" not in os.environ:
            raise ValueError(
                "ANYVAR_ANNOTATION_TABLE_NAME is required if ANYVAR_ANNOTATION_STORAGE_URI is set"
            )
        annotation_storage = anyvar.anyvar.create_annotation_storage(
            os.environ["ANYVAR_ANNOTATION_STORAGE_URI"],
            table_name=os.environ["ANYVAR_ANNOTATION_TABLE_NAME"],
        )
        anyannotation_instance = AnyAnnotation(annotation_storage)
        param_app.state.anyannotation = anyannotation_instance

    yield

    # close storage connector on shutdown
    storage.close()
    if annotation_storage:
        annotation_storage.close()


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
    summary="Check system status and configurations",
    description="System status check and configurations",
    tags=[EndpointTag.GENERAL],
)
def get_info() -> InfoResponse:
    """Get system status check and configuration"""
    return InfoResponse(
        anyvar=DependencyInfo(version=anyvar.__version__),
        ga4gh_vrs=DependencyInfo(version=ga4gh.vrs.__version__),
    )


@app.get(
    "/locations/{location_id}",
    response_model_exclude_none=True,
    summary="Retrieve sequence location",
    description="Retrieve registered sequence location by ID",
    tags=[EndpointTag.LOCATIONS],
)
def get_location_by_id(
    request: Request,
    location_id: Annotated[StrictStr, Path(..., description="Location VRS ID")],
) -> GetSequenceLocationResponse:
    """Retrieve stored location object by ID.

    :param request: FastAPI request object
    :param location_id: VRS location identifier
    :return: complete location object if successful
    :raise HTTPException: if requested location isn't found
    """
    av: AnyVar = request.app.state.anyvar
    try:
        location: ga4gh.vrs.models.SequenceLocation = av.get_object(location_id)  # type: ignore[reportAssignmentType]
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
        ) from e

    if location:
        return GetSequenceLocationResponse(location=location)
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail=f"Location {location_id} not found"
    )


@app.post(
    "/variation/{vrs_id}/annotations",
    response_model_exclude_none=True,
    summary="Add annotation to a variation",
    description="Provide an annotation to associate with a Variation object. The Variation must be registered with AnyVar before adding annotations.",
    tags=[EndpointTag.VARIATIONS],
)
def add_variation_annotation(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    annotation: Annotated[
        AddAnnotationRequest,
        Body(
            description="Annotation to associate with the variation",
        ),
    ],
) -> AddAnnotationResponse:
    """Store an annotation for a variation.

    :param request: FastAPI request object
    :param vrs_id: the VRS ID of the variation to annotate
    :param annotation: the annotation to store
    :return: the variation and annotations if stored
    :raise HTTPException: if requested location isn't found
    """
    messages: list[str] = []
    # Look up the variation from the AnyVar store
    av: AnyVar = request.app.state.anyvar
    try:
        variation = av.get_object(vrs_id)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=f"Variation {vrs_id} not found"
        ) from e

    # Add the annotation to the annotation store
    if hasattr(request.app.state, "anyannotation"):
        anyannotation: AnyAnnotation = request.app.state.anyannotation
        try:
            anyannotation.put_annotation(
                object_id=vrs_id,
                annotation_type=annotation.annotation_type,
                annotation=annotation.annotation,
            )
        except ValueError as e:
            _logger.exception(
                "Failed to add annotation `%s` on variation `%s`", annotation, vrs_id
            )
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"Failed to add annotation: {annotation}",
            ) from e

    return AddAnnotationResponse(
        messages=messages,
        object=variation,
        object_id=vrs_id,
        annotation_type=annotation.annotation_type,
        annotation=annotation.annotation,
    )


@app.get(
    "/variation/{vrs_id}/annotations/{annotation_type}",
    response_model_exclude_none=True,
    summary="Retrieve annotations for a variation",
    description="Retrieve annotations for a variation by VRS ID and annotation type",
    tags=[EndpointTag.VARIATIONS],
)
def get_variation_annotation(
    request: Request,
    vrs_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
    annotation_type: Annotated[StrictStr, Path(..., description="Annotation type")],
) -> GetAnnotationResponse:
    """Retrieve annotations for a variation.

    :param request: FastAPI request object
    :param vrs_id: VRS ID for variation
    :param annotation_type: type of annotation to retrieve
    :return: response object containing list of annotations for the variation
    """
    # Retrieve the annotation from the annotation store
    if hasattr(request.app.state, "anyannotation"):
        anyannotation: AnyAnnotation = request.app.state.anyannotation
        annotations = anyannotation.get_annotation(vrs_id, annotation_type)
    else:
        annotations = []

    return GetAnnotationResponse(annotations=annotations)


@app.middleware("http")
async def add_creation_timestamp_annotation(
    request: Request, call_next: Callable
) -> Response:
    """Add a creation timestamp annotation to a variation if it doesn't already exist."""
    # Do nothing on request. Pass downstream.
    response = await call_next(request)

    # Check if the request was for the "/variation" endpoint
    if request.url.path == "/variation":
        # With response, check if timestamp exists
        annotator: AnyAnnotation = getattr(request.app.state, "anyannotation", None)
        if annotator:
            response_chunks = [chunk async for chunk in response.body_iterator]
            response_body = b"".join(response_chunks)
            response_body = response_body.decode("utf-8")
            response_json: dict = json.loads(response_body)
            vrs_id = response_json.get("object", {}).get("id")
            annotations = annotator.get_annotation(vrs_id, "creation_timestamp")
            if not annotations:
                annotator.put_annotation(
                    object_id=vrs_id,
                    annotation_type="creation_timestamp",
                    annotation={
                        "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat()
                    },
                )
            # Create a new response object since we have exhausted the response body iterator
            return JSONResponse(
                content=response_json,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )

    return response


@app.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and digest is returned for later reference.",
    tags=[EndpointTag.VARIATIONS],
)
def register_variation(
    request: Request,
    variation: Annotated[
        RegisterVariationRequest,
        Body(
            description="Variation description, including (at minimum) a definition property. Can provide optional input_type if the expected output representation is known. If representing copy number, provide copies or copy_change.",
            examples=[
                {
                    "definition": "NC_000007.13:g.36561662_36561663del",
                    "input_type": "Allele",
                    "copies": 0,
                    "copy_change": "complete genomic loss",
                }
            ],
        ),
    ],
) -> RegisterVariationResponse:
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
    return RegisterVariationResponse(**result)


@app.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. A digest is returned for later reference.",
    response_model_exclude_none=True,
    tags=[EndpointTag.VARIATIONS],
)
def register_vrs_object(
    request: Request,
    variation: Annotated[
        VrsVariation,
        Body(
            description="Valid VRS object.",
            examples=[
                {
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
                }
            ],
        ),
    ],
) -> RegisterVrsVariationResponse:
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
    return RegisterVrsVariationResponse(**result)


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

    bg_tasks.add_task(os.unlink, temp_in_path)
    bg_tasks.add_task(os.unlink, temp_out_path)

    return FileResponse(temp_out_path)


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
    response_model_exclude_none=True,
    operation_id="getVariation",
    summary="Retrieve a variation object",
    description="Gets a variation instance by ID. May return any supported type of variation.",
    tags=[EndpointTag.VARIATIONS],
)
def get_variation_by_id(
    request: Request,
    variation_id: Annotated[StrictStr, Path(..., description="VRS ID for variation")],
) -> GetVariationResponse:
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

    if not variation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Variation {variation_id} not found",
        )
    return GetVariationResponse(messages=[], data=variation)


@app.get(
    "/search",
    response_model_exclude_none=True,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Fetch all registered variations within the provided genomic coordinates",
    tags=[EndpointTag.SEARCH],
)
def search_variations(
    request: Request,
    accession: Annotated[str, Query(..., description="Sequence accession identifier")],
    start: Annotated[int, Query(..., description="Start position for genomic region")],
    end: Annotated[int, Query(..., description="End position for genomic region")],
) -> SearchResponse:
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

    return SearchResponse(variations=inline_alleles)


@app.get(
    "/stats/{variation_type}",
    operation_id="getStats",
    summary="Summary statistics for registered variations",
    description="Retrieve summary statistics for registered variation objects.",
    tags=[EndpointTag.GENERAL],
)
def get_stats(
    request: Request,
    variation_type: Annotated[
        VariationStatisticType, Path(..., description="category of variation")
    ],
) -> AnyVarStatsResponse:
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
    return AnyVarStatsResponse(variation_type=variation_type, count=count)
