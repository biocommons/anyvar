"""Tests the SqlStorage methods that are NOT tested through the
REST API tests.  To test against different SQL backends, this
test must be run with different ANYVAR_TEST_STORAGE_URI settings
and different ANYVAR_SQL_STORE_BATCH_ADD_MODE settings
"""

from ga4gh.vrs.enderef import vrs_enref

from anyvar.storage.snowflake import SnowflakeBatchAddMode, SnowflakeObjectStore
from anyvar.translate.vrs_python import VrsPythonTranslator


# pause for 5 seconds because Snowflake storage is an async write and
#   tests will sometimes fail on test_storage_mapping
def test_waitforsync():
    import time

    time.sleep(5)


# __getitem__
def test_getitem(storage, alleles):
    for allele_id in alleles:
        assert storage[allele_id] is not None


# __contains__
def test_contains(storage, alleles):
    for allele_id in alleles:
        assert allele_id in storage


# __len__
def test_len(storage):
    assert len(storage) > 0


# __iter__
def test_iter(storage):
    obj_iter = iter(storage)
    count = 0
    while True:
        try:
            next(obj_iter)
            count += 1
        except StopIteration:
            break
    assert count == (
        18
        if isinstance(storage, SnowflakeObjectStore)
        and storage.batch_add_mode == SnowflakeBatchAddMode.insert
        else 14
    )


# keys
def test_keys(storage, alleles):
    key_list = storage.keys()
    for allele_id in alleles:
        assert allele_id in key_list


# __delitem__
def test_delitem(storage, alleles):
    for allele_id in alleles:
        del storage[allele_id]


# __setitem__
def test_setitem(storage, alleles):
    for allele in alleles.values():
        variation = allele["params"]
        definition = variation["definition"]
        translated_variation = VrsPythonTranslator().translate_variation(definition)
        vrs_enref(translated_variation, storage)
