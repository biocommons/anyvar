"""Functions to run common storage tests on different storage backends."""

import pytest
from ga4gh.vrs import models

from anyvar.storage.base_storage import (
    DataIntegrityError,
    IncompleteVrsObjectError,
    InvalidSearchParamsError,
    Storage,
)
from anyvar.utils import types


def run_db_lifecycle(storage: Storage, validated_vrs_alleles: dict[str, models.Allele]):
    # set up and populate DB
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


def run_query_max_rows(
    monkeypatch,
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    """Test that storage class has cap on # of rows that can be returned.

    This should be altered/maybe removed by issue #295
    """
    storage.add_objects(focus_alleles)
    result = storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) > 1

    monkeypatch.setattr(type(storage), "MAX_ROWS", 1)
    result = storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) == 1


def run_alleles_crud(
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad test coverage of CRUD methods for alleles"""
    storage.add_objects(focus_alleles)

    # get 1 allele
    result = storage.get_objects(models.Allele, [focus_alleles[0].id])
    assert result == [focus_alleles[0]]

    # get multiple alleles
    result = storage.get_objects(
        models.Allele, [focus_alleles[1].id, focus_alleles[2].id]
    )
    assert len(list(result)) == 2
    assert focus_alleles[1] in list(result)
    assert focus_alleles[2] in list(result)

    # get alleles, including some that don't exist
    result = storage.get_objects(
        models.Allele, ["ga4gh:VA.not_real", focus_alleles[0].id]
    )
    assert result == [focus_alleles[0]]
    result = storage.get_objects(models.Allele, ["ga4gh:VA.sdfljsdflk"])
    assert result == []

    # add empty allele
    _ = storage.add_objects([])

    # get contained objects
    result = storage.get_objects(
        models.SequenceLocation, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # delete objects
    storage.delete_objects(models.Allele, [focus_alleles[1].id, focus_alleles[2].id])
    assert storage.get_objects(models.Allele, [focus_alleles[1].id]) == []
    result = storage.get_objects(models.Allele, [focus_alleles[0].id])
    assert result == [focus_alleles[0]]
    storage.delete_objects(models.Allele, [focus_alleles[0].id])
    assert storage.get_objects(models.Allele, [focus_alleles[0].id]) == []

    # contained objects persist
    result = storage.get_objects(
        models.SequenceLocation, [focus_alleles[0].location.id]
    )
    assert result == [focus_alleles[0].location]

    # test that all allele fixtures load w/o issue
    storage.add_objects(validated_vrs_alleles.values())


def run_incomplete_objects_error(storage: Storage):
    # allele with IRI ref for location
    reffed_allele = models.Allele(
        id="ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
        location=models.iriReference(root="ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I"),
        state=models.ReferenceLengthExpression(
            length=0, sequence=models.sequenceString(root=""), repeatSubunitLength=2
        ),
    )
    with pytest.raises(IncompleteVrsObjectError):
        storage.add_objects([reffed_allele])

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
        storage.add_objects([idless_allele])

    # sequencelocation missing ID
    idless_sl = models.SequenceLocation(
        sequenceReference=models.SequenceReference(
            refgetAccession="SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86"
        ),
        start=36561661,
        end=36561663,
    )
    with pytest.raises(IncompleteVrsObjectError):
        storage.add_objects([idless_sl])

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
        storage.add_objects([allele_with_idless_sl])

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
        storage.add_objects([digestless_allele])


def run_objects_raises_integrityerror(
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    storage.add_objects(focus_alleles)
    with pytest.raises(DataIntegrityError):
        storage.delete_objects(
            models.SequenceReference,
            [focus_alleles[0].location.sequenceReference.refgetAccession],
        )


def run_sequencelocations_crud(
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    sls_to_add = [
        models.SequenceLocation.model_validate(a.location) for a in focus_alleles
    ]
    storage.add_objects(sls_to_add)

    # get SLs, including one with the wrong type/ID
    result = storage.get_objects(
        models.SequenceLocation,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sls_to_add[0].id,
        ],
    )
    assert result == [sls_to_add[0]]

    # delete objects, other objects still persist
    storage.delete_objects(models.SequenceLocation, [sls_to_add[2].id])
    result = storage.get_objects(models.SequenceLocation, [sls_to_add[2].id])
    assert result == []
    result = storage.get_objects(
        models.SequenceLocation, [sls_to_add[1].id, sls_to_add[0].id]
    )
    assert len(result) == 2
    assert sls_to_add[0] in result
    assert sls_to_add[1] in result

    # test that all sequencelocation fixtures load w/o issue
    all_sls = [a.location for a in validated_vrs_alleles.values()]
    storage.add_objects(all_sls)


def run_sequencereferences_crud(
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
    validated_vrs_alleles: dict[str, models.Allele],
):
    sequence_references_to_add: list[models.SequenceReference] = [
        models.SequenceReference.model_validate(
            a.location.sequenceReference  # type: ignore
        )
        for a in focus_alleles
    ]
    storage.add_objects(sequence_references_to_add)

    # get SequenceReferences, including one with the wrong type/ID
    result = storage.get_objects(
        models.SequenceReference,
        [
            "ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i",
            sequence_references_to_add[0].refgetAccession,
        ],
    )
    assert result == [sequence_references_to_add[0]]

    # delete objects, other objects still persist
    storage.delete_objects(
        models.SequenceReference,
        [sequence_references_to_add[2].refgetAccession],  # type: ignore
    )
    result = storage.get_objects(
        models.SequenceReference,
        [sequence_references_to_add[2].refgetAccession],  # type: ignore
    )
    assert result == []

    result = list(
        storage.get_objects(
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
    storage.add_objects(all_sequence_references)


def run_mappings_crud(
    storage: Storage,
    validated_vrs_alleles: dict[str, models.Allele],
):
    """Broad coverage of CRUD methods for variation mappings"""
    # prepopulate
    allele_38 = validated_vrs_alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"]
    allele_37 = validated_vrs_alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"]
    allele_tx = validated_vrs_alleles["ga4gh:VA.VrGVDMrq3BCWHIopVxMDtVpMOrxjfQJC"]
    storage.add_objects([allele_38, allele_37, allele_tx])

    # add mapping
    liftover_mapping = types.VariationMapping(
        source_id=allele_38.id,
        dest_id=allele_37.id,
        mapping_type=types.VariationMappingType.LIFTOVER,
    )
    storage.add_mapping(liftover_mapping)
    tx_mapping = types.VariationMapping(
        source_id=allele_38.id,
        dest_id=allele_tx.id,
        mapping_type=types.VariationMappingType.TRANSCRIPTION,
    )
    storage.add_mapping(tx_mapping)

    # get mapping
    assert storage.get_mappings(
        allele_38.id, types.VariationMappingType.TRANSCRIPTION
    ) == [tx_mapping]
    assert storage.get_mappings(allele_38.id, types.VariationMappingType.LIFTOVER) == [
        liftover_mapping
    ]

    # redundant adds still work
    storage.add_mapping(liftover_mapping)
    assert storage.get_mappings(allele_38.id, types.VariationMappingType.LIFTOVER) == [
        liftover_mapping
    ]

    # type param optional
    get_result = storage.get_mappings(allele_38.id)
    assert len(get_result) == 2
    sorted(get_result, key=lambda a: a.mapping_type)
    assert get_result[0] == liftover_mapping
    assert get_result[1] == tx_mapping

    # delete mapping
    storage.delete_mapping(liftover_mapping)
    assert storage.get_mappings(allele_38.id, types.VariationMappingType.LIFTOVER) == []
    assert storage.get_mappings(allele_38.id) == [tx_mapping]
    storage.delete_mapping(tx_mapping)
    assert storage.get_mappings(allele_38.id) == []


def run_annotations_crud(
    storage: Storage,
    focus_alleles: tuple[models.Allele, models.Allele, models.Allele],
):
    """Broad coverage of CRUD methods for annotations"""
    # prepopulate
    storage.add_objects(focus_alleles)

    # add arbitrary annotations
    ann1 = types.Annotation(
        object_id=focus_alleles[0].id,
        annotation_type="classification",
        annotation_value="pathogenic",
    )
    storage.add_annotation(ann1)
    ann2 = types.Annotation(
        object_id=focus_alleles[1].id,
        annotation_type="sample_count",
        annotation_value=5,
    )
    storage.add_annotation(ann2)
    ann3 = types.Annotation(
        object_id=focus_alleles[2].id,
        annotation_type="classification",
        annotation_value="likely_benign",
    )
    storage.add_annotation(ann3)
    ann4 = types.Annotation(
        object_id=focus_alleles[2].id,
        annotation_type="reference",
        annotation_value={"type": "article", "value": "pmid:123456"},
    )
    storage.add_annotation(ann4)

    # get annotations back
    result = storage.get_annotations(focus_alleles[0].id, "classification")
    assert result == [ann1]

    result = storage.get_annotations(focus_alleles[2].id, "reference")
    assert result == [ann4]

    result = storage.get_annotations(focus_alleles[2].id)
    sorted(result, key=lambda i: (i.annotation_type, i.annotation_value))
    assert result == [ann3, ann4]

    # adding the same annotation multiple times creates redundant rows
    storage.add_annotation(ann4)
    result = storage.get_annotations(focus_alleles[2].id, "reference")
    assert result == [ann4, ann4]

    # test optional type
    assert storage.get_annotations(focus_alleles[0].id) == storage.get_annotations(
        focus_alleles[0].id, annotation_type="classification"
    )

    # fetch nonexistent annotation
    result = storage.get_annotations("ga4gh:VA.ZZZZZZZ")
    assert result == []

    # delete annotations
    result = storage.get_annotations(focus_alleles[0].id, "classification")
    storage.delete_annotation(result[0])
    result = storage.get_annotations(focus_alleles[0].id, "classification")
    assert result == []


def run_search_alleles(
    storage: Storage,
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
    storage.add_objects(
        [egfr_variant, braf_variant, other_variant, rle, long_ins, rle_del]
    )

    # result fully contained in interval
    result = storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561660, 36561665
    )
    assert result == [rle]
    result = storage.search_alleles(
        egfr_variant.location.sequenceReference.refgetAccession, 55174010, 140753340
    )
    sorted(result, key=lambda a: a.id)
    assert result == [egfr_variant, braf_variant]

    # result partially overlaps with interval
    result = storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561662, 36561665
    )
    assert result == [rle]
    assert storage.search_alleles(
        rle.location.sequenceReference.refgetAccession, 36561662, 36561663
    ) == [rle]

    # position ranges are inclusive
    result = storage.search_alleles(
        braf_variant.location.sequenceReference.refgetAccession, 140753335, 140753336
    )
    assert result == [braf_variant]

    # handle unrecognized accession
    assert storage.search_alleles("SQ.unknown-sequence", 1, 10) == []

    # handle invalid params
    with pytest.raises(InvalidSearchParamsError):
        storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, -1, 36561665
        )

    with pytest.raises(InvalidSearchParamsError):
        storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, -5, -1
        )
    with pytest.raises(InvalidSearchParamsError):
        storage.search_alleles(
            braf_variant.location.sequenceReference.refgetAccession, 10, 9
        )

    # intervals adjacent to, but not within sequence location of, larger indels/RLEs
    assert (
        storage.search_alleles(
            long_ins.location.sequenceReference.refgetAccession, 10599292, 10599295
        )
        == []
    )
    assert (
        storage.search_alleles(
            rle_del.location.sequenceReference.refgetAccession, 905, 910
        )
        == []
    )
    assert storage.search_alleles(
        rle_del.location.sequenceReference.refgetAccession, 904, 910
    ) == [rle_del]
