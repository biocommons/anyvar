"""Normalize incoming variation descriptions with the VICC Variation Normalizer."""
from http import HTTPStatus
from typing import Dict, Optional

import requests

from anyvar.utils.types import VrsPythonVariation, variation_class_map

from . import TranslatorConnectionException, _Translator


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
        if resp.status_code != HTTPStatus.OK:
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

    @staticmethod
    def _safe_check_variation_type(var_normalizer_response: Dict) -> Optional[str]:
        """Safely check variation type in response from variation normalizer. Resilient
        to different response structures.

        :param var_normalizer_response: complete response received from normalizer
        :return: type value if exists, None otherwise
        """
        # variation_descriptor = var_normalizer_response.get("variation_descriptor")
        # if not variation_descriptor:
        #     return None
        variation = var_normalizer_response.get("variation")
        if not variation:
            return None
        return variation.get("type")

    def translate(self, var: str) -> Optional[VrsPythonVariation]:
        """Translate provided variation text into a normalized VRS object.

        :param var: user-provided string describing or referencing a variation.
        :returns: VRS-Python variation object if able to normalize
        :raises TranslatorConnectionException: if translation request returns error
        """
        req_url = self.endpoint_base + f"translate_from?variation={var}"
        resp = self._send_rest_request(req_url)

        if resp.status_code == HTTPStatus.NOT_FOUND:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at " f"{req_url}"
            )
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned server error for {var}"
            )
        elif resp.status_code != HTTPStatus.OK:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} " f"for {var}"
            )

        resp_json = resp.json()
        variation_type = self._safe_check_variation_type(resp_json)

        if not variation_type:
            return None

        if variation_type not in variation_class_map:
            raise NotImplementedError(f"{variation_type} isn't supported by AnyVar yet.")

        variation = resp_json["variation"]
        return variation_class_map[variation_type](**variation)

    def translate_vcf_row(self, coords: str) -> Optional[VrsPythonVariation]:
        """Translate VCF-like data to a normalized VRS object.

        :param coords: string formatted a la "<chr>-<pos>-<ref>-<alt>"
        :return: VRS variation (using VRS-Python class) if translation is successful
        :raises TranslatorConnectionException: if translation request returns HTTP error
        :raises NotImplementedError: if unsupported variation type is encountered
        """
        req_url = f"{self.endpoint_base}translate_from?variation={coords}&fmt=gnomad"
        resp = self._send_rest_request(req_url)

        if resp.status_code == HTTPStatus.NOT_FOUND:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at " f"{req_url}"
            )
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TranslatorConnectionException(
                "Variation Normalizer REST endpoint returned server error for VCF " f"{coords}"
            )
        elif resp.status_code != HTTPStatus.OK:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} "
                f"for VCF {coords}"
            )

        resp_json = resp.json()
        if resp_json.get("warnings"):
            return None

        variation_type = resp_json["variation"]["type"]

        if not variation_type:
            return None

        if variation_type not in variation_class_map:
            raise NotImplementedError(f"{variation_type} isn't supported by AnyVar yet.")

        variation = resp_json["variation"]
        return variation_class_map[variation_type](**variation)

    def get_sequence_id(self, accession_id: str) -> str:
        """Get GA4GH sequence identifier for provided accession ID

        :param accession_id: ID to convert
        :return: equivalent GA4GH sequence ID
        :raise: KeyError if no equivalent ID is available
        """
        req_url = (
            self.endpoint_base
            + f"translate_identifier?identifier={accession_id}&target_namespaces=ga4gh"
        )  # noqa: E501
        resp = self._send_rest_request(req_url)
        if resp.status_code == HTTPStatus.NOT_FOUND:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at {req_url}"  # noqa: E501
            )
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned server error for {accession_id}"  # noqa: E501
            )
        elif resp.status_code != HTTPStatus.OK:
            raise TranslatorConnectionException(
                f"Variation Normalizer REST endpoint returned {resp.status_code} for {accession_id}"  # noqa: E501
            )

        resp_json = resp.json()
        if resp_json.get("warnings") or len(resp_json.get("aliases", [])) == 0:
            raise KeyError(f"Unable to find GA4GH ID for {accession_id}")
        return resp_json["aliases"][0]
