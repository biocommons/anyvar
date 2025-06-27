"""Check basic functions of general endpoint(s)"""

import re
from datetime import datetime
from http import HTTPStatus

from fastapi.testclient import TestClient

from anyvar.restapi.schema import ServiceEnvironment


def test_info(client: TestClient):
    response = client.get("/info")
    assert response.status_code == HTTPStatus.OK
    assert "anyvar" in response.json()
    assert "ga4gh_vrs" in response.json()


def test_service_info(client: TestClient):
    response = client.get("/service-info")
    assert response.status_code == 200
    expected_version_pattern = r"\d\.\d\."  # at minimum, should be something like "0.1"
    response_json = response.json()
    assert response_json["id"] == "org.ga4gh.gks.anyvar"
    assert response_json["name"] == "anyvar"
    assert response_json["type"]["group"] == "org.ga4gh.gks"
    assert response_json["type"]["artifact"] == "anyvar"
    assert (
        re.match(expected_version_pattern, response_json["type"]["version"])
        or response_json["type"]["version"] == "unknown"
    )
    assert (
        response_json["description"]
        == "This service provides a registry for GA4GH VRS objects."
    )
    assert response_json["organization"] == {
        "name": "GA4GH Genomic Knowledge Standards Workstream",
        "url": "https://www.ga4gh.org/work_stream/genomic-knowledge-standards/",
    }
    assert response_json["contactUrl"] == "Alex.Wagner@nationwidechildrens.org"
    assert response_json["documentationUrl"] == "https://github.com/biocommons/anyvar"
    assert datetime.fromisoformat(response_json["createdAt"])
    assert ServiceEnvironment(response_json["environment"])
    assert (
        re.match(expected_version_pattern, response_json["version"])
        or response_json["version"] == "unknown"
    )


def test_summary_statistics(client: TestClient):
    response = client.get("/stats/all")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"variation_type": "all", "count": 2}
