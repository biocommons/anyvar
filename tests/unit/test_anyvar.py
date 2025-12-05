"""Test anyvar methods"""

from unittest.mock import Mock

from anyvar.utils.types import Annotation, AnnotationType


def test_create_timestamp_annotation_missing(anyvar_instance):
    """Test that create_timestamp_annotation_if_missing works correctly, if annotation is missing"""
    expected_annotation_id = 1
    object_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"

    anyvar_instance.get_object_annotations = Mock(return_value=[])
    anyvar_instance.put_annotation = Mock(return_value=expected_annotation_id)

    result = anyvar_instance.create_timestamp_annotation_if_missing(object_id)

    assert result == expected_annotation_id
    anyvar_instance.get_object_annotations.assert_called_once_with(
        object_id, AnnotationType.CREATION_TIMESTAMP
    )
    anyvar_instance.put_annotation.assert_called_once()


def test_create_timestamp_annotation_exists(anyvar_instance):
    """Test that create_timestamp_annotation_if_missing works correctly, if annotation exists"""
    object_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"

    anyvar_instance.get_object_annotations = Mock(
        return_value=[
            Annotation(
                object_id=object_id,
                annotation_type=AnnotationType.CREATION_TIMESTAMP,
                annotation_value="2025-12-04T14:13:41.521791+00:00",
            )
        ]
    )
    anyvar_instance.put_annotation = Mock(return_value=None)

    result = anyvar_instance.create_timestamp_annotation_if_missing(object_id)

    assert result is None
    anyvar_instance.put_annotation.assert_not_called()
