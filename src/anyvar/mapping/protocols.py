"""Provide a public interface to mapping models and functions"""

from typing import Protocol

from anyvar.core.objects import SupportedVrsVariation
from anyvar.mapping.projection_models import ProjectionResults
from anyvar.storage.base import Storage


class VariantProjectorProtocol(Protocol):
    """Protocol for variant projection across the central dogma."""

    def project_variations(  # noqa: D102
        self,
        variation: SupportedVrsVariation,
    ) -> ProjectionResults: ...


def project_and_register_variations(
    projector: VariantProjectorProtocol,
    storage: Storage,
    variation: SupportedVrsVariation,
) -> ProjectionResults:
    """Project a variant to other molecule types and store those variants + mappings.

    For genomic variants, projects to coding (TRANSCRIBE_TO) and protein
    (TRANSLATE_TO) representations using cool-seq-tool transcript selection
    with longest-compatible fallback. For transcript variants, projects
    directly to the associated protein.

    Note: I don't think this module is the best home for this function.

    :param projector: variant projector instance
    :param storage: Storage instance
    :param variation: variation to project
    :return: result class containing successfully-generated mappings as well as failures
    """
    projection_results = projector.project_variations(variation)
    storage.add_objects(
        [pr.destination_variation for pr in projection_results.projections]
    )
    for projection in projection_results.projections:
        storage.add_mapping(projection.mapping)
    return projection_results
