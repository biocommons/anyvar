"""Define data models for use in variant projection"""

from dataclasses import dataclass, field
from typing import TypeAlias

from ga4gh.vrs import models

from anyvar.core.metadata import VariationMapping
from anyvar.core.objects import SupportedVrsVariation


class ProjectionError(Exception):
    """Indicates a failure during variant projection."""


@dataclass(frozen=True)
class ProjectedVariation:
    """A projected variation and the mapping used to derive it.

    Instances are returned in dependency order so that each mapping's source
    variation is either the original input variation or a previously projected
    variation.
    """

    destination_variation: SupportedVrsVariation
    mapping: VariationMapping


@dataclass(frozen=True)
class ProjectionFailure:
    """Information describing a failed projection.

    Each failure records the destination molecule type that could not be
    produced along with the corresponding projection error.
    """

    source_id: str
    description: str
    destination_molecule_type: models.MoleculeType | None = None

    @classmethod
    def from_error(
        cls,
        source_id: str,
        error: ProjectionError,
        destination_molecule_type: models.MoleculeType | None = None,
    ) -> "ProjectionFailure":
        """Create from a projection error

        This class needs to pull messages out of exceptions to store them; otherwise,
        it's difficult/annoying to check equality (eg in tests)
        """
        return cls(
            source_id=source_id,
            description=str(error),
            destination_molecule_type=destination_molecule_type,
        )


@dataclass(frozen=True)
class ProjectionNotApplicable:
    """A projection that was not applicable to the input variation.

    Records the destination molecule type that could not meaningfully be
    produced and the reason projection was not attempted.
    """

    source_id: str
    reason: str
    destination_molecule_type: models.MoleculeType | None


ProjectionOutcome: TypeAlias = (
    ProjectedVariation | ProjectionFailure | ProjectionNotApplicable
)


@dataclass
class ProjectionResults:
    """The outcome of projecting a variation to other molecule types.

    Contains successful projections, expected projection failures, and
    projections that were not applicable to the input variation.

    We should try to be specific about what constitutes an error versus "not applicable":
    do we *know* there's no biological projection possible (ie an untranslated region)
    or were we simply unable to successfully resolve or calculate projected location
    or state? The latter should be a "failure", the former should be "not applicable"
    """

    projections: list[ProjectedVariation] = field(default_factory=list)
    failures: list[ProjectionFailure] = field(default_factory=list)
    not_applicable: list[ProjectionNotApplicable] = field(default_factory=list)

    @property
    def fully_succeeded(self) -> bool:
        """Return ``True`` if all attempted projections succeeded."""
        return not self.failures

    def add(self, outcome: ProjectionOutcome) -> None:
        """Add a single projection outcome to the appropriate collection."""
        match outcome:
            case ProjectedVariation():
                self.projections.append(outcome)
            case ProjectionFailure():
                self.failures.append(outcome)
            case ProjectionNotApplicable():
                self.not_applicable.append(outcome)
            case _:
                raise TypeError(
                    f"Unsupported projection outcome: {type(outcome).__name__}"
                )
