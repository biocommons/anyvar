from typing import get_args

import pytest

from anyvar.core.objects import VrsVariation
from anyvar.restapi.schema import SupportedVariationType
from anyvar.storage.orm import _camel_to_snake


@pytest.mark.ci_ok
def test_supported_object_type():
    for cls in get_args(VrsVariation):
        assert SupportedVariationType[_camel_to_snake(cls.__name__)] == cls.__name__
    assert len(get_args(VrsVariation)) == len(SupportedVariationType)
