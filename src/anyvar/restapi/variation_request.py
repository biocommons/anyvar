"""Provide shared request bodies/descriptions/example payloads/etc

No need to put new request body definitions here unless they're shared by >=2 modules
"""

from http import HTTPStatus

from fastapi import Body, HTTPException

from anyvar.core import objects
from anyvar.restapi.examples import VARIATION_OPENAPI_EXAMPLES
from anyvar.restapi.schema import VariationRequest
from anyvar.translate.base import Translator
from anyvar.translate.register import translate_variation

variation_request_body = Body(
    description='Variation description, including (at minimum) a `definition` property. Can provide optional `input_type` if the expected output representation type is known, as well as an assembly_name (e.g.,"GRCh37" or "GRCh38"). If representing copy number, provide `copies` or `copy_change`.',
    openapi_examples=VARIATION_OPENAPI_EXAMPLES,
)


def handle_translation_request(
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
    translation_result = translate_variation(tlr, var_req)
    if translation_result.error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=translation_result.error,
        )

    return translation_result.variation  # type: ignore
