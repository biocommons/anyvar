from typing import get_args

import pytest

from anyvar.core.objects import VrsVariation
from anyvar.core.string import camel_to_snake
from anyvar.restapi.schema import SupportedVariationType


@pytest.mark.ci_ok
def test_supported_object_type():
    for cls in get_args(VrsVariation):
        assert SupportedVariationType[camel_to_snake(cls.__name__)] == cls.__name__
    assert len(get_args(VrsVariation)) == len(SupportedVariationType)
