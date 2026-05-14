from typing import get_args

import pytest

from anyvar.core.objects import SupportedVrsVariation
from anyvar.restapi.schema import SupportedVariationType
from anyvar.storage.orm import _camel_to_snake


@pytest.mark.ci_ok
def test_supported_object_type():
    supported_variation_classes = get_args(SupportedVrsVariation) or (
        SupportedVrsVariation,
    )

    for cls in supported_variation_classes:
        assert SupportedVariationType[_camel_to_snake(cls.__name__)] == cls.__name__
    assert len(supported_variation_classes) == len(SupportedVariationType)
