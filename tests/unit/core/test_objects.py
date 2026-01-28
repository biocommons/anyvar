from typing import get_args

import pytest

from anyvar.core.objects import SupportedObjectType, VrsObject
from anyvar.core.string import camel_to_snake


@pytest.mark.ci_ok
def test_supported_object_type():
    for cls in get_args(VrsObject):
        assert SupportedObjectType[camel_to_snake(cls.__name__)] == cls.__name__
    assert len(get_args(VrsObject)) == len(SupportedObjectType)
