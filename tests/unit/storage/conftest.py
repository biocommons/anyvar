from collections.abc import Callable

import pytest
from ga4gh.vrs import models


@pytest.fixture
def focus_alleles(
    alleles: dict, build_vrs_variant_from_dict_function: Callable[[dict], models.Allele]
) -> tuple[models.Allele, ...]:
    """A small subset of test alleles to use in more focused tests

    This is a tuple because many checks assume a specific order of these objects
    """
    return tuple(
        models.Allele.model_validate(
            build_vrs_variant_from_dict_function(a["variation"])
        )
        for a in (
            alleles["ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"],
            alleles["ga4gh:VA.rQBlRht2jfsSp6TpX3xhraxtmgXNKvQf"],
            alleles["ga4gh:VA.1FzYrqG-7jB3Wr46eIL_L5BWElQZEB7i"],
        )
    )


@pytest.fixture
def validated_vrs_alleles(
    alleles: dict, build_vrs_variant_from_dict_function: Callable[[dict], models.Allele]
) -> dict[str, models.Allele]:
    """All allele fixtures, transformed into VRS Pydantic models w/ other test metadata removed"""
    return {
        k: build_vrs_variant_from_dict_function(v["variation"])
        for k, v in alleles.items()
    }
