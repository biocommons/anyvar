"""Provide core route definitions for REST service."""
import ga4gh.vrs
from fastapi import Body, FastAPI, HTTPException, Query, Request
from pydantic import StrictStr

import anyvar
from anyvar.anyvar import AnyVar, create_storage, create_translator
from anyvar.restapi.schema import (AnyVarStatsResponse, EndpointTag,
                                   GetSequenceLocationResponse,
                                   GetVariationResponse, InfoResponse,
                                   RegisterVariationRequest,
                                   RegisterVariationResponse, SearchResponse,
                                   VariationStatisticType)
from anyvar.translate.translate import TranslationException

app = FastAPI(
    version=anyvar.__version__,
    docs_url="/",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"tryItOutEnabled": True},
    description="Register and retrieve VRS value objects."
)

@app.on_event("startup")
async def startup():
    """Get FUSOR reference"""
    storage = create_storage()
    translator = create_translator()
    anyvar_instance = AnyVar(object_store=storage, translator=translator)
    app.state.anyvar = anyvar_instance


@app.get(
    "/info",
    response_model=InfoResponse,
    summary="Check system status and configurations",
    description="System status check and configurations",
    tags=[EndpointTag.GENERAL]
)
def get_info():
    """Get system status check and configuration"""
    return {
        "anyvar": {
            "version": anyvar.__version__,
            },
        "ga4gh_vrs": {
            "version": ga4gh.vrs.__version__
        },
    }


@app.get(
    "/locations/{location_id}",
    response_model=GetSequenceLocationResponse,
    summary="Retrieve sequence location",
    description="Retrieve registered sequence location by ID",
    tags=[EndpointTag.LOCATIONS]
)
def get_location_by_id(
    request: Request,
    location_id: StrictStr = Query(..., description="Location VRS ID")
):
    """Retrieve stored location object by ID.

    :param request: FastAPI request object
    :param location_id: VRS location identifier
    :return: complete location object if successful
    :raise HTTPException: if requested location isn't found
    """
    av: AnyVar = request.app.state.anyvar
    try:
        location = av.get_object(location_id)
    except KeyError:
        return HTTPException(status_code=404)
    return {"location": location.as_dict()}


@app.put(
    "/variation",
    response_model=RegisterVariationResponse,
    summary="Register a new variation object",
    description="Provide a variation definition to be normalized and registered with AnyVar. A complete VRS object and digest is returned for later reference.",  # noqa: E501
    tags=[EndpointTag.VARIATIONS]
)
def register_variation(
    request: Request,
    variation: RegisterVariationRequest = Body(
        description="Variation description, including (at minimum) a definition property"  # noqa: E501
    )
):
    """Register a variation based on a provided description or reference.

    :param request: FastAPI request object
    :param variation: provided variation description
    :return: messages describing translation failure, or object and references if
        successful
    """
    av: AnyVar = request.app.state.anyvar
    definition = variation.definition
    result = {
        "object": None,
        "messages": []
    }
    try:
        translated_variation = av.translator.translate(var=definition)
    except TranslationException:
        result["messages"].append(f"Unable to translate {definition}")
    except NotImplementedError:
        result["messages"].append(
            f"Variation class for {definition} is currently unsupported."
        )
    else:
        v_id = av.put_object(translated_variation)
        result["object"] = translated_variation.as_dict()
        result["object_id"] = v_id
    return result


@app.get(
    "/variation/{variation_id}",
    response_model=GetVariationResponse,
    operation_id="getVariation",
    summary="Retrieve a variation object",
    description="Gets a variation instance by ID. May return any supported type of variation.",  # noqa: E501
    tags=[EndpointTag.VARIATIONS]
)
def get_variation_by_id(
    request: Request,
    variation_id: StrictStr = Query(..., description="VRS ID for variation")
):
    """Get registered variation given VRS ID.

    :param request: FastAPI request object
    :param variation_id: ID to look up
    :return: VRS variation if successful
    :raise HTTPException: if no variation matches provided ID
    """
    av: AnyVar = request.app.state.anyvar

    try:
        variation = av.get_object(variation_id, deref=True)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Variation {variation_id} not found"
        )

    result = {"messages": [], "data": variation.as_dict()}

    return result


@app.get(
    "/search",
    response_model=SearchResponse,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Fetch all registered variations within the provided genomic coordinates",  # noqa: E501
    tags=[EndpointTag.SEARCH]
)
def search_variations(
    request: Request,
    accession: str = Query(..., description="Sequence accession identifier"),
    start: int = Query(..., description="Start position for genomic region"),
    end: int = Query(..., description="End position for genomic region")
):
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
    except KeyError:
        raise HTTPException(
            status_code=404, detail="Unable to dereference provided accession ID"
        )

    alleles = []
    if ga4gh_id:
        try:
            alleles = av.object_store.search_variations(ga4gh_id, start, end)
        except NotImplementedError:
            raise HTTPException(
                status_code=501,
                detail="Search not implemented for current storage backend"
            )

    inline_alleles = []
    for allele in alleles:
        inline_alleles.append(av.get_object(allele["_id"], deref=True).asdict())

    return {"variations": inline_alleles}


@app.get(
    "/stats/{variation_type}",
    response_model=AnyVarStatsResponse,
    operation_id="getStats",
    summary="Summary statistics for registered variations",
    description="Retrieve summary statistics for registered variation objects.",
    tags=[EndpointTag.GENERAL]
)
def get_stats(
    request: Request,
    variation_type: VariationStatisticType = Query(
        ..., description="category of variation"
    )
):
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
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Stats not available for current storage backend"
        )
    return {
        "variation_type": variation_type,
        "count": count
    }
