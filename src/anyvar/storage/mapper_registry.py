"""Central registry for all object mappers."""

from typing import TypeVar

from ga4gh.vrs import models as vrs_models

from anyvar.storage import orm
from anyvar.storage.mappers import (
    AlleleMapper,
    AnnotationMapper,
    BaseMapper,
    SequenceLocationMapper,
    SequenceReferenceMapper,
    VariationMappingMapper,
)
from anyvar.utils import types

T = TypeVar("T")


class MapperRegistry:
    """Central registry for all object mappers."""

    def __init__(self) -> None:
        """Initialize the MapperRegistry with known mappers."""
        self.anyvar_to_db_mapping = {
            vrs_models.Allele: orm.Allele,
            vrs_models.SequenceLocation: orm.Location,
            vrs_models.SequenceReference: orm.SequenceReference,
            types.VariationMapping: orm.VariationMapping,
            types.Annotation: orm.Annotation,
        }

        self._mappers: dict[type, BaseMapper] = {
            orm.Allele: AlleleMapper(),
            orm.Location: SequenceLocationMapper(),
            orm.SequenceReference: SequenceReferenceMapper(),
            orm.VariationMapping: VariationMappingMapper(),
            orm.Annotation: AnnotationMapper(),
        }

    def get_mapper(self, entity_type: type[T]) -> BaseMapper:
        """Get mapper for the given entity type."""
        mapper = self._mappers.get(entity_type)
        if mapper is None:
            raise ValueError(f"No mapper registered for type: {entity_type}")
        return mapper

    def from_db_entity(self, db_entity):  # noqa: ANN201, ANN001
        """Convert any DB entity to its corresponding VRS model."""
        mapper = self.get_mapper(type(db_entity))
        return mapper.from_db_entity(db_entity)

    def to_db_entity(self, anyvar_entity) -> orm.Base:  # noqa: ANN001
        """Convert any VRS model to its corresponding DB entity."""
        # Map VRS model types to DB entity types

        db_type = self.anyvar_to_db_mapping.get(type(anyvar_entity))
        if db_type is None:
            raise ValueError(
                f"No DB entity type mapped for VRS model: {type(anyvar_entity)}"
            )

        mapper = self.get_mapper(db_type)
        return mapper.to_db_entity(anyvar_entity)


# Global registry instance
mapper_registry = MapperRegistry()
