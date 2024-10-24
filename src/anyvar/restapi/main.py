"""Provide core route definitions for REST service."""

import logging
import logging.config
import os
import pathlib
import tempfile
from contextlib import asynccontextmanager
from http import HTTPStatus

import ga4gh.vrs
import yaml
from fastapi import Body, FastAPI, File, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar
from anyvar.extras.vcf import VcfRegistrar
from anyvar.restapi.schema import (
    AnyVarStatsResponse,
    EndpointTag,
    GetSequenceLocationResponse,
    GetVariationResponse,
    InfoResponse,
    RegisterVariationRequest,
    RegisterVariationResponse,
    RegisterVrsVariationResponse,
    SearchResponse,
    VariationStatisticType,
)
from anyvar.translate.translate import (
    TranslationError,
    TranslatorConnectionError,
)
from anyvar.utils.types import VrsVariation, variation_class_map

logging_config_file = os.environ.get("ANYVAR_LOGGING_CONFIG", None)
if logging_config_file and pathlib.Path(logging_config_file).is_file():
    with pathlib.Path(logging_config_file).open() as fd:
        try:
            config = yaml.safe_load(fd.read())
            logging.config.dictConfig(config)
        except Exception:
            logging.exception("Error in Logging Configuration. Using default configs")

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
) -> FileResponse | dict:
    """Register alleles from a VCF and return a file annotated with VRS IDs.

    :param request: FastAPI request object
    :param vcf: incoming VCF file object
    :param for_ref: whether to compute VRS IDs for REF alleles
    :param allow_async_write: whether to allow async database writes
    :param assembly: the reference assembly for the VCF
    :return: streamed annotated file
    """
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(await vcf.read())
        temp_file.close()

        av: AnyVar = request.app.state.anyvar
        registrar = VcfRegistrar(av)
        with tempfile.NamedTemporaryFile(delete=False) as temp_out_file:
            try:
                registrar.annotate(
                    temp_file.name,
                    vcf_out=temp_out_file.name,
                    compute_for_ref=for_ref,
                    assembly=assembly,
                )
            except (TranslatorConnectionError, OSError) as e:
                _logger.error("Encountered error during VCF registration: %s", e)
                return {"error": "VCF registration failed."}
            except ValueError as e:
                _logger.error("Encountered error during VCF registration: %s", e)
                return {"error": "Encountered ValueError when registering VCF"}
            if not allow_async_write:
                _logger.info("Waiting for object store writes from API handler method")
                av.object_store.wait_for_writes()
            return FileResponse(temp_out_file.name)


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
