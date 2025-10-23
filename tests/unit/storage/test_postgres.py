"""Tests postgres storage implementation methods directly."""

import os

import pytest
from ga4gh.vrs import models

from anyvar.storage.base_storage import StoredObjectType
from anyvar.storage.postgres import PostgresObjectStore
from anyvar.utils import types
from anyvar.utils.funcs import build_vrs_variant_from_dict


@pytest.fixture(scope="session")
def postgres_uri():
    uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    return uri


@pytest.fixture
def focus_alleles(alleles: dict):
    """A small subset of test alleles to use in more focused tests

    This is a tuple because many checks assume a specific order of these objects
    """
    return tuple(
        build_vrs_variant_from_dict(a["variation"])
        for a in (
            alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"],
            alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"],
            alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"],
        )
    )


@pytest.fixture
def validated_vrs_alleles(alleles: dict):
    """All allele fixtures, transformed into VRS Pydantic models w/ other test metadata removed"""
    return {k: build_vrs_variant_from_dict(v["variation"]) for k, v in alleles.items()}


@pytest.fixture
def postgres_storage(postgres_uri: str):
    """Reset storage state after each test case"""
    storage = PostgresObjectStore(postgres_uri)
    yield storage
    storage.wipe_db()


@pytest.mark.ci_ok
def test_db_lifecycle(
    postgres_uri: str, validated_vrs_alleles: dict[str, models.Allele]
):
    # set up and populate DB
    storage = PostgresObjectStore(postgres_uri)
    allele_38 = validated_vrs_alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_37 = validated_vrs_alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
    storage.add_objects([allele_38, allele_37])
    storage.add_annotation(
        types.Annotation(
            object_id=allele_38.id,
            annotation_type="classification",
            annotation_value="uncertain",
        )
    )
    storage.add_mapping(
        types.VariationMapping(
            source_id=allele_38.id,
            dest_id=allele_37.id,
            mapping_type=types.VariationMappingType.LIFTOVER,
        )
    )

    # wipe_db removes objects
    storage.wipe_db()
    result = storage.get_objects(
        StoredObjectType.SEQUENCE_REFERENCE,
        [allele_38.location.sequenceReference.refgetAccession],
    )
    assert result == []


def test_alleles_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad test coverage of CRUD methods for alleles"""
    postgres_storage.add_objects(focus_alleles)

    # get 1 allele
    result = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]

    # get multiple alleles
    result = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) == 2
    assert focus_alleles[1] in list(result)
    assert focus_alleles[2] in list(result)

    # get alleles, including some that don't exist
    result = postgres_storage.get_objects(
        StoredObjectType.ALLELE, ["ga4gh:VA.not_real", focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]
    result = postgres_storage.get_objects(
        StoredObjectType.ALLELE, ["ga4gh:VA.sdfljsdflk"]
    )
    assert result == []

    # add empty allele
    _ = postgres_storage.add_objects([])

    # get contained objects
    result = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # delete objects
    postgres_storage.delete_objects(
        StoredObjectType.ALLELE, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert (
        postgres_storage.get_objects(StoredObjectType.ALLELE, [focus_alleles[1].id])
        == []
    )
    result = postgres_storage.get_objects(
        StoredObjectType.ALLELE, [focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]
    postgres_storage.delete_objects(StoredObjectType.ALLELE, [focus_alleles[0].id])
    assert (
        postgres_storage.get_objects(StoredObjectType.ALLELE, [focus_alleles[0].id])
        == []
    )

    # contained objects persist
    result = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # test that all allele fixtures load w/o issue
    postgres_storage.add_objects(validated_vrs_alleles.values())


def test_sequencelocations_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    sls_to_add = [a.location for a in focus_alleles]
    postgres_storage.add_objects(sls_to_add)

    # get SLs, including one with the wrong type/ID
    result = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sls_to_add[0].id,
        ],
    )
    assert result == [sls_to_add[0]]

    # delete objects, other objects still persist
    postgres_storage.delete_objects(
        StoredObjectType.SEQUENCE_LOCATION, [sls_to_add[2].id]
    )
    result = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [sls_to_add[2].id]
    )
    assert result == []
    result = postgres_storage.get_objects(
        StoredObjectType.SEQUENCE_LOCATION, [sls_to_add[1].id, sls_to_add[0].id]
    )
    assert len(result) == 2
    assert sls_to_add[0] in result
    assert sls_to_add[1] in result

    # test that all sequencelocation fixtures load w/o issue
    all_sls = [a.location for a in validated_vrs_alleles.values()]
    postgres_storage.add_objects(all_sls)


def test_get_all_ids(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    assert postgres_storage.get_all_object_ids() == []
    postgres_storage.add_objects(focus_alleles)
    result = list(postgres_storage.get_all_object_ids())
    assert len(result) == 3
    assert "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU" in result
    assert "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf" in result
    assert "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i" in result


def test_mappings_crud(
    postgres_storage: PostgresObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad coverage of CRUD methods for variation mappings"""
    # prepopulate
    allele_38 = validated_vrs_alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_37 = validated_vrs_alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
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


def test_annotations_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    """Broad coverage of CRUD methods for annotations"""
    # prepopulate
    postgres_storage.add_objects(focus_alleles)

    # add arbitrary annotations
    ann1 = types.Annotation(
        object_id=focus_alleles[0].id,
        annotation_type="classification",
        annotation_value="pathogenic",
    )
    postgres_storage.add_annotation(ann1)
    ann2 = types.Annotation(
        object_id=focus_alleles[1].id,
        annotation_type="sample_count",
        annotation_value=5,
    )
    postgres_storage.add_annotation(ann2)
    ann3 = types.Annotation(
        object_id=focus_alleles[2].id,
        annotation_type="classification",
        annotation_value="likely_benign",
    )
    postgres_storage.add_annotation(ann3)
    ann4 = types.Annotation(
        object_id=focus_alleles[2].id,
        annotation_type="reference",
        annotation_value={"type": "article", "value": "pmid:123456"},
    )
    postgres_storage.add_annotation(ann4)

    # get annotations back
    result = postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[0].id, "classification"
    )
    assert result[0].object_id == ann1.object_id
    assert result[0].annotation_type == ann1.annotation_type
    assert result[0].annotation_value == ann1.annotation_value

    result = postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[2].id, "reference"
    )
    assert result[0].object_id == ann4.object_id
    assert result[0].annotation_type == ann4.annotation_type
    assert result[0].annotation_value == ann4.annotation_value

    result = postgres_storage.get_annotations_by_object_and_type(focus_alleles[2].id)
    sorted(result, key=lambda i: (i.annotation_type, i.annotation_value))
    assert result[0].object_id == ann3.object_id
    assert result[0].annotation_type == ann3.annotation_type
    assert result[0].annotation_value == ann3.annotation_value
    assert result[1].object_id == ann4.object_id
    assert result[1].annotation_type == ann4.annotation_type
    assert result[1].annotation_value == ann4.annotation_value

    # test optional type
    assert postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[0].id
    ) == postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[0].id, annotation_type="classification"
    )

    # fetch nonexistent annotation
    result = postgres_storage.get_annotations_by_object_and_type("ga4gh:VA.ZZZZZZZ")
    assert result == []

    # delete annotations
    result = postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[0].id, "classification"
    )
    postgres_storage.delete_annotation(result[0].id)
    result = postgres_storage.get_annotations_by_object_and_type(
        focus_alleles[0].id, "classification"
    )
    assert result == []
