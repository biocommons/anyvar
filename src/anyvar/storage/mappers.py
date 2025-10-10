"""Object mappers for converting between VRS models and database entities."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from ga4gh.vrs import models as vrs_models

from anyvar.storage import orm
from anyvar.utils import types

A = TypeVar("A")  # Anyvar entity type
D = TypeVar("D")  # DB entity type


class BaseMapper(Generic[A, D], ABC):
    """Base class for all object mappers."""

    @abstractmethod
    def from_db_entity(self, db_entity: D) -> A:
        """Convert DB entity to VRS model."""

    @abstractmethod
    def to_db_entity(self, anyvar_entity: A) -> D:
        """Convert VRS model to DB entity."""


class SequenceReferenceMapper(
    BaseMapper[vrs_models.SequenceReference, orm.SequenceReference]
):
    """Maps between orm.SequenceReference entities."""

    def from_db_entity(
        self, db_entity: orm.SequenceReference
    ) -> vrs_models.SequenceReference:
        """Convert DB orm.SequenceReference to VRS orm.SequenceReference."""
        return vrs_models.SequenceReference(
            type="SequenceReference",
            refgetAccession=db_entity.id,
            moleculeType=db_entity.molecule_type,
        )

    def to_db_entity(
        self, anyvar_entity: vrs_models.SequenceReference
    ) -> orm.SequenceReference:
        """Convert VRS orm.SequenceReference to DB orm.SequenceReference."""
        return orm.SequenceReference(
            id=anyvar_entity.refgetAccession,  # Use refgetAccession as primary key
            molecule_type=anyvar_entity.moleculeType,
        )


class SequenceLocationMapper(BaseMapper[vrs_models.SequenceLocation, orm.Location]):
    """Maps between SequenceLocation entities."""

    def __init__(self) -> None:
        """Initialize SequenceLocationMapper."""
        self.seq_ref_mapper = SequenceReferenceMapper()

    def from_db_entity(self, db_entity: orm.Location) -> vrs_models.SequenceLocation:
        """Convert DB orm.Location to VRS SequenceLocation."""
        # Handle range vs simple coordinates
        start = self._resolve_coordinate_from_db(
            simple=db_entity.start,
            start=db_entity.start_outer,
            end=db_entity.start_inner,
        )
        end = self._resolve_coordinate_from_db(
            simple=db_entity.end, start=db_entity.end_outer, end=db_entity.end_inner
        )

        return vrs_models.SequenceLocation(
            id=db_entity.id,
            digest=db_entity.digest,
            type="SequenceLocation",
            sequenceReference=self.seq_ref_mapper.from_db_entity(
                db_entity.sequence_reference
            ),
            start=start,
            end=end,
        )

    def to_db_entity(self, anyvar_entity: vrs_models.SequenceLocation) -> orm.Location:
        """Convert VRS SequenceLocation to DB orm.Location."""
        # Convert VRS int/Range coordinates to DB fields
        start_simple, start_outer, start_inner = self._resolve_coordinate_to_db(
            anyvar_entity.start
        )
        end_simple, end_outer, end_inner = self._resolve_coordinate_to_db(
            anyvar_entity.end
        )

        # Construct orm.Location and delegate to orm.SequenceReference mapper
        return orm.Location(
            id=anyvar_entity.id,
            digest=anyvar_entity.digest,
            sequence_reference_id=anyvar_entity.sequenceReference.refgetAccession,
            sequence_reference=self.seq_ref_mapper.to_db_entity(
                anyvar_entity.sequenceReference
            ),
            start=start_simple,
            end=end_simple,
            start_outer=start_outer,
            start_inner=start_inner,
            end_outer=end_outer,
            end_inner=end_inner,
        )

    def _resolve_coordinate_from_db(
        self, simple: int | None, start: int | None, end: int | None
    ) -> int | vrs_models.Range | None:
        """Resolve coordinate from DB fields to VRS format."""
        if simple is not None:
            return simple
        if start is not None and end is not None:
            return vrs_models.Range([start, end])
        return None

    def _resolve_coordinate_to_db(
        self, coordinate: int | vrs_models.Range | None
    ) -> tuple[int | None, int | None, int | None]:
        """Resolve VRS coordinate to DB fields."""
        if coordinate is None:
            return None, None, None
        if isinstance(coordinate, vrs_models.Range):
            return None, coordinate.root[0], coordinate.root[1]
        if isinstance(coordinate, int):
            return coordinate, None, None
        return None, None, None


class AlleleMapper(BaseMapper[vrs_models.Allele, orm.Allele]):
    """Maps between orm.Allele entities."""

    def __init__(self) -> None:
        """Initialize AlleleMapper."""
        self.location_mapper = SequenceLocationMapper()

    def from_db_entity(self, db_entity: orm.Allele) -> vrs_models.Allele:
        """Convert DB orm.Allele to VRS orm.Allele."""
        # Reconstruct state from JSONB
        state = self._reconstruct_state(db_entity.state)

        # Construct orm.Allele and delegate to orm.Location mapper
        return vrs_models.Allele(
            id=db_entity.id,
            digest=db_entity.digest,
            type="Allele",
            location=self.location_mapper.from_db_entity(db_entity.location),
            state=state,
        )

    def to_db_entity(self, anyvar_entity: vrs_models.Allele) -> orm.Allele:
        """Convert VRS orm.Allele to DB orm.Allele."""
        # Ensure IDs are computed if not present
        if not anyvar_entity.id:
            # TODO implement here and for other objects, maybe further up the stack
            raise NotImplementedError("Auto ID generation not implemented yet")

        # Validate required nested objects
        if not anyvar_entity.location or not anyvar_entity.location.sequenceReference:
            raise ValueError("orm.Allele requires valid location and sequenceReference")

        # Serialize state
        state_dict = anyvar_entity.state.model_dump(exclude_none=True)

        return orm.Allele(
            id=anyvar_entity.id,
            digest=anyvar_entity.digest,
            location_id=anyvar_entity.location.id,
            location=self.location_mapper.to_db_entity(anyvar_entity.location),
            state=state_dict,
        )

    def _reconstruct_state(
        self, state_data: dict
    ) -> (
        vrs_models.LiteralSequenceExpression
        | vrs_models.ReferenceLengthExpression
        | vrs_models.LengthExpression
    ):
        """Reconstruct state object from JSONB data."""
        state_type = state_data.get("type")

        if state_type == "LiteralSequenceExpression":
            return vrs_models.LiteralSequenceExpression(**state_data)
        if state_type == "ReferenceLengthExpression":
            return vrs_models.ReferenceLengthExpression(**state_data)
        if state_type == "LengthExpression":
            return vrs_models.LengthExpression(**state_data)
        raise ValueError(f"Unknown state type '{state_type}' from: {state_data}")


class VariationMappingMapper(BaseMapper[types.VariationMapping, orm.VariationMapping]):
    """Maps between VariationMapping entities."""

    def from_db_entity(self, db_entity: orm.VariationMapping) -> types.VariationMapping:
        """Convert DB instance into business logic object"""
        mapping_type = types.VariationMappingType(db_entity.mapping_type)
        return types.VariationMapping(
            source_id=db_entity.source_id,
            dest_id=db_entity.dest_id,
            mapping_type=mapping_type,
        )

    def to_db_entity(self, vrs_model: types.VariationMapping) -> orm.VariationMapping:
        """Convert VariationMapping object to DB mapping instance."""
        return orm.VariationMapping(
            source_id=vrs_model.source_id,
            dest_id=vrs_model.dest_id,
            mapping_type=vrs_model.mapping_type,
        )


class AnnotationMapper(BaseMapper[types.Annotation, orm.Annotation]):
    """Maps between Annotations entities."""

    def from_db_entity(self, db_entity: orm.Annotation) -> types.Annotation:
        """Convert DB orm.SequenceReference to VRS orm.SequenceReference.

        :param db_entity: An ORM model orm.Annotation instance
        :return: An Anyvar orm.Annotation instance
        """
        return types.Annotation(
            object_id=db_entity.object_id,
            annotation_type=db_entity.annotation_type,
            annotation_value=db_entity.annotation_value,
            id=db_entity.id,
        )

    def to_db_entity(self, anyvar_entity: types.Annotation) -> orm.Annotation:
        """Convert VRS orm.SequenceReference to DB orm.SequenceReference.

        :param anyvar_entity: An Anyvar orm.Annotation instance
        :return: An ORM model orm.Annotation instance
        """
        return orm.Annotation(**anyvar_entity.model_dump())
