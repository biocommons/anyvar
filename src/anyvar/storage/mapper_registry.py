"""Central registry for all object mappers."""

from typing import TypeVar

from ga4gh.vrs import models as vrs_models

from anyvar.storage import db
from anyvar.storage.abc import VariationMapping

from .mappers import (
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
        self._mappers: dict[type, BaseMapper] = {
            db.Allele: AlleleMapper(),
            db.Location: SequenceLocationMapper(),
            db.SequenceReference: SequenceReferenceMapper(),
            db.VariationMapping: VariationMappingMapper(),
        }

    def get_mapper(self, entity_type: type[T]) -> BaseMapper:
        """Get mapper for the given entity type."""
        mapper = self._mappers.get(entity_type)
        if mapper is None:
            raise ValueError(f"No mapper registered for type: {entity_type}")
        return mapper

    def to_vrs_model(self, db_entity):  # noqa: ANN201, ANN001
        """Convert any DB entity to its corresponding VRS model."""
        mapper = self.get_mapper(type(db_entity))
        return mapper.to_vrs_model(db_entity)

    def to_db_entity(self, vrs_model):  # noqa: ANN201, ANN001
        """Convert any VRS model to its corresponding DB entity."""
        # Map VRS model types to DB entity types
        vrs_to_db_mapping = {
            vrs_models.Allele: db.Allele,
            vrs_models.SequenceLocation: db.Location,
            vrs_models.SequenceReference: db.SequenceReference,
            VariationMapping: db.VariationMapping,
        }

        db_type = vrs_to_db_mapping.get(type(vrs_model))
        if db_type is None:
            raise ValueError(
                f"No DB entity type mapped for VRS model: {type(vrs_model)}"
            )

        mapper = self.get_mapper(db_type)
        return mapper.to_db_entity(vrs_model)


# Global registry instance
mapper_registry = MapperRegistry()
