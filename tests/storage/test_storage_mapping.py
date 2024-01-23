"""Tests the mutable mapping API of the storage backend"""
from ga4gh.vrs import vrs_enref

from anyvar.translate.vrs_python import VrsPythonTranslator

# pause for 5 seconds because Snowflake storage is an async write and
#   tests will sometimes fail on test_storage_mapping
def test_waitforsync():
    import time
    time.sleep(5)

# __getitem__
def test_getitem(storage, alleles):
    for allele_id, allele in alleles.items():
        assert storage[allele_id] is not None

# __contains__
def test_contains(storage, alleles):
    for allele_id, allele in alleles.items():
        assert allele_id in storage

# __len__
def test_len(storage):
    assert len(storage) > 0

# __iter__
def test_iter(storage, alleles):
    obj_iter = iter(storage)
    count = 0
    while True:
        try:
            obj = next(obj_iter)
            count += 1
        except StopIteration:
            break
    assert count == 14

# keys
def test_keys(storage, alleles):
    key_list = storage.keys()
    for allele_id, allele in alleles.items():
        assert allele_id in key_list
        
# __delitem__
def test_delitem(storage, alleles):
    for allele_id, allele in alleles.items():
        del storage[allele_id]

# __setitem__
def test_setitem(storage, alleles):
    for allele_id, allele in alleles.items():
        variation = allele["params"]
        definition = variation["definition"]
        translated_variation = VrsPythonTranslator().translate_variation(definition)
        vrs_enref(translated_variation, storage)