"""Provide API routes relating to search operations"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request
from ga4gh.vrs.dataproxy import DataProxyValidationError
from hgvs.exceptions import HGVSParseError

from anyvar.anyvar import AnyVar
from anyvar.core import objects
from anyvar.mapping import liftover
from anyvar.restapi.schema import (
    GetObjectResponse,
    RegisterVariationResponse,
    SearchResponse,
    TranslationResult,
    VariationRequest,
)
from anyvar.restapi.utils import get_vrs_object
from anyvar.storage.base import IncompleteVrsObjectError
from anyvar.translate.base import TranslationError, Translator

variations_router = APIRouter()

VARIATION_EXAMPLE_PAYLOAD = {
    "definition": "NC_000007.13:g.36561662_36561663del",
    "input_type": "Allele",
    "copies": 0,
    "copy_change": "complete genomic loss",
    "assembly_name": None,
}


_variation_request_body = Body(
    description='Variation description, including (at minimum) a `definition` property. Can provide optional `input_type` if the expected output representation type is known, as well as an assembly_name (e.g.,"GRCh37" or "GRCh38"). If representing copy number, provide `copies` or `copy_change`.',
    examples=[VARIATION_EXAMPLE_PAYLOAD],
)


def _translate_variation(
    tlr: Translator, variation_request: VariationRequest
) -> TranslationResult:
    """Perform variant translation

    :param tlr: Translator instance
    :param variation_request: Input variation request to translate
    :return: TranslationResult object with translated variation, if translation is
        successful. Otherwise, return error message
    """
    definition = variation_request.definition

    try:
        translated_variation = tlr.translate_variation(
            definition, **variation_request.model_dump(mode="json")
        )
        return TranslationResult(variation=translated_variation)
    except DataProxyValidationError as e:
        return TranslationResult(error=str(e))
    except HGVSParseError:
        return TranslationResult(
            error=f'Unable to parse HGVS expression "{definition}"'
        )
    except NotImplementedError:
        return TranslationResult(
            error=f"Variation class for {definition} is currently unsupported."
        )
    except TranslationError:
        return TranslationResult(error=f'Unable to translate "{definition}"')


def _handle_translation_request(
    tlr: Translator, var_req: VariationRequest
) -> objects.SupportedVrsVariation:
    """Perform variant translation and convert known exceptions to appropriate HTTP responses

    :param tlr: Translator instance
    :param var_req: request object relayed to variation endpoint
    :return: VRS variation instance
    :raise HTTPException: return 422 response if
       * Variant definition cannot be translated
       * Reference base in gnomad/VCF-style expression fails to validate
       * translator returns not-implemented variation type
    """
    translation_result = _translate_variation(tlr, var_req)
    if translation_result.error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=translation_result.error,
        )

    return translation_result.variation  # type: ignore


def _register_variations(
    av: AnyVar, variation_requests: list[VariationRequest]
) -> list[RegisterVariationResponse]:
    """Bulk register variations

    :param av: AnyVar instance
    :param variation_requests: Input variation requests to register
    :return: List of RegisterVariationResponse objects in the same order as the input.
        Variations that fail translation are not registered and are returned with null
        `object` and `object_id` fields. Registration or liftover failure messages may
        also be included in the `messages` field.
    """
    translation_results: list[TranslationResult] = []
    variations_to_store: list[objects.SupportedVrsObject] = []

    for variation_request in variation_requests:
        translation_result = _translate_variation(av.translator, variation_request)
        translation_results.append(translation_result)

        if translation_result.variation:
            variations_to_store.append(translation_result.variation)

    if variations_to_store:
        av.put_objects(variations_to_store)

    responses: list[RegisterVariationResponse] = []

    for variation_request, translation_result in zip(
        variation_requests, translation_results, strict=True
    ):
        if not translation_result.variation:
            responses.append(
                RegisterVariationResponse(
                    input_variation=variation_request,
                    messages=[translation_result.error]
                    if translation_result.error
                    else [],
                )
            )
            continue

        # add variant metadata
        av.create_timestamp_if_missing(translation_result.variation.id)  # type: ignore (ID guaranteed to be present)
        messages: list[str] = (
            liftover.add_liftover_mapping(
                variation=translation_result.variation,
                storage=av.object_store,
                dataproxy=av.translator.dp,
            )
            or []
        )

        responses.append(
            RegisterVariationResponse(
                input_variation=variation_request,
                object=translation_result.variation,
                object_id=translation_result.variation.id
                if translation_result.variation
                else None,
                messages=messages,
            )
        )

    return responses


@variations_router.put(
    "/variation",
    response_model_exclude_none=True,
    summary="Register a new allele or copy number object",
    description="Provide a variation definition  to be normalized and registered with AnyVar. A complete VRS Allele or Copy Number object and ID is returned.",
)
def register_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> RegisterVariationResponse:
    """Register a variation based on a provided description or reference."""
    av: AnyVar = request.app.state.anyvar

    responses: list[RegisterVariationResponse] = _register_variations(av, [variation])
    return responses[0]


@variations_router.put(
    "/variations",
    response_model_exclude_none=True,
    summary="Bulk register alleles or copy number objects",
    description="Provide a list of variation definitions to be normalized and registered with AnyVar. The response contains one result per input, in the same order. Variations that fail translation are not registered and are returned with null `object` and `object_id` fields. Registration or liftover failure messages may also be included in the `messages` field.",
)
def register_variations(
    request: Request,
    variations: Annotated[
        list[VariationRequest], Body(description="List of variations to register")
    ],
) -> list[RegisterVariationResponse]:
    """Register multiple variations based on provided descriptions or references."""
    av: AnyVar = request.app.state.anyvar
    return _register_variations(av, variations)


PUT_VRS_VARIATION_EXAMPLE_PAYLOAD = {
    "location": {
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


@variations_router.put(
    "/vrs_variation",
    summary="Register a VRS variation",
    description="Provide a valid VRS variation object to be registered with AnyVar. Returns a fully-identified VRS object.",
    response_model_exclude_none=True,
)
def register_vrs_variation(
    request: Request,
    variation: Annotated[
        objects.SupportedVrsVariation,
        Body(
            description="Valid VRS object.",
            examples=[PUT_VRS_VARIATION_EXAMPLE_PAYLOAD],
        ),
    ],
) -> RegisterVariationResponse:
    """Register a complete VRS variation object.

    No additional formatting or normalization is performed. IDs are added if not provided.
    """
    av: AnyVar = request.app.state.anyvar
    input_variation = variation
    try:
        av.put_objects([variation])
    except IncompleteVrsObjectError:
        variation = objects.recursive_identify(variation)
        av.put_objects([variation])

    liftover_messages = liftover.add_liftover_mapping(
        variation, av.object_store, av.translator.dp
    )

    return RegisterVariationResponse(
        input_variation=input_variation,
        object=variation,
        object_id=variation.id,
        messages=liftover_messages or [],
    )


@variations_router.post(
    "/variation",
    response_model_exclude_none=True,
    summary="Retrieve a registered VRS allele or copy number variation",
    description="Provide a variation definition to be normalized and searched for in AnyVar",
)
def get_variation(
    request: Request,
    variation: Annotated[VariationRequest, _variation_request_body],
) -> GetObjectResponse:
    """Search for registered variation"""
    av: AnyVar = request.app.state.anyvar
    translated_variation = _handle_translation_request(av.translator, variation)
    vrs_id: str = translated_variation.id  # type: ignore
    _ = get_vrs_object(av, vrs_id)  # raise NOT_FOUND for vrs_id not present in DB
    return GetObjectResponse(messages=[], data=translated_variation)


@variations_router.get(
    "/variations",
    response_model_exclude_none=True,
    operation_id="searchVariations",
    summary="Search for registered variations by genomic region",
    description="Return all variants with start and end positions that fall within the provided start and end arguments (inclusive).",
)
def search_variations(
    request: Request,
    accession: Annotated[
        str,
        Query(
            ...,
            description='Sequence accession identifier (for example: `"ga4gh:SQ.8_liLu1aycC0tPQPFmUaGXJLDs5SbPZ5"`)',
            examples=["ga4gh:SQ.8_liLu1aycC0tPQPFmUaGXJLDs5SbPZ5"],
        ),
    ],
    start: Annotated[
        int,
        Query(..., description="Start position for genomic region", examples=[2781631]),
    ],
    end: Annotated[
        int,
        Query(..., description="End position for genomic region", examples=[2781758]),
    ],
    page_size: int = Query(1000, ge=1, le=10000),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
) -> SearchResponse:
    """Perform genomic coordinate-based search over all registered variations."""
    av: AnyVar = request.app.state.anyvar
    try:
        if accession.startswith("ga4gh:"):
            ga4gh_id = accession
        else:
            ga4gh_id = av.translator.get_sequence_id(accession)
    except KeyError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Unable to dereference provided accession ID",
        ) from e

    if not ga4gh_id:
        return SearchResponse(variations=[], next_cursor=None)

    try:
        refget_accession = ga4gh_id.split("ga4gh:")[-1]
        page = av.object_store.search_alleles(
            refget_accession, start, end, page_size=page_size, cursor=cursor
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            detail="Search not implemented for current storage backend",
        ) from e

    return SearchResponse(variations=page.items, next_cursor=page.next_cursor)
