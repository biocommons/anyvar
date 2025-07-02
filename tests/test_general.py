"""Check basic functions of general endpoint(s)"""

from http import HTTPStatus
from pathlib import Path

import jsonschema
import yaml
from fastapi.testclient import TestClient


def test_info(client: TestClient):
    response = client.get("/info")
    assert response.status_code == HTTPStatus.OK
    assert "anyvar" in response.json()
    assert "ga4gh_vrs" in response.json()


def test_service_info(client: TestClient, test_data_dir: Path):
    response = client.get("/service-info")
    response.raise_for_status()

    with (test_data_dir / "service_info_openapi.yaml").open() as f:
        spec = yaml.safe_load(f)

    resp_schema = spec["paths"]["/service-info"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    resolver = jsonschema.RefResolver.from_schema(spec)
    data = response.json()
    jsonschema.validate(instance=data, schema=resp_schema, resolver=resolver)


def test_summary_statistics(client: TestClient):
    response = client.get("/stats/all")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"variation_type": "all", "count": 2}
