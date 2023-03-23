from typing import Dict, Optional

import requests
from ga4gh.vrs import models as vrs_models
from ga4gh.vrsatile.pydantic.vrs_models import VRSTypes

from . import TranslationException, TranslatorConnectionException, _Translator

variation_class_map = {
    VRSTypes.ALLELE: vrs_models.Allele,
    VRSTypes.TEXT: vrs_models.Text
}

class VariationNormalizerRestTranslator(_Translator):

    def __init__(self, endpoint_uri: str):
        """Initialize normalizer-based translator.

        :param endpoint_uri: base REST endpoint address
        :raises TranslatorConnectionException: if endpoint doesn't respond to initial
            query
        """
        self.endpoint_base = endpoint_uri

        openapi_docs = self.endpoint_base + "openapi.json"
        resp = requests.get(openapi_docs)
        if resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at "
                f"{openapi_docs}"
            )

    def _send_rest_request(self, request_url: str) -> requests.Response:
        """Emit normalization request. Broken out to enable mocking.

        :param request_url: URL containing normalization request parameters
        :return: content of response
        """
        return requests.get(request_url)

    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        req_url = self.endpoint_base + f"translate_identifier?identifier={accession_id}&target_namespaces=ga4gh"  # noqa: E501
        resp = self._send_rest_request(req_url)
        if resp.status_code == 404:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at {req_url}")  # noqa: E501
        elif resp.status_code == 500:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned server error for {accession_id}"  # noqa: E501
            )
        elif resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} for {accession_id}"  # noqa: E501
            )

        resp_json = resp.json()
        if resp_json.get("warnings") or len(resp_json.get("aliases", [])) == 0:
            raise KeyError(f"Unable to find GA4GH ID for {accession_id}")
        return resp_json["aliases"][0]

    @staticmethod
    def _safe_check_variation_type(var_normalizer_response: Dict) -> Optional[str]:
        """Safely check variation type in response from variation normalizer. Resilient
        to different response structures.

        :param var_normalizer_response: complete response received from normalizer
        :return: type value if exists, None otherwise
        """
        variation_descriptor = var_normalizer_response.get("variation_descriptor")
        if not variation_descriptor:
            return None
        variation = variation_descriptor.get("variation")
        if not variation:
            return None
        return variation.get("type")

    def translate(
        self, var: str, untranslatable_to_text: bool, **kwargs: Dict
    ) -> vrs_models.Allele:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided text object describing or referencing a variation.
        :param untranslatable_to_text: if True, store un-normalized descriptions
            as Text objects
        :raises TranslatorConnectionException: if translation request returns error
        """

        req_url = self.endpoint_base + f"normalize?q={var}&untranslatable_returns_text=true"  # noqa: E501
        resp = self._send_rest_request(req_url)
        if resp.status_code == 404:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at "
                f"{req_url}"
            )
        elif resp.status_code == 500:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned server error for {var}"
            )
        elif resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} "
                f"for {var}"
            )

        resp_json = resp.json()
        variation_type = self._safe_check_variation_type(resp_json)

        # TODO -- further narrow scope on when to store variant as text vs not?
        if variation_type is None or \
                (not untranslatable_to_text and resp_json.get("warnings")):
                raise TranslationException(f"Unable to store {var}.")
        if variation_type not in variation_class_map:
            raise NotImplementedError(
                "AnyVar currently only supports Allele and Text storage"
            )
        variation = resp_json["variation_descriptor"]["variation"]
        return variation_class_map[variation_type](**variation)
