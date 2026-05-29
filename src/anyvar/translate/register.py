"""Provide shared variation registration logic for use by REST API and Celery workers."""

import logging

from ga4gh.vrs.dataproxy import DataProxyValidationError
from hgvs.exceptions import HGVSParseError

from anyvar.anyvar import AnyVar
from anyvar.core import objects
from anyvar.mapping import liftover
from anyvar.restapi.schema import (
    RegisterVariationResponse,
    TranslationResult,
    VariationRequest,
)
from anyvar.translate.base import TranslationError, Translator

_logger = logging.getLogger(__name__)


def translate_variation(
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


def register_variations(
    av: AnyVar,
    variation_requests: list[VariationRequest],
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
        translation_result = translate_variation(av.translator, variation_request)
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
        messages = (
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
                object_id=(
                    translation_result.variation.id
                    if translation_result.variation
                    else None
                ),
                messages=messages,
            )
        )

    return responses
