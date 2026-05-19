"""Tests for async /variations and /variation endpoints in objects_router."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from ga4gh.vrs import models

from anyvar.anyvar import AnyVar
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.restapi.schema import (
    ErrorResponse,
    RegisterVariationResponse,
    ServiceInfo,
    VariationRequest,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anyvar():
    """Provide a fully-mocked AnyVar for endpoint tests."""
    av = MagicMock(spec=AnyVar)
    av.translator = MagicMock()
    av.translator.dp = MagicMock()
    av.object_store = MagicMock()
    return av


@pytest.fixture
def test_client(mock_anyvar):
    """TestClient wired with a mocked AnyVar instance."""
    anyvar_restapi.state.anyvar = mock_anyvar
    anyvar_restapi.state.service_info = ServiceInfo()
    return TestClient(app=anyvar_restapi)


@pytest.fixture
def sample_allele():
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


VARIATION_PAYLOAD = {
    "definition": "NC_000007.13:g.36561662_36561663del",
}


# ---------------------------------------------------------------------------
# PUT /variations with run_async=true
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestPutVariationsAsync:
    @patch("anyvar.restapi.objects_router._async_imports_available", False)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=False,
    )
    def test_async_not_enabled(self, _mock_enabled, test_client):  # noqa: PT019
        """PUT /variations with run_async=true returns 400 when async queueing is not enabled."""
        resp = test_client.put(
            "/variations",
            json=[VARIATION_PAYLOAD],
            params={"run_async": True},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert (
            "missing" in resp.json()["error"].lower()
            or "modules" in resp.json()["error"].lower()
        )

    @patch("anyvar.restapi.objects_router._async_imports_available", True)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=True,
    )
    @patch("anyvar.restapi.objects_router.validate_run_id_available")
    def test_async_duplicate_run_id(self, mock_validate, _mock_enabled, test_client):  # noqa: PT019
        """PUT /variations with run_async=true and an already-active run_id returns 400."""

        def set_error(run_id, response):
            response.status_code = 400
            return ErrorResponse(error=f"An existing run with id {run_id} is SUCCESS.")

        mock_validate.side_effect = set_error

        resp = test_client.put(
            "/variations",
            json=[VARIATION_PAYLOAD],
            params={"run_async": True, "run_id": "dup-id"},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "dup-id" in resp.json()["error"]

    @patch("anyvar.restapi.objects_router._async_imports_available", True)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=True,
    )
    @patch("anyvar.restapi.objects_router.validate_run_id_available", return_value=None)
    @patch("anyvar.restapi.objects_router.celery_worker")
    def test_async_success(
        self,
        mock_celery,
        _mock_validate,  # noqa: PT019
        _mock_enabled,  # noqa: PT019
        test_client,
    ):
        """PUT /variations with run_async=true returns 202 with Location and Retry-After headers."""
        mock_task = MagicMock()
        mock_task.id = "async-run-123"
        mock_celery.register_variations.apply_async.return_value = mock_task

        resp = test_client.put(
            "/variations",
            json=[VARIATION_PAYLOAD],
            params={"run_async": True},
        )
        assert resp.status_code == HTTPStatus.ACCEPTED
        body = resp.json()
        assert body["run_id"] == "async-run-123"
        assert body["status"] == "PENDING"
        assert "Location" in resp.headers
        assert "/variations/async-run-123" in resp.headers["Location"]
        assert "Retry-After" in resp.headers

    @patch("anyvar.restapi.objects_router._async_imports_available", True)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=True,
    )
    @patch("anyvar.restapi.objects_router.validate_run_id_available", return_value=None)
    @patch("anyvar.restapi.objects_router.celery_worker")
    def test_async_with_custom_run_id(
        self,
        mock_celery,
        _mock_validate,  # noqa: PT019
        _mock_enabled,  # noqa: PT019
        test_client,
    ):
        """PUT /variations with run_async=true and a custom run_id passes it through to Celery."""
        mock_task = MagicMock()
        mock_task.id = "my-custom-id"
        mock_celery.register_variations.apply_async.return_value = mock_task

        resp = test_client.put(
            "/variations",
            json=[VARIATION_PAYLOAD],
            params={"run_async": True, "run_id": "my-custom-id"},
        )
        assert resp.status_code == HTTPStatus.ACCEPTED
        assert resp.json()["run_id"] == "my-custom-id"

        # Verify task_id was passed to apply_async
        call_kwargs = mock_celery.register_variations.apply_async.call_args
        assert (
            call_kwargs.kwargs.get("task_id") == "my-custom-id"
            or call_kwargs[1].get("task_id") == "my-custom-id"
        )


# ---------------------------------------------------------------------------
# PUT /variations synchronous
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestPutVariationsSync:
    @patch("anyvar.restapi.objects_router._register_variations")
    def test_sync_returns_results(
        self, mock_register, test_client, sample_allele, sample_lifted_allele
    ):
        """PUT /variations in sync mode returns 200 with lifted_over_to in each response item."""
        mock_register.return_value = [
            RegisterVariationResponse(
                input_variation=VariationRequest(**VARIATION_PAYLOAD),
                object=sample_allele,
                object_id=sample_allele.id,
                lifted_over_to=sample_lifted_allele,
                messages=[],
            )
        ]

        resp = test_client.put("/variations", json=[VARIATION_PAYLOAD])
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert len(body) == 1
        assert body[0]["object_id"] == sample_allele.id
        assert body[0]["lifted_over_to"] is not None

    @patch("anyvar.restapi.objects_router._register_variations")
    def test_sync_do_liftover_false(self, mock_register, test_client, sample_allele):
        """PUT /variations with do_liftover=false passes the flag through and omits lifted_over_to."""
        mock_register.return_value = [
            RegisterVariationResponse(
                input_variation=VariationRequest(**VARIATION_PAYLOAD),
                object=sample_allele,
                object_id=sample_allele.id,
                messages=[],
            )
        ]

        resp = test_client.put(
            "/variations",
            json=[VARIATION_PAYLOAD],
            params={"do_liftover": False},
        )
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert len(body) == 1
        assert body[0].get("lifted_over_to") is None

        # Verify do_liftover=False was passed through
        call_args = mock_register.call_args
        assert call_args.kwargs.get("do_liftover") is False or call_args[0][2] is False


# ---------------------------------------------------------------------------
# PUT /variation with do_liftover parameter
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestPutVariation:
    @patch("anyvar.restapi.objects_router._register_variations")
    def test_response_includes_lifted_over_to(
        self, mock_register, test_client, sample_allele, sample_lifted_allele
    ):
        """PUT /variation response includes lifted_over_to with the lifted-over VRS variation."""
        mock_register.return_value = [
            RegisterVariationResponse(
                input_variation=VariationRequest(**VARIATION_PAYLOAD),
                object=sample_allele,
                object_id=sample_allele.id,
                lifted_over_to=sample_lifted_allele,
                messages=[],
            )
        ]

        resp = test_client.put("/variation", json=VARIATION_PAYLOAD)
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["object_id"] == sample_allele.id
        assert body["lifted_over_to"] is not None
        assert body["lifted_over_to"]["id"] == sample_lifted_allele.id

    @patch("anyvar.restapi.objects_router._register_variations")
    def test_do_liftover_false(self, mock_register, test_client, sample_allele):
        """PUT /variation with do_liftover=false omits lifted_over_to from the response."""
        mock_register.return_value = [
            RegisterVariationResponse(
                input_variation=VariationRequest(**VARIATION_PAYLOAD),
                object=sample_allele,
                object_id=sample_allele.id,
                messages=[],
            )
        ]

        resp = test_client.put(
            "/variation",
            json=VARIATION_PAYLOAD,
            params={"do_liftover": False},
        )
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body.get("lifted_over_to") is None

        # Verify do_liftover=False was passed to _register_variations
        call_kwargs = mock_register.call_args
        assert call_kwargs.kwargs.get("do_liftover") is False


# ---------------------------------------------------------------------------
# GET /variations/{run_id}
# ---------------------------------------------------------------------------


@pytest.mark.ci_ok
class TestGetVariationsRunStatus:
    @patch("anyvar.restapi.objects_router._async_imports_available", False)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=False,
    )
    def test_async_not_enabled(self, _mock_enabled, test_client):  # noqa: PT019
        """GET /variations/{run_id} returns 400 when async queueing is not enabled."""
        resp = test_client.get("/variations/some-run-id")
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert (
            "missing" in resp.json()["error"].lower()
            or "modules" in resp.json()["error"].lower()
        )

    @patch("anyvar.restapi.objects_router._async_imports_available", True)
    @patch(
        "anyvar.restapi.objects_router.anyvar.anyvar.has_variations_queueing_enabled",
        return_value=True,
    )
    @patch("anyvar.restapi.objects_router.resolve_async_task_status")
    def test_delegates_to_resolve_async_task_status(
        self,
        mock_resolve,
        _mock_enabled,  # noqa: PT019
        test_client,
    ):
        """GET /variations/{run_id} delegates to resolve_async_task_status with the correct run_id."""

        mock_resolve.return_value = JSONResponse(
            content=[{"object_id": "ga4gh:VA.123"}],
            status_code=200,
        )
        # resolve_async_task_status is awaited, so make it an async mock
        mock_resolve.side_effect = None
        mock_resolve.return_value = JSONResponse(
            content=[{"object_id": "ga4gh:VA.123"}],
            status_code=200,
        )

        _ = test_client.get("/variations/run-123")
        # verify resolve_async_task_status was called with the run_id
        mock_resolve.assert_called_once()
        call_args = mock_resolve.call_args
        assert call_args[0][0] == "run-123"
