"""Tests Storage implementation methods directly.
To test against different SQL backends, this test can
be run with different ANYVAR_TEST_STORAGE_URI env var.
"""

from ga4gh.vrs import models

from anyvar.storage.base_storage import Storage, StoredObjectType, VariationMappingType
from anyvar.translate.vrs_python import VrsPythonTranslator


# Test add_objects method (replaces __setitem__)
def test_add_objects(storage, alleles):
    objects_to_add = []
    for allele in alleles.values():
        variation = allele["params"]
        definition = variation["definition"]
        translated_variation = VrsPythonTranslator().translate_variation(definition)
        objects_to_add.append(translated_variation)
    storage.add_objects(objects_to_add)


# Test get_objects method (replaces __getitem__)
def test_get_objects(storage, alleles):
    allele_ids = list(alleles.keys())
    retrieved_objects = list(storage.get_objects(StoredObjectType.ALLELE, allele_ids))
    assert len(retrieved_objects) > 0
    assert sorted([obj.id for obj in retrieved_objects]) == sorted(allele_ids)


# Test object existence using get_objects (replaces __contains__)
def test_object_exists(storage, alleles):
    for allele_id in alleles:
        retrieved_objects = list(
            storage.get_objects(StoredObjectType.ALLELE, [allele_id])
        )
        assert len(retrieved_objects) == 1
        assert retrieved_objects[0] is not None
        assert retrieved_objects[0].id == allele_id


# Test get_all_object_ids method (replaces keys)
def test_get_all_object_ids_contains_alleles(storage, alleles):
    all_ids = list(storage.get_all_object_ids())
    for allele_id in alleles:
        assert allele_id in all_ids


def test_delete_objects(storage, alleles):
    allele_ids = list(alleles.keys())
    storage.delete_objects(StoredObjectType.ALLELE, allele_ids)


# Test that objects were deleted
def test_objects_deleted(storage, alleles):
    """
    Depends on test_delete_objects having been run
    """
    for allele_id in alleles:
        retrieved_objects = list(
            storage.get_objects(StoredObjectType.ALLELE, [allele_id])
        )
        assert len(retrieved_objects) == 0


def test_mappings_crud(storage: Storage, alleles: dict):
    allele_38_fixture = alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_38 = models.Allele(**allele_38_fixture["allele_response"]["object"])
    allele_37_fixture = alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
    allele_37 = models.Allele(**allele_37_fixture["allele_response"]["object"])

    storage.add_objects([allele_38, allele_37])
    storage.add_mapping(allele_38.id, allele_37.id, VariationMappingType.LIFTOVER)

    assert storage.get_mappings(allele_38.id, VariationMappingType.LIFTOVER) == [
        allele_37.id
    ]

    storage.delete_mapping(allele_38.id, allele_37.id, VariationMappingType.LIFTOVER)


def test_cascading_delete(storage: Storage, alleles: dict):
    allele_38_fixture = alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_38 = models.Allele(**allele_38_fixture["allele_response"]["object"])
    allele_37_fixture = alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
    allele_37 = models.Allele(**allele_37_fixture["allele_response"]["object"])

    storage.add_objects([allele_38, allele_37])
    storage.add_mapping(allele_38.id, allele_37.id, VariationMappingType.LIFTOVER)

    storage.delete_objects(StoredObjectType.ALLELE, [allele_38.id])
    storage.delete_objects(StoredObjectType.ALLELE, [allele_37.id])
