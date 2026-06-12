from http import HTTPStatus

from fastapi.testclient import TestClient
from ga4gh.cat_vrs.models import (
    CategoricalVariant,
    Constraint,
    DefiningAlleleConstraint,
)

from anyvar.restapi.categorical_variants_router import _put_ca_example, _put_psq_example


def test_register_psq(restapi_client: TestClient, alleles: dict):
    payload = CategoricalVariant(
        id="civic.mpid:34",
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


def test_register_psq_nonprotein(restapi_client: TestClient):
    response = restapi_client.put(
        "/categorical_variants/protein_sequence_consequences",
        json=_put_ca_example.model_dump(),
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


def test_register_ca(restapi_client: TestClient, alleles: dict):
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
        ],
    )
    put_response = restapi_client.put(
        "/categorical_variants/canonical_alleles",
        json=payload.model_dump(),
    )
    assert put_response.status_code == HTTPStatus.OK

    get_response = restapi_client.get(
        f"/categorical_variants/canonical_alleles/{payload.id}"
    )
    assert get_response.status_code == HTTPStatus.OK
    assert CategoricalVariant(**get_response.json()) == payload


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
