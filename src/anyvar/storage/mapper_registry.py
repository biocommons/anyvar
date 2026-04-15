"""Central registry for all object mappers."""

from typing import TypeVar, overload

from ga4gh.vrs import models as vrs_models

from anyvar.core import metadata
from anyvar.storage import orm
from anyvar.storage.mappers import (
    AlleleMapper,
    AnnotationMapper,
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
        self.anyvar_to_db_mapping = {
            vrs_models.Allele: orm.Allele,
            vrs_models.SequenceLocation: orm.Location,
            vrs_models.SequenceReference: orm.SequenceReference,
            metadata.VariationMapping: orm.VariationMapping,
            metadata.Annotation: orm.Annotation,
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

    @overload
    def from_db_entity(self, db_entity: orm.Allele) -> vrs_models.Allele: ...

    @overload
    def from_db_entity(
        self, db_entity: orm.Location
    ) -> vrs_models.SequenceLocation: ...

    @overload
    def from_db_entity(
        self, db_entity: orm.SequenceReference
    ) -> vrs_models.SequenceReference: ...

    @overload
    def from_db_entity(
        self, db_entity: orm.VariationMapping
    ) -> metadata.VariationMapping: ...

    @overload
    def from_db_entity(self, db_entity: orm.Annotation) -> metadata.Annotation: ...

    def from_db_entity(
        self,
        db_entity: (
            orm.Allele
            | orm.Location
            | orm.SequenceReference
            | orm.VariationMapping
            | orm.Annotation
        ),
    ):
        """Convert any DB entity to its corresponding VRS model."""
        mapper = self.get_mapper(type(db_entity))
        return mapper.from_db_entity(db_entity)

    @overload
    def to_db_entity(self, anyvar_entity: vrs_models.Allele) -> orm.Allele: ...

    @overload
    def to_db_entity(
        self, anyvar_entity: vrs_models.SequenceLocation
    ) -> orm.Location: ...

    @overload
    def to_db_entity(
        self, anyvar_entity: vrs_models.SequenceReference
    ) -> orm.SequenceReference: ...

    @overload
    def to_db_entity(
        self, anyvar_entity: metadata.VariationMapping
    ) -> orm.VariationMapping: ...

    @overload
    def to_db_entity(self, anyvar_entity: metadata.Annotation) -> orm.Annotation: ...

    def to_db_entity(
        self,
        anyvar_entity: (
            vrs_models.Allele
            | vrs_models.SequenceLocation
            | vrs_models.SequenceReference
            | metadata.VariationMapping
            | metadata.Annotation
        ),
    ) -> orm.Base:
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
