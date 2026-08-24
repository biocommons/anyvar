from http import HTTPStatus
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from ga4gh.cat_vrs.models import (
    CategoricalVariant,
    Constraint,
    DefiningAlleleConstraint,
)

from anyvar.restapi.categorical_variants_router import _put_ca_example, _put_psq_example


class _CatvarMemberSet(NamedTuple):
    catvar: CategoricalVariant
    id_38g: str
    id_37g: str
    id_c: str
    id_p: str
    expr_38g: str | None
    expr_37g: str | None
    expr_c: str | None
    expr_p: str | None


@pytest.fixture
def psq_example(alleles: dict) -> _CatvarMemberSet:
    """CIViC molecular profile for EGFR T790M

    civic var url: https://civicdb.org/variants/34/summary
    civic mp url: https://civicdb.org/molecular-profiles/34/summary
    """
    defining_allele_id = "ga4gh:VA.sMA9h8fzDi0RvweMlxtD0_Oi8B-JZ1V-"
    return _CatvarMemberSet(
        catvar=CategoricalVariant(
            id="civic.mpid:34",
            name="EGFR T790M",
            constraints=[
                Constraint(
                    root=DefiningAlleleConstraint(
                        allele=alleles[defining_allele_id]["variation"]
                    )
                )
            ],
        ),
        id_38g="ga4gh:VA._1-3emZcNV1di2ClHh5aSJOjrv0Grf75",
        id_37g="ga4gh:VA.UiSJUln6KsWMXcIgdwsrPvS9dlGzwOib",
        id_c="ga4gh:VA.UcdCCED1ezuKzrCRazbW6SPXpse6q95g",
        id_p=defining_allele_id,
        expr_38g="NC_000007.14:g.55181378C>T",
        expr_37g="NC_000007.13:g.55249071C>T",
        expr_c="NM_005228.4:c.2369C>T",
        expr_p="NP_005219.2:p.Thr790Met",
    )


@pytest.fixture
def ca_example(alleles: dict) -> _CatvarMemberSet:
    # allele reg url: https://reg.clinicalgenome.org/redmine/projects/registry/genboree_registry/by_canonicalid?canonicalid=CA321211
    defining_allele_expr = "NC_000011.10:g.68032291C>T"
    defining_allele_id = "ga4gh:VA.EEk-kGY1YF1QgGShZ040hl3V5HWXsL4q"
    return _CatvarMemberSet(
        catvar=CategoricalVariant(
            id="clingen.allele:CA321211",
            name=defining_allele_expr,
            constraints=[
                Constraint(
                    root=DefiningAlleleConstraint(
                        allele=alleles[defining_allele_id]["variation"]
                    )
                )
            ],
        ),
        id_38g=defining_allele_id,
        id_37g="ga4gh:VA.ULoQTpBaN51VvUkhDk8eDjCBl2tFcs6e",
        id_c="ga4gh:VA.LPlBUf5ui6MTu4DzlF6jOpXJ0PBxvfdZ",
        id_p="ga4gh:VA.hR_tdETF6LLcAaIj7e3OtsB6EgO2Ex6H",
        expr_38g="NC_000011.10:g.68032291C>T",
        expr_37g="NC_000011.9:g.67799758C>T",
        expr_c="NM_002496.4:c.64C>T",
        expr_p="NP_002487.1:p.Pro22Ser",
    )


def test_register_psq(
    restapi_client: TestClient, alleles: dict, psq_example: _CatvarMemberSet
):
    payload = CategoricalVariant(
        id="civic.mpid:34",
        name="EGFR T790M",
        constraints=[
            Constraint(
                root=DefiningAlleleConstraint(
                    allele=alleles[psq_example.id_p]["variation"]
                )
            )
        ],
    )
    put_response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=payload.model_dump(),
    )
    assert put_response.status_code == HTTPStatus.OK

    get_response = restapi_client.get(
        f"/categorical_variants/protein_sequence_consequences/{payload.id}"
    )
    assert get_response.status_code == HTTPStatus.OK
    assert CategoricalVariant(**get_response.json()) == payload


def test_get_unregistered_psq(restapi_client: TestClient):
    response = restapi_client.get(
        "/categorical_variants/protein_sequence_consequences/fake:12345"
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_register_psq_example(restapi_client: TestClient):
    put_response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=_put_psq_example.model_dump(),
    )
    assert put_response.status_code == HTTPStatus.OK

    get_response = restapi_client.get(
        f"/categorical_variants/protein_sequence_consequences/{_put_psq_example.id}"
    )
    assert get_response.status_code == HTTPStatus.OK
    assert CategoricalVariant(**get_response.json()) == _put_psq_example


def test_register_psq_nonprotein(
    restapi_client: TestClient, ca_example: _CatvarMemberSet
):
    response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=ca_example.catvar.model_dump(),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_register_psq_invalid(restapi_client: TestClient, alleles: dict):
    payload = CategoricalVariant(
        name="EGFR T790M",
        constraints=[
            Constraint(
                root=DefiningAlleleConstraint(
                    allele=alleles["ga4gh:VA.sMA9h8fzDi0RvweMlxtD0_Oi8B-JZ1V-"][
                        "variation"
                    ]
                )
            )
        ],
    )
    response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=payload.model_dump(),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_register_ca(restapi_client: TestClient, ca_example: _CatvarMemberSet):
    put_response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=ca_example.catvar.model_dump(),
    )
    assert put_response.status_code == HTTPStatus.OK

    get_response = restapi_client.get(
        f"/categorical_variants/canonical_alleles/{ca_example.catvar.id}"
    )
    assert get_response.status_code == HTTPStatus.OK
    assert CategoricalVariant(**get_response.json()) == ca_example.catvar


def test_register_ca_example(restapi_client: TestClient):
    put_response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=_put_ca_example.model_dump(),
    )
    assert put_response.status_code == HTTPStatus.OK

    get_response = restapi_client.get(
        f"/categorical_variants/canonical_alleles/{_put_ca_example.id}"
    )
    assert get_response.status_code == HTTPStatus.OK
    assert CategoricalVariant(**get_response.json()) == _put_ca_example


def test_register_ca_nongenomic(restapi_client: TestClient):
    response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=_put_psq_example.model_dump(),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_register_ca_invalid(restapi_client: TestClient, alleles: dict):
    payload = CategoricalVariant(
        id="clingen.allele:CA321211",
        name="NC_000007.13:g.36561662_36561663del",
        constraints=[
            Constraint(
                root=DefiningAlleleConstraint(
                    allele=alleles["ga4gh:VA.EEk-kGY1YF1QgGShZ040hl3V5HWXsL4q"][
                        "variation"
                    ]
                )
            ),
            Constraint(
                root=DefiningAlleleConstraint(
                    allele=alleles["ga4gh:VA.EEk-kGY1YF1QgGShZ040hl3V5HWXsL4q"][
                        "variation"
                    ]
                )
            ),
        ],
    )
    response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=payload.model_dump(),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_get_catvars_by_member_id(
    restapi_client: TestClient,
    psq_example: _CatvarMemberSet,
    ca_example: _CatvarMemberSet,
):
    # canonical allele retrieval
    put_response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=ca_example.catvar.model_dump(),
    )
    put_response.raise_for_status()

    response = restapi_client.get(f"/categorical_variants?vrs_id={ca_example.id_38g}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.get(f"/categorical_variants?vrs_id={ca_example.id_37g}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.get(f"/categorical_variants?vrs_id={ca_example.id_c}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.get(f"/categorical_variants?vrs_id={ca_example.id_p}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    # psq retrieval
    put_response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=psq_example.catvar.model_dump(),
    )

    put_response.raise_for_status()
    response = restapi_client.get(f"/categorical_variants?vrs_id={psq_example.id_p}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [psq_example.catvar.model_dump(exclude_none=True)]


def test_get_catvars_by_variation(
    restapi_client: TestClient,
    psq_example: _CatvarMemberSet,
    ca_example: _CatvarMemberSet,
):
    # canonical allele retrieval
    put_response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=ca_example.catvar.model_dump(),
    )
    put_response.raise_for_status()

    response = restapi_client.post(
        "/categorical_variants", json={"definition": ca_example.expr_38g}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.post(
        "/categorical_variants", json={"definition": ca_example.expr_37g}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]
    response = restapi_client.post(
        "/categorical_variants", json={"definition": ca_example.expr_c}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.post(
        "/categorical_variants", json={"definition": ca_example.expr_p}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [ca_example.catvar.model_dump(exclude_none=True)]

    # psq retrieval
    put_response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=psq_example.catvar.model_dump(),
    )

    response = restapi_client.post(
        "/categorical_variants", json={"definition": psq_example.expr_p}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [psq_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.post(
        "/categorical_variants", json={"definition": psq_example.expr_c}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [psq_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.post(
        "/categorical_variants", json={"definition": psq_example.expr_38g}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [psq_example.catvar.model_dump(exclude_none=True)]

    response = restapi_client.post(
        "/categorical_variants", json={"definition": psq_example.expr_37g}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [psq_example.catvar.model_dump(exclude_none=True)]
