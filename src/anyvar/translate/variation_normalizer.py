"""Perform translation using the VICC Variation Normalizer."""
import os
from typing import Dict, Optional

import requests
from ga4gh.vrs import models as vrs_models

from anyvar.translate.translate import Translator, TranslatorConnectionException


class VariationNormalizerRestTranslator(Translator):

    def __init__(self, endpoint_uri: Optional[str] = None):
        if not endpoint_uri:
            pass

        # get uri
        # self.endpoint_base = "http://localhost:8000/variation/"
        self.endpoint_base = "https://normalize.cancervariants.org/variation/"

        openapi_docs = self.endpoint_base + "openapi.json"
        resp = requests.get(openapi_docs)
        if resp.status_code != 200:
            raise TranslatorConnectionException(
                f"Failed to get response from Variation Normalizer REST endpoint at {openapi_docs}"
            )

    def translate_from(self, var: str, **kwargs: Dict) -> vrs_models.Allele:
        """

        """

        req_url = self.endpoint_base + f"normalize?q={var}"
        resp = requests.get(req_url)
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
            raise Exception("TODO figure out what exception should get caught")
        variation = resp_json["variation_descriptor"]["variation"]
        if variation["type"] != "Allele":
            raise Exception  # TODO more specific

        return vrs_models.Allele(**variation)
