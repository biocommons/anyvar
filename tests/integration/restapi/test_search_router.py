"""Test search functionality."""

from collections.abc import AsyncGenerator
from http import HTTPStatus

import pytest_asyncio
from cool_seq_tool.sources import UtaDatabase
from fastapi.testclient import TestClient

from anyvar.anyvar import AnyVar
from anyvar.restapi.main import app as anyvar_restapi
from anyvar.restapi.schema import ServiceInfo


def test_search(restapi_client: TestClient, preloaded_alleles: dict):
    """Test basic search functions."""
    for allele in preloaded_alleles.values():
        start = allele["variation"]["location"]["start"]
        end = allele["variation"]["location"]["end"]
        refget_ac = allele["variation"]["location"]["sequenceReference"][
            "refgetAccession"
        ]
        accession = f"ga4gh:{refget_ac}"
        resp = restapi_client.get(
            f"/search?accession={accession}&start={start}&end={end}"
        )
        assert resp.status_code == HTTPStatus.OK

        resp_json = resp.json()

        assert len(resp_json["variations"]) == 1

        assert resp_json["variations"][0] == allele["variation"]


@pytest_asyncio.fixture(scope="module")
async def uta_enabled_restapi_client(
    anyvar_instance: AnyVar,
) -> AsyncGenerator[TestClient, None]:
    """RestAPI client instance with UTA injected into app state.

    Broken out from other test client instance because UTA access would require
    additional mocks or a real instance to connect to
    """
    anyvar_restapi.state.anyvar = anyvar_instance
    anyvar_restapi.state.service_info = ServiceInfo()

    uta = await UtaDatabase.create()
    await uta.create_pool()
    anyvar_restapi.state.uta = uta
    with TestClient(app=anyvar_restapi) as client:
        yield client

    await uta._connection_pool.close()  # noqa: SLF001


def test_gene_search(uta_enabled_restapi_client: TestClient, alleles: dict):
    # ensure DB populated
    allele_to_put = alleles["ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe"]["variation"]
    put_resp = uta_enabled_restapi_client.put("/vrs_variation", json=allele_to_put)
    assert put_resp.status_code == HTTPStatus.OK

    # run test
    resp = uta_enabled_restapi_client.get("/search_by_gene?gene=BRAF")
    assert resp.status_code == HTTPStatus.OK
    resp_json = resp.json()
    assert resp_json["variations"]
