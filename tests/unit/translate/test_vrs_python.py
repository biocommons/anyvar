"""Test VRS-Python-based translator

Some tests are designed to test the caching functions, which means they can use fake data
and will run in GitHub actions. Others involve more integration and aren't as easily mockable.
"""

import pytest
from ga4gh.vrs.models import Allele

from anyvar.translate.base import TranslationError
from anyvar.translate.vrs_python import VrsPythonTranslator


def test_translator(translator: VrsPythonTranslator, alleles: dict):
    result = translator.translate_variation("1-35227334-G-A")
    assert result == Allele(
        **alleles["ga4gh:VA.aqLIhSpwt8_SFJ7_9RKK8XVuc-UuzE_h"]["variation"]
    )


def test_translator_specific_assembly(translator: VrsPythonTranslator, alleles: dict):
    result = translator.translate_variation("1-35227334-G-A", assembly_name="GRCh37")
    assert result == Allele(
        **alleles["ga4gh:VA.lHm5O2TRaxF1tYvxutOofpC40WTjGHea"]["variation"]
    )


def test_translator_failed_input(translator: VrsPythonTranslator):
    with pytest.raises(TranslationError):
        _ = translator.translate_variation(
            "GRCh38/hg38 7p22.3-q36.3(chr7:54185-159282390)x1"
        )
