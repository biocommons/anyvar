"""Object mappers for converting between VRS models and database entities."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from ga4gh.vrs import models as vrs_models

from anyvar.storage import db

V = TypeVar("V")  # VRS model type
A = TypeVar("A")  # AnyVar DB entity type


class BaseMapper(Generic[V, A], ABC):
    """Base class for all object mappers."""

    @abstractmethod
    def to_vrs_model(self, db_entity: A) -> V:
        """Convert DB entity to VRS model."""

    @abstractmethod
    def to_db_entity(self, vrs_model: V) -> A:
        """Convert VRS model to DB entity."""


class SequenceReferenceMapper(
    BaseMapper[vrs_models.SequenceReference, db.SequenceReference]
):
    """Maps between SequenceReference entities."""

    def to_vrs_model(
        self, db_entity: db.SequenceReference
    ) -> vrs_models.SequenceReference:
        """Convert DB SequenceReference to VRS SequenceReference."""
        return vrs_models.SequenceReference(
            type="SequenceReference",
            refgetAccession=db_entity.refseq_id,
            moleculeType=db_entity.molecule_type,
        )

    def to_db_entity(
        self, vrs_model: vrs_models.SequenceReference
    ) -> db.SequenceReference:
        """Convert VRS SequenceReference to DB SequenceReference."""
        return db.SequenceReference(
            id=vrs_model.refgetAccession,  # Use refgetAccession as primary key
            refseq_id=vrs_model.refgetAccession,
            molecule_type=vrs_model.moleculeType,
        )


class SequenceLocationMapper(BaseMapper[vrs_models.SequenceLocation, db.Location]):
    """Maps between SequenceLocation entities."""

    def __init__(self) -> None:
        """Initialize SequenceLocationMapper."""
        self.seq_ref_mapper = SequenceReferenceMapper()

    def to_vrs_model(self, db_entity: db.Location) -> vrs_models.SequenceLocation:
        """Convert DB Location to VRS SequenceLocation."""
        # Handle range vs simple coordinates
        start = self._resolve_coordinate_from_db(
            db_entity.start, db_entity.start_outer, db_entity.start_inner
        )
        end = self._resolve_coordinate_from_db(
            db_entity.end, db_entity.end_outer, db_entity.end_inner
        )

        return vrs_models.SequenceLocation(
            id=db_entity.id,
            type="SequenceLocation",
            sequenceReference=self.seq_ref_mapper.to_vrs_model(
                db_entity.sequence_reference
            ),
            start=start,
            end=end,
        )

    def to_db_entity(self, vrs_model: vrs_models.SequenceLocation) -> db.Location:
        """Convert VRS SequenceLocation to DB Location."""
        # Convert VRS int/Range coordinates to DB fields
        start_simple, start_outer, start_inner = self._resolve_coordinate_to_db(
            vrs_model.start
        )
        end_simple, end_outer, end_inner = self._resolve_coordinate_to_db(vrs_model.end)

        # Construct Location and delegate to SequenceReference mapper
        return db.Location(
            id=vrs_model.id,
            sequence_reference_id=vrs_model.sequenceReference.refgetAccession,
            sequence_reference=self.seq_ref_mapper.to_db_entity(
                vrs_model.sequenceReference
            ),
            start=start_simple,
            end=end_simple,
            start_outer=start_outer,
            start_inner=start_inner,
            end_outer=end_outer,
            end_inner=end_inner,
        )

    def _resolve_coordinate_from_db(
        self, simple: int | None, outer: int | None, inner: int | None
    ) -> int | vrs_models.Range | None:
        """Resolve coordinate from DB fields to VRS format."""
        if simple is not None:
            return simple
        if outer is not None and inner is not None:
            return vrs_models.Range(start=outer, end=inner)
        return None

    def _resolve_coordinate_to_db(
        self, coordinate: int | vrs_models.Range | None
    ) -> tuple[int | None, int | None, int | None]:
        """Resolve VRS coordinate to DB fields."""
        if coordinate is None:
            return None, None, None
        if isinstance(coordinate, vrs_models.Range):
            return None, coordinate.start, coordinate.end
        if isinstance(coordinate, int):
            return coordinate, None, None
        return None, None, None


class AlleleMapper(BaseMapper[vrs_models.Allele, db.Allele]):
    """Maps between Allele entities."""

    def __init__(self) -> None:
        """Initialize AlleleMapper."""
        self.location_mapper = SequenceLocationMapper()

    def to_vrs_model(self, db_entity: db.Allele) -> vrs_models.Allele:
        """Convert DB Allele to VRS Allele."""
        # Reconstruct state from JSONB
        state = self._reconstruct_state(db_entity.state)

        # Construct Allele and delegate to Location mapper
        return vrs_models.Allele(
            id=db_entity.id,
            type="Allele",
            location=self.location_mapper.to_vrs_model(db_entity.location),
            state=state,
        )

    def to_db_entity(self, vrs_model: vrs_models.Allele) -> db.Allele:
        """Convert VRS Allele to DB Allele."""
        # Ensure IDs are computed if not present
        if not vrs_model.id:
            # TODO implement here and for other objects, maybe further up the stack
            raise NotImplementedError("Auto ID generation not implemented yet")

        # Validate required nested objects
        if not vrs_model.location or not vrs_model.location.sequenceReference:
            raise ValueError("Allele requires valid location and sequenceReference")

        # Serialize state
        state_dict = vrs_model.state.model_dump(exclude_none=True)

        return db.Allele(
            id=vrs_model.id,
            location_id=vrs_model.location.id,
            location=self.location_mapper.to_db_entity(vrs_model.location),
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
        raise ValueError(f"Unknown state type: {state_type}")
