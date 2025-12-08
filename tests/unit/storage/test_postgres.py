"""Tests postgres storage implementation methods directly."""

import os

import pytest
from conftest import build_vrs_variant_from_dict
from ga4gh.vrs import models

from anyvar.storage.base_storage import (
    DataIntegrityError,
    IncompleteVrsObjectError,
    InvalidSearchParamsError,
)
from anyvar.storage.postgres import PostgresObjectStore
from anyvar.utils import types


@pytest.fixture(scope="session")
def postgres_uri():
    uri = os.environ.get(
        "ANYVAR_TEST_STORAGE_URI",
        "postgresql://postgres:postgres@localhost:5432/anyvar_test",
    )
    return uri


@pytest.fixture
def focus_alleles(alleles: dict) -> tuple[models.Allele, ...]:
    """A small subset of test alleles to use in more focused tests

    This is a tuple because many checks assume a specific order of these objects
    """
    return tuple(
        models.Allele.model_validate(build_vrs_variant_from_dict(a["variation"]))
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
        models.SequenceReference,
        [allele_38.location.sequenceReference.refgetAccession],
    )
    assert result == []


@pytest.mark.ci_ok
def test_db_batch_size(
    monkeypatch,
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    """Test that batch size works correctly"""
    postgres_storage.add_objects(focus_alleles)
    result = postgres_storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) > 1

    monkeypatch.setattr(type(postgres_storage), "BATCH_SIZE", 1)
    result = postgres_storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) == 1


@pytest.mark.ci_ok
def test_alleles_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad test coverage of CRUD methods for alleles"""
    postgres_storage.add_objects(focus_alleles)

    # get 1 allele
    result = postgres_storage.get_objects(models.Allele, [focus_alleles[0].id])
    assert result == [focus_alleles[0]]

    # get multiple alleles
    result = postgres_storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) == 2
    assert focus_alleles[1] in list(result)
    assert focus_alleles[2] in list(result)

    # get alleles, including some that don't exist
    result = postgres_storage.get_objects(
        models.Allele, ["ga4gh:VA.not_real", focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]
    result = postgres_storage.get_objects(models.Allele, ["ga4gh:VA.sdfljsdflk"])
    assert result == []

    # add empty allele
    _ = postgres_storage.add_objects([])

    # get contained objects
    result = postgres_storage.get_objects(
        models.SequenceLocation, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # delete objects
    postgres_storage.delete_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert postgres_storage.get_objects(models.Allele, [focus_alleles[1].id]) == []
    result = postgres_storage.get_objects(models.Allele, [focus_alleles[0].id])
    assert result == [focus_alleles[0]]
    postgres_storage.delete_objects(models.Allele, [focus_alleles[0].id])
    assert postgres_storage.get_objects(models.Allele, [focus_alleles[0].id]) == []

    # contained objects persist
    result = postgres_storage.get_objects(
        models.SequenceLocation, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # test that all allele fixtures load w/o issue
    postgres_storage.add_objects(validated_vrs_alleles.values())


@pytest.mark.ci_ok
def test_incomplete_objects_error(postgres_storage: PostgresObjectStore):
    # allele with IRI ref for location
    reffed_allele = models.Allele(
        id="ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        location=models.iriReference(root="ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I"),
        state=models.ReferenceLengthExpression(
            length=0, sequence=models.sequenceString(root=""), repeatSubunitLength=2
        ),
    )
    with pytest.raises(IncompleteVrsObjectError):
        postgres_storage.add_objects([reffed_allele])

    # allele missing ID
    idless_allele = models.Allele(
        location=models.SequenceLocation(
            id="ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
            sequenceReference=models.SequenceReference(
                refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"
            ),
            start=36561661,
            end=36561663,
        ),
        state=models.ReferenceLengthExpression(
            length=0, sequence=models.sequenceString(root=""), repeatSubunitLength=2
        ),
    )
    with pytest.raises(IncompleteVrsObjectError):
        postgres_storage.add_objects([idless_allele])

    # sequencelocation missing ID
    idless_sl = models.SequenceLocation(
        sequenceReference=models.SequenceReference(
            refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"
        ),
        start=36561661,
        end=36561663,
    )
    with pytest.raises(IncompleteVrsObjectError):
        postgres_storage.add_objects([idless_sl])

    # allele with sequencelocation missing ID
    allele_with_idless_sl = models.Allele(
        id="ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        digest="d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        location=models.SequenceLocation(
            sequenceReference=models.SequenceReference(
                refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"
            ),
            start=36561661,
            end=36561663,
        ),
        state=models.ReferenceLengthExpression(
            length=0, sequence=models.sequenceString(root=""), repeatSubunitLength=2
        ),
    )
    with pytest.raises(IncompleteVrsObjectError):
        postgres_storage.add_objects([allele_with_idless_sl])

    # allele missing digest
    digestless_allele = models.Allele(
        id="ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        location=models.SequenceLocation(
            id="ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
            sequenceReference=models.SequenceReference(
                refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"
            ),
            start=36561661,
            end=36561663,
        ),
        state=models.ReferenceLengthExpression(
            length=0, sequence=models.sequenceString(root=""), repeatSubunitLength=2
        ),
    )
    with pytest.raises(IncompleteVrsObjectError):
        postgres_storage.add_objects([digestless_allele])


@pytest.mark.ci_ok
def test_objects_raises_integrityerror(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    postgres_storage.add_objects(focus_alleles)
    with pytest.raises(DataIntegrityError):
        postgres_storage.delete_objects(
            models.SequenceReference,
            [focus_alleles[0].location.sequenceReference.refgetAccession],
        )


@pytest.mark.ci_ok
def test_sequencelocations_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    sls_to_add = [
        models.SequenceLocation.model_validate(a.location) for a in focus_alleles
    ]
    postgres_storage.add_objects(sls_to_add)

    # get SLs, including one with the wrong type/ID
    result = postgres_storage.get_objects(
        models.SequenceLocation,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sls_to_add[0].id,
        ],
    )
    assert result == [sls_to_add[0]]

    # delete objects, other objects still persist
    postgres_storage.delete_objects(models.SequenceLocation, [sls_to_add[2].id])
    result = postgres_storage.get_objects(models.SequenceLocation, [sls_to_add[2].id])
    assert result == []
    result = postgres_storage.get_objects(
        models.SequenceLocation, [sls_to_add[1].id, sls_to_add[0].id]
    )
    assert len(result) == 2
    assert sls_to_add[0] in result
    assert sls_to_add[1] in result

    # test that all sequencelocation fixtures load w/o issue
    all_sls = [a.location for a in validated_vrs_alleles.values()]
    postgres_storage.add_objects(all_sls)


@pytest.mark.ci_ok
def test_sequencereferences_crud(
    postgres_storage: PostgresObjectStore,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    sequence_references_to_add: list[models.SequenceReference] = [
        models.SequenceReference.model_validate(
            a.location.sequenceReference  # type: ignore
        )
        for a in focus_alleles
    ]
    postgres_storage.add_objects(sequence_references_to_add)

    # get SequenceReferences, including one with the wrong type/ID
    result = postgres_storage.get_objects(
        models.SequenceReference,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sequence_references_to_add[0].refgetAccession,
        ],
    )
    assert result == [sequence_references_to_add[0]]

    # delete objects, other objects still persist
    postgres_storage.delete_objects(
        models.SequenceReference,
        [sequence_references_to_add[2].refgetAccession],  # type: ignore
    )
    result = postgres_storage.get_objects(
        models.SequenceReference,
        [sequence_references_to_add[2].refgetAccession],  # type: ignore
    )
    assert result == []

    result = list(
        postgres_storage.get_objects(
            models.SequenceReference,
            [
                sequence_references_to_add[1].refgetAccession,
                sequence_references_to_add[0].refgetAccession,
            ],  # type: ignore
        )
    )
    assert len(result) == 2
    assert sequence_references_to_add[0] in result
    assert sequence_references_to_add[1] in result

    # test that all SequenceReferences fixtures load w/o issue
    all_sequence_references = [
        models.SequenceReference.model_validate(
            a.location.sequenceReference  # type: ignore
        )
        for a in validated_vrs_alleles.values()
    ]
    postgres_storage.add_objects(all_sequence_references)


@pytest.mark.ci_ok
def test_mappings_crud(
    postgres_storage: PostgresObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad coverage of CRUD methods for variation mappings"""
    # prepopulate
    allele_38 = validated_vrs_alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_37 = validated_vrs_alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
    allele_tx = validated_vrs_alleles["ga4gh:VA.VrGVDMrq3BCWHIopVxMDtVpMOrxjfQJC"]
    postgres_storage.add_objects([allele_38, allele_37, allele_tx])

    # add mapping
    liftover_mapping = types.VariationMapping(
        source_id=allele_38.id,
        dest_id=allele_37.id,
        mapping_type=types.VariationMappingType.LIFTOVER,
    )
    postgres_storage.add_mapping(liftover_mapping)
    tx_mapping = types.VariationMapping(
        source_id=allele_38.id,
        dest_id=allele_tx.id,
        mapping_type=types.VariationMappingType.TRANSCRIPTION,
    )
    postgres_storage.add_mapping(tx_mapping)

    # get mapping
    assert postgres_storage.get_mappings(
        allele_38.id, types.VariationMappingType.TRANSCRIPTION
    ) == [tx_mapping]
    assert postgres_storage.get_mappings(
        allele_38.id, types.VariationMappingType.LIFTOVER
    ) == [liftover_mapping]

    # redundant adds still work
    postgres_storage.add_mapping(liftover_mapping)
    assert postgres_storage.get_mappings(
        allele_38.id, types.VariationMappingType.LIFTOVER
    ) == [liftover_mapping]

    # type param optional
    get_result = postgres_storage.get_mappings(allele_38.id)
    assert len(get_result) == 2
    sorted(get_result, key=lambda a: a.mapping_type)
    assert get_result[0] == liftover_mapping
    assert get_result[1] == tx_mapping

    # delete mapping
    postgres_storage.delete_mapping(liftover_mapping)
    assert (
        postgres_storage.get_mappings(allele_38.id, types.VariationMappingType.LIFTOVER)
        == []
    )
    assert postgres_storage.get_mappings(allele_38.id) == [tx_mapping]
    postgres_storage.delete_mapping(tx_mapping)
    assert postgres_storage.get_mappings(allele_38.id) == []


@pytest.mark.ci_ok
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
    result = postgres_storage.get_annotations(focus_alleles[0].id, "classification")
    assert result == [ann1]

    result = postgres_storage.get_annotations(focus_alleles[2].id, "reference")
    assert result == [ann4]

    result = postgres_storage.get_annotations(focus_alleles[2].id)
    sorted(result, key=lambda i: (i.annotation_type, i.annotation_value))
    assert result == [ann3, ann4]

    # adding the same annotation multiple times creates redundant rows
    postgres_storage.add_annotation(ann4)
    result = postgres_storage.get_annotations(focus_alleles[2].id, "reference")
    assert result == [ann4, ann4]

    # test optional type
    assert postgres_storage.get_annotations(
        focus_alleles[0].id
    ) == postgres_storage.get_annotations(
        focus_alleles[0].id, annotation_type="classification"
    )

    # fetch nonexistent annotation
    result = postgres_storage.get_annotations("ga4gh:VA.ZZZZZZZ")
    assert result == []

    # delete annotations
    result = postgres_storage.get_annotations(focus_alleles[0].id, "classification")
    postgres_storage.delete_annotation(result[0])
    result = postgres_storage.get_annotations(focus_alleles[0].id, "classification")
    assert result == []


def test_search_alleles(
    postgres_storage: PostgresObjectStore,
    validated_vrs_alleles: dict[str, models.Allele],
):
    # these are on the same accession
    egfr_variant = validated_vrs_alleles["ga4gh:VA.jm5N6PIwuQ8H0rBZCqxOVMlZN7lGvCrX"]
    braf_variant = validated_vrs_alleles["ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe"]
    # this is on a different accession
    other_variant = validated_vrs_alleles["ga4gh:VA.J-gW7La8EblIdT1MfqZzhzbO26lkEH7D"]
    # some edge cases
    rle = validated_vrs_alleles["ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb"]
    long_ins = validated_vrs_alleles["ga4gh:VA.uR23Z7AAFaLHhPUymUEYNG4o2CCE560T"]
    rle_del = validated_vrs_alleles["ga4gh:VA.pc65jiqYvcLLocEPb3msu216eBQ3R-mr"]
    postgres_storage.add_objects(
        [egfr_variant, braf_variant, other_variant, rle, long_ins, rle_del]
    )

    # result fully contained in interval
    result = postgres_storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561660, 36561665
    )
    assert result == [rle]
    result = postgres_storage.search_alleles(
        egfr_variant.location.sequenceReference.refgetAccession, 55174010, 140753340
    )
    sorted(result, key=lambda a: a.id)
    assert result == [egfr_variant, braf_variant]

    # result partially overlaps with interval
    result = postgres_storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561662, 36561665
    )
    assert result == [rle]
    assert postgres_storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561662, 36561663
    ) == [rle]

    # position ranges are inclusive
    result = postgres_storage.search_alleles(
        braf_variant.location.sequenceReference.refgetAccession, 140753335, 140753336
    )
    assert result == [braf_variant]

    # handle unrecognized accession
    assert postgres_storage.search_alleles("SQ.unknown-sequence", 1, 10) == []

    # handle invalid params
    with pytest.raises(InvalidSearchParamsError):
        postgres_storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, -1, 36561665
        )

    with pytest.raises(InvalidSearchParamsError):
        postgres_storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, -5, -1
        )
    with pytest.raises(InvalidSearchParamsError):
        postgres_storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, 10, 9
        )

    # intervals adjacent to, but not within sequence location of, larger indels/RLEs
    assert (
        postgres_storage.search_alleles(
            long_ins.location.sequenceReference.refgetAccession, 10599292, 10599295
        )
        == []
    )
    assert (
        postgres_storage.search_alleles(
            rle_del.location.sequenceReference.refgetAccession, 905, 910
        )
        == []
    )
    assert postgres_storage.search_alleles(
        rle_del.location.sequenceReference.refgetAccession, 904, 910
    ) == [rle_del]
