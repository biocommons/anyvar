"""Central registry for all object mappers."""

from typing import TypeVar

from ga4gh.vrs import models as vrs_models

from anyvar.storage import orm
from anyvar.storage.base_storage import VariationMapping
from anyvar.storage.mappers import (
    AlleleMapper,
    BaseMapper,
    SequenceLocationMapper,
    SequenceReferenceMapper,
    VariationMappingMapper,
)

T = TypeVar("T")


class MapperRegistry:
    """Central registry for all object mappers."""

    def __init__(self) -> None:
        """Initialize the MapperRegistry with known mappers."""
        self.vrs_to_db_mapping = {
            vrs_models.Allele: orm.Allele,
            vrs_models.SequenceLocation: orm.Location,
            vrs_models.SequenceReference: orm.SequenceReference,
            VariationMapping: orm.VariationMapping,
        }

        self._mappers: dict[type, BaseMapper] = {
            orm.Allele: AlleleMapper(),
            orm.Location: SequenceLocationMapper(),
            orm.SequenceReference: SequenceReferenceMapper(),
            orm.VariationMapping: VariationMappingMapper,
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

    def to_db_entity(self, vrs_model):  # noqa: ANN201, ANN001
        """Convert any VRS model to its corresponding DB entity."""
        # Map VRS model types to DB entity types

        db_type = self.vrs_to_db_mapping.get(type(vrs_model))
        if db_type is None:
            raise ValueError(
                f"No DB entity type mapped for VRS model: {type(vrs_model)}"
            )

        mapper = self.get_mapper(db_type)
        return mapper.to_db_entity(vrs_model)


# Global registry instance
mapper_registry = MapperRegistry()
