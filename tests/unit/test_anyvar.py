"""Test anyvar methods"""

from types import SimpleNamespace
from unittest.mock import Mock

from anyvar.anyvar import AnyVar, create_projector
from anyvar.core import metadata


def test_create_timestamp_missing(anyvar_instance: AnyVar):
    """Test that timestamp creation works correctly, if timestamp is missing"""
    expected_ext_id = 1
    object_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"

    anyvar_instance.get_object_extensions = Mock(return_value=[])
    anyvar_instance.put_extension = Mock(return_value=expected_ext_id)

    result = anyvar_instance.create_timestamp_if_missing(object_id)

    assert result == expected_ext_id
    anyvar_instance.get_object_extensions.assert_called_once_with(
        object_id, metadata.ExtensionName.CREATION_TIMESTAMP
    )
    anyvar_instance.put_extension.assert_called_once()


def test_create_timestamp_exists(anyvar_instance: AnyVar):
    """Test that create_timestamp_extension_if_missing works correctly, if extension exists"""
    object_id = "ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"

    anyvar_instance.get_object_extensions = Mock(
        return_value=[
            metadata.Extension(
                object_id=object_id,
                name=metadata.ExtensionName.CREATION_TIMESTAMP,
                value="2025-12-04T14:13:41.521791+00:00",
            )
        ]
    )
    anyvar_instance.put_extension = Mock(return_value=None)

    result = anyvar_instance.create_timestamp_if_missing(object_id)

    assert result is None
    anyvar_instance.put_extension.assert_not_called()


def test_create_projector_requires_literal_true(monkeypatch):
    """Projection is enabled only by setting ANYVAR_ENABLE_PROJECTION=true."""
    translator = SimpleNamespace(dp=SimpleNamespace())

    for value in ("1", "yes", "false", ""):
        monkeypatch.setenv("ANYVAR_ENABLE_PROJECTION", value)

        assert create_projector(translator) is None
