"""Tests postgres storage implementation methods directly."""

import json
import os
from pathlib import Path

import pytest
from ga4gh.vrs import models

from anyvar.storage.base_storage import StoredObjectType
from anyvar.storage.postgres import PostgresObjectStore
from anyvar.utils import types
from anyvar.utils.funcs import build_vrs_variant_from_dict


@pytest.fixture
def postgres_storage():
    """Reset storage state after each test case"""
    uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    storage = PostgresObjectStore(uri)
    yield storage
    storage.wipe_db()


@pytest.fixture(scope="session")
def alleles(test_data_dir: Path):
    with (test_data_dir / "variations.json").open() as f:
        data = json.load(f)
        return data["alleles"]


def test_db_lifecycle():
    # TODO test wipe db, maybe test setup?
    pass


def test_alleles_crud(postgres_storage: PostgresObjectStore, alleles: dict):
    """Broad test coverage of CRUD methods for alleles"""
    alleles_to_add = [
        build_vrs_variant_from_dict(a["variation"])
        for a in (
            alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"],
            alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"],
            alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"],
        )
    ]
    postgres_storage.add_objects(alleles_to_add)

    # get 1 allele
    response = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [alleles_to_add[0].id]
    )
    assert response == [alleles_to_add[0]]

    # get multiple alleles
    response = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [alleles_to_add[1].id, alleles_to_add[2].id]
    )
    assert len(list(response)) == 2
    assert alleles_to_add[1] in list(response)
    assert alleles_to_add[2] in list(response)

    # get alleles, including some that don't exist
    response = postgres_storage.get_objects(
        StoredObjectType.ALLELE, ["ga4gh:VA.not_real", alleles_to_add[0].id]
    )
    assert response == [alleles_to_add[0]]
    response = postgres_storage.get_objects(
        StoredObjectType.ALLELE, ["ga4gh:VA.sdfljsdflk"]
    )
    assert response == []

    # add empty allele
    _ = postgres_storage.add_objects([])

    # get contained objects
    response = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [alleles_to_add[0].location.id]
    )
    assert response == [alleles_to_add[0].location]

    # delete objects
    postgres_storage.delete_objects(
        StoredObjectType.ALLELE, [alleles_to_add[1].id, alleles_to_add[2].id]
    )
    assert (
        postgres_storage.get_objects(StoredObjectType.ALLELE, [alleles_to_add[1].id])
        == []
    )
    response = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [alleles_to_add[0].id]
    )
    assert response == [alleles_to_add[0]]
    postgres_storage.delete_objects(StoredObjectType.ALLELE, [alleles_to_add[0].id])
    assert (
        postgres_storage.get_objects(StoredObjectType.ALLELE, [alleles_to_add[0].id])
        == []
    )

    # contained objects persist
    response = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [alleles_to_add[0].location.id]
    )
    assert response == [alleles_to_add[0].location]


def test_sequencelocations_crud(postgres_storage: PostgresObjectStore, alleles: dict):
    sls_to_add = [
        models.SequenceLocation(**a["variation"]["location"])
        for a in (
            alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"],
            alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"],
            alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"],
        )
    ]
    postgres_storage.add_objects(sls_to_add)

    # get SLs, including one with the wrong type/ID
    response = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sls_to_add[0].id,
        ],
    )
    assert response == [sls_to_add[0]]

    # delete objects, other objects still persist
    postgres_storage.delete_objects(
        StoredObjectType.SEQUENCE_LOCATION, [sls_to_add[2].id]
    )
    response = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [sls_to_add[1].id, sls_to_add[0].id]
    )
    assert len(response) == 2
    assert sls_to_add[0] in response
    assert sls_to_add[1] in response


def test_get_all_ids(postgres_storage: PostgresObjectStore, alleles: dict):
    assert postgres_storage.get_all_object_ids() == []
    postgres_storage.add_objects(
        [
            build_vrs_variant_from_dict(a)
            for a in (
                alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]["variation"],
                alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]["variation"],
                alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"]["variation"],
            )
        ]
    )
    response = list(postgres_storage.get_all_object_ids())
    assert len(response) == 3
    assert "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU" in response
    assert "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf" in response
    assert "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i" in response


def test_mappings_crud(postgres_storage: PostgresObjectStore, alleles: dict):
    """Broad coverage of CRUD methods for variation mappings"""
    # prepopulate
    allele_38 = models.Allele(
        **alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]["variation"]
    )
    allele_37 = models.Allele(
        **alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]["variation"]
    )
    postgres_storage.add_objects([allele_38, allele_37])

    # add mapping
    mapping = types.VariationMapping(
        source_id=allele_38.id,
        dest_id=allele_37.id,
        mapping_type=types.VariationMappingType.LIFTOVER,
    )
    postgres_storage.add_mapping(mapping)

    # get mapping
    assert postgres_storage.get_mappings(
        allele_38.id, types.VariationMappingType.LIFTOVER
    ) == [mapping]

    # delete mapping
    postgres_storage.delete_mapping(mapping)
    assert (
        postgres_storage.get_mappings(allele_38.id, types.VariationMappingType.LIFTOVER)
        == []
    )


def test_annotations_crud(postgres_storage: PostgresObjectStore, alleles: dict):
    """Broad coverage of CRUD methods for annotations"""
    # prepopulate
    alleles_to_add = [
        build_vrs_variant_from_dict(a)
        for a in (
            alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]["variation"],
            alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]["variation"],
            alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"]["variation"],
        )
    ]
    postgres_storage.add_objects(alleles_to_add)

    # add arbitrary annotations
    ann1 = types.Annotation(
        object_id=alleles_to_add[0].id,
        annotation_type="classification",
        annotation_value="pathogenic",
    )
    postgres_storage.add_annotation(ann1)
    ann2 = types.Annotation(
        object_id=alleles_to_add[1].id,
        annotation_type="sample_count",
        annotation_value=5,
    )
    postgres_storage.add_annotation(ann2)
    ann3 = types.Annotation(
        object_id=alleles_to_add[2].id,
        annotation_type="classification",
        annotation_value="likely_benign",
    )
    postgres_storage.add_annotation(ann3)
    ann4 = types.Annotation(
        object_id=alleles_to_add[2].id,
        annotation_type="reference",
        annotation_value={"type": "article", "value": "pmid:123456"},
    )
    postgres_storage.add_annotation(ann4)

    # get annotations back
    response = postgres_storage.get_annotations_by_object_and_type(
        alleles_to_add[0].id, "classification"
    )
    assert response[0].object_id == ann1.object_id
    assert response[0].annotation_type == ann1.annotation_type
    assert response[0].annotation_value == ann1.annotation_value

    response = postgres_storage.get_annotations_by_object_and_type(
        alleles_to_add[2].id, "reference"
    )
    assert response[0].object_id == ann4.object_id
    assert response[0].annotation_type == ann4.annotation_type
    assert response[0].annotation_value == ann4.annotation_value

    response = postgres_storage.get_annotations_by_object_and_type(alleles_to_add[2].id)
    sorted(response, key=lambda i: (i.annotation_type, i.annotation_value))
    assert response[0].object_id == ann3.object_id
    assert response[0].annotation_type == ann3.annotation_type
    assert response[0].annotation_value == ann3.annotation_value
    assert response[1].object_id == ann4.object_id
    assert response[1].annotation_type == ann4.annotation_type
    assert response[1].annotation_value == ann4.annotation_value

    # test optional type
    assert postgres_storage.get_annotations_by_object_and_type(
        alleles_to_add[0].id
    ) == postgres_storage.get_annotations_by_object_and_type(
        alleles_to_add[0].id, annotation_type="classification"
    )

    # fetch nonexistent annotation
    response = postgres_storage.get_annotations_by_object_and_type("ga4gh:VA.ZZZZZZZ")
    assert response == []

    # delete annotations
