"""Provide response definitions to REST API endpoint."""

from enum import Enum
from typing import Any, Optional

from ga4gh.vrs import models
from pydantic import BaseModel, StrictInt, StrictStr

from anyvar.utils.types import SupportedVariationType


class EndpointTag(str, Enum):
    """Denote endpoint group membership"""

    GENERAL = "General"
    SEQUENCES = "Sequences"
    LOCATIONS = "Locations"
    VARIATIONS = "Variations"
    SEARCH = "Search"


class DependencyInfo(BaseModel):
    """Provide information for a specific dependency"""

    version: StrictStr


class InfoResponse(BaseModel):
    """Describe response for the /info endpoint"""

    anyvar: DependencyInfo
    ga4gh_vrs: DependencyInfo

    class Config:
        """Configure InfoResponse class"""

        @staticmethod
        def schema_extra(schema: dict[str, Any], model: type["InfoResponse"]) -> None:  # noqa: ARG004
            """Configure OpenAPI schema"""
            if "title" in schema:
                schema.pop("title", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)
            schema["example"] = {
                "anyvar": {"version": "0.1.2.dev58+g81eb592.d20230316"},
                "ga4gh_vrs": {"version": "0.7.6"},
            }


class GetSequenceLocationResponse(BaseModel):
    """Describe response for the /locations/ endpoint"""

    location: models.SequenceLocation | None


class RegisterVariationRequest(BaseModel):
    """Describe request structure for variation registration endpoint"""

    definition: StrictStr
    input_type: SupportedVariationType | None = None
    copies: int | None = None
    copy_change: models.CopyChange | None = None

    class Config:
        """Configure RegisterAlleleRequest class"""

        schema_extra = {  # noqa: RUF012
            "example": {
                "definition": "BRAF V600E",
                "input_type": None,
                "copies": None,
                "copy_change": None,
            }
        }


class RegisterVariationResponse(BaseModel):
    """Describe response for the variation registry endpoint"""

    messages: list[str]
    object: models.Variation | None
    object_id: str | None

    class Config:
        """Configure RegisterVariationResponse class"""

        @staticmethod
        def schema_extra(
            schema: dict[str, Any],
            model: type["RegisterVariationResponse"],  # noqa: ARG004
        ) -> None:
            """Configure OpenAPI schema"""
            if "title" in schema:
                schema.pop("title", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)
            schema["example"] = {
                "messages": [],
                "object": {
                    "_id": "ga4gh:VA.ZDdoQdURgO2Daj2NxLj4pcDnjiiAsfbO",
                    "type": "Allele",
                    "location": {
                        "_id": "ga4gh:VSL.2cHIgn7iLKk4x9z3zLkSTTFMV0e48DR4",
                        "type": "SequenceLocation",
                        "sequence_id": "ga4gh:SQ.cQvw4UsHHRRlogxbWCB8W-mKD4AraM9y",
                        "interval": {
                            "type": "SequenceInterval",
                            "start": {"type": "Number", "value": 599},
                            "end": {"type": "Number", "value": 600},
                        },
                    },
                    "state": {"type": "LiteralSequenceExpression", "sequence": "E"},
                },
                "object_id": "ga4gh:VA.ZDdoQdURgO2Daj2NxLj4pcDnjiiAsfbO",
            }


class RegisterVrsVariationResponse(BaseModel):
    """Describe response for VRS object registration endpoint"""

    messages: list[str]
    object: models.Variation | None
    object_id: str | None


class GetVariationResponse(BaseModel):
    """Describe response for the /variation get endpoint"""

    messages: list[StrictStr]
    data: models.Variation

    class Config:
        """Configure GetVariationResponse class"""

        @staticmethod
        def schema_extra(
            schema: dict[str, Any],
            model: type["GetVariationResponse"],  # noqa: ARG004
        ) -> None:
            """Configure OpenAPI schema"""
            if "title" in schema:
                schema.pop("title", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)
            schema["example"] = {
                "messages": [],
                "data": {
                    "digest": "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
                    "id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
                    "location": {
                        "digest": "01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
                        "id": "ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
                        "start": 87894076,
                        "end": 87894077,
                        "sequenceReference": {
                            "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB",
                            "type": "SequenceReference",
                        },
                        "type": "SequenceLocation",
                    },
                    "state": {"sequence": "T", "type": "LiteralSequenceExpression"},
                    "type": "Allele",
                },
            }


class SearchResponse(BaseModel):
    """Describe response for the /search endpoint"""

    variations: list[models.Variation]


class VariationStatisticType(str, Enum):
    """Define parameter values for variation statistics endpoint"""

    SUBSTITUTION = "substitution"
    DELETION = "deletion"
    INSERTION = "insertion"
    ALL = "all"


class AnyVarStatsResponse(BaseModel):
    """Describe response for the /stats endpoint"""

    variation_type: VariationStatisticType
    count: StrictInt


class RunStatusResponse(BaseModel):
    """Represents the response for triggering or checking the status of a run."""

    run_id: str  # Run ID
    status: str  # Run status
    status_message: Optional[str] = (  # noqa: UP007
        None  # Detailed status message for failures
    )


class ErrorResponse(BaseModel):
    """Represents an error message"""

    error: str  # Error message
    error_code: Optional[str] = None  # error code # noqa: UP007
