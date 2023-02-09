from typing import Dict
import requests
from ga4gh.vrs import models as vrs_models

from . import _Translator, TranslatorConnectionException, TranslationException


class VariationNormalizerRestTranslator(_Translator):

    def __init__(self, endpoint_uri: str):
        """Initialize normalizer-based translator.

        :param endpoint_uri: base REST endpoint address
        :raises TranslatorConnectionException: if endpoint doesn't respond to initial query
        """
        self.endpoint_base = endpoint_uri

        openapi_docs = self.endpoint_base + "openapi.json"
        resp = requests.get(openapi_docs)
        if resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at {openapi_docs}"
            )

    def _send_rest_request(self, request_url: str):
        """Emit normalization request. Broken out to enable mocking.

        :param request_url: URL containing normalization request parameters
        """
        return requests.get(request_url)

    def translate(self, var: str, **kwargs: Dict) -> vrs_models.Allele:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided text object describing or referencing a variation.
        :raises TranslatorConnectionException: if translation request returns error
        """

        req_url = self.endpoint_base + f"normalize?q={var}"
        resp = self._send_rest_request(req_url)
        if resp.status_code == 404:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at {req_url}"
            )
        elif resp.status_code == 500:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned server error for {var}"
            )
        elif resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} for {var}"
            )

        resp_json = resp.json()
        if resp_json.get("warnings"):
            raise TranslationException(f"Unable to normalize {var}.")
        variation = resp_json["variation_descriptor"]["variation"]
        if variation["type"] != "Allele":
            raise NotImplementedError("AnyVar currently only supports Allele storage")

        return vrs_models.Allele(**variation)
