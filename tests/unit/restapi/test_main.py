"""Check basic functions of general endpoint(s)"""

import re
from pathlib import Path

import jsonschema
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anyvar.restapi.main import app_lifespan
from anyvar.storage import Storage


@pytest.mark.ci_ok
def test_service_info(restapi_client: TestClient, test_data_dir: Path):
    response = restapi_client.get("/service-info")
    response.raise_for_status()

    with (test_data_dir / "service_info_openapi.yaml").open() as f:
        spec = yaml.safe_load(f)

    resp_schema = spec["paths"]["/service-info"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    resolver = jsonschema.RefResolver.from_schema(spec)
    data = response.json()
    jsonschema.validate(instance=data, schema=resp_schema, resolver=resolver)

    # test extra metadata
    assert re.match(r"^2\.\d+\.\d+.?$", data["spec_metadata"]["vrs_version"]), (
        "VRS version is 2.x"
    )
    assert re.match(r"^2\.\d+\.\d+.?$", data["impl_metadata"]["vrs_python_version"]), (
        "VRS-Python version is 2.x"
    )
    assert sorted(data["capabilities_metadata"]["liftover_assemblies"]) == [
        "GRCh37",
        "GRCh38",
    ]


@pytest.mark.ci_ok
def test_fastapi_lifespan(mocker):
    create_storage_mock = mocker.patch("anyvar.anyvar.create_storage")
    storage_mock = mocker.Mock(spec=Storage)
    create_storage_mock.return_value = storage_mock
    create_translator_mock = mocker.patch("anyvar.anyvar.create_translator")
    create_translator_mock.return_value = {}
    app = FastAPI(
        title="AnyVarTest",
        docs_url="/",
        openapi_url="/openapi.json",
        description="Test app",
        lifespan=app_lifespan,
    )
    with TestClient(app):
        create_storage_mock.assert_called_once()
        create_translator_mock.assert_called_once()
        assert app.state.anyvar is not None

    storage_mock.close.assert_called_once()
