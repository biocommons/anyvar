"""Tests for anyvar.translate.register module."""

from unittest.mock import MagicMock, patch

import pytest
from ga4gh.vrs import models
from ga4gh.vrs.dataproxy import DataProxyValidationError
from hgvs.exceptions import HGVSParseError

from anyvar.restapi.schema import TranslationResult, VariationRequest
from anyvar.translate.base import TranslationError
from anyvar.translate.register import register_variations, translate_variation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_translator():
    tlr = MagicMock()
    tlr.dp = MagicMock()
    return tlr


@pytest.fixture
def sample_allele():
    """Return a minimal Allele object for testing."""
    allele = models.Allele(
        location=models.SequenceLocation(
            sequenceReference=models.SequenceReference(
                refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
            ),
            start=36561661,
            end=36561663,
        ),
        state=models.LiteralSequenceExpression(sequence=""),
    )
    allele.id = "ga4gh:VA.test123"
    return allele


@pytest.fixture
def sample_lifted_allele():
    """Return a mock lifted-over Allele."""
    allele = models.Allele(
        location=models.SequenceLocation(
            sequenceReference=models.SequenceReference(
                refgetAccession="SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
            ),
            start=100,
            end=200,
        ),
        state=models.LiteralSequenceExpression(sequence="A"),
    )
    allele.id = "ga4gh:VA.lifted123"
    return allele


@pytest.fixture
def sample_variation_request():
    return VariationRequest(definition="NC_000007.13:g.36561662_36561663del")


@pytest.fixture
def mock_anyvar(mock_translator, sample_allele):
    av = MagicMock()
    av.translator = mock_translator
    av.translator.translate_variation.return_value = sample_allele
    av.object_store = MagicMock()
    av.translator.dp = MagicMock()
    return av


# ---------------------------------------------------------------------------
# Tests: translate_variation()
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestTranslateVariation:
    def test_success(self, mock_translator, sample_allele, sample_variation_request):
        """Successful translation returns a TranslationResult with variation set and no error."""
        mock_translator.translate_variation.return_value = sample_allele
        result = translate_variation(mock_translator, sample_variation_request)

        assert isinstance(result, TranslationResult)
        assert result.variation == sample_allele
        assert result.error is None
        mock_translator.translate_variation.assert_called_once()

    def test_data_proxy_validation_error(
        self, mock_translator, sample_variation_request
    ):
        """DataProxyValidationError during translation produces an error message in the result."""
        mock_translator.translate_variation.side_effect = DataProxyValidationError(
            "Reference mismatch"
        )
        result = translate_variation(mock_translator, sample_variation_request)

        assert result.variation is None
        assert "Reference mismatch" in result.error

    def test_hgvs_parse_error(self, mock_translator, sample_variation_request):
        """HGVSParseError during translation produces an 'Unable to parse' error message."""
        mock_translator.translate_variation.side_effect = HGVSParseError()
        result = translate_variation(mock_translator, sample_variation_request)

        assert result.variation is None
        assert "Unable to parse HGVS expression" in result.error
        assert sample_variation_request.definition in result.error

    def test_not_implemented_error(self, mock_translator, sample_variation_request):
        """NotImplementedError during translation produces a 'currently unsupported' error message."""
        mock_translator.translate_variation.side_effect = NotImplementedError()
        result = translate_variation(mock_translator, sample_variation_request)

        assert result.variation is None
        assert "currently unsupported" in result.error

    def test_translation_error(self, mock_translator, sample_variation_request):
        """TranslationError during translation produces an 'Unable to translate' error message."""
        mock_translator.translate_variation.side_effect = TranslationError()
        result = translate_variation(mock_translator, sample_variation_request)

        assert result.variation is None
        assert "Unable to translate" in result.error
        assert sample_variation_request.definition in result.error


# ---------------------------------------------------------------------------
# Tests: register_variations()
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestRegisterVariations:
    @patch("anyvar.translate.register.liftover")
    @patch("anyvar.translate.register.translate_variation")
    def test_success_with_liftover(
        self,
        mock_translate,
        mock_liftover_mod,
        mock_anyvar,
        sample_allele,
        sample_lifted_allele,
        sample_variation_request,
    ):
        """Successful registration calls liftover and populates object, object_id."""
        mock_translate.return_value = TranslationResult(variation=sample_allele)
        mock_liftover_mod.add_liftover_mapping.return_value = (
            None,
            sample_lifted_allele,
        )

        responses = register_variations(mock_anyvar, [sample_variation_request])

        assert len(responses) == 1
        resp = responses[0]
        assert resp.object == sample_allele
        assert resp.object_id == sample_allele.id
        assert resp.messages == []
        mock_anyvar.put_objects.assert_called_once_with([sample_allele])
        mock_anyvar.create_timestamp_if_missing.assert_called_once_with(
            sample_allele.id
        )
        mock_liftover_mod.add_liftover_mapping.assert_called_once()

    @patch("anyvar.translate.register.liftover")
    @patch("anyvar.translate.register.translate_variation")
    def test_mixed_success_and_failure(
        self,
        mock_translate,
        mock_liftover_mod,
        mock_anyvar,
        sample_allele,
        sample_lifted_allele,
    ):
        """Batch with one valid and one invalid variation: only the valid one is stored and lifted over."""
        good_req = VariationRequest(definition="NC_000007.13:g.36561662_36561663del")
        bad_req = VariationRequest(definition="invalid-variant")

        mock_translate.side_effect = [
            TranslationResult(variation=sample_allele),
            TranslationResult(error='Unable to translate "invalid-variant"'),
        ]
        mock_liftover_mod.add_liftover_mapping.return_value = (
            None,
            sample_lifted_allele,
        )

        responses = register_variations(mock_anyvar, [good_req, bad_req])

        assert len(responses) == 2

        # Good response
        assert responses[0].object == sample_allele
        assert responses[0].object_id == sample_allele.id
        assert responses[0].messages == []

        # Bad response
        assert responses[1].object is None
        assert responses[1].object_id is None
        assert "Unable to translate" in responses[1].messages[0]

        # Only the successful variation should be stored
        mock_anyvar.put_objects.assert_called_once_with([sample_allele])

    @patch("anyvar.translate.register.liftover")
    @patch("anyvar.translate.register.translate_variation")
    def test_liftover_failure_returns_messages(
        self,
        mock_translate,
        mock_liftover_mod,
        mock_anyvar,
        sample_allele,
        sample_variation_request,
    ):
        """When liftover fails, response includes error messages."""
        mock_translate.return_value = TranslationResult(variation=sample_allele)
        mock_liftover_mod.add_liftover_mapping.return_value = (
            ["Unable to complete liftover: some error"],
            None,
        )

        responses = register_variations(mock_anyvar, [sample_variation_request])

        assert len(responses) == 1
        resp = responses[0]
        assert resp.object == sample_allele
        assert resp.object_id == sample_allele.id
        assert resp.messages == ["Unable to complete liftover: some error"]

    @patch("anyvar.translate.register.liftover")
    @patch("anyvar.translate.register.translate_variation")
    def test_all_translations_fail(
        self,
        mock_translate,
        mock_liftover_mod,
        mock_anyvar,
    ):
        """When all translations fail, no objects are stored and no liftover is attempted."""
        bad_req = VariationRequest(definition="bad-variant")
        mock_translate.return_value = TranslationResult(
            error='Unable to translate "bad-variant"'
        )

        responses = register_variations(mock_anyvar, [bad_req])

        assert len(responses) == 1
        assert responses[0].object is None
        assert responses[0].object_id is None
        assert "Unable to translate" in responses[0].messages[0]

        # put_objects should not be called when nothing translates
        mock_anyvar.put_objects.assert_not_called()
        mock_liftover_mod.add_liftover_mapping.assert_not_called()
