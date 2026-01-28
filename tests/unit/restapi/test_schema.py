from typing import get_args

import pytest

from anyvar.restapi.schema import SupportedVariationType
from anyvar.utils.funcs import camel_to_snake
from anyvar.utils.types import VrsVariation


@pytest.mark.ci_ok
def test_supported_object_type():
    for cls in get_args(VrsVariation):
        assert SupportedVariationType[camel_to_snake(cls.__name__)] == cls.__name__
    assert len(get_args(VrsVariation)) == len(SupportedVariationType)
