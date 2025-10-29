"""Check basic functions of general endpoint(s)"""

import re
from pathlib import Path

import jsonschema
import yaml
from fastapi.testclient import TestClient


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
