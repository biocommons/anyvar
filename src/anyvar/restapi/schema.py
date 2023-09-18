"""Provide response definitions to REST API endpoint."""
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from ga4gh.vrsatile.pydantic.vrs_models import Allele, SequenceLocation, Text
from pydantic import BaseModel, StrictInt, StrictStr


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
        def schema_extra(schema: Dict[str, Any], model: Type["InfoResponse"]) -> None:
            """Configure OpenAPI schema"""
            if "title" in schema.keys():
                schema.pop("title", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)
            schema["example"] = {
                "anyvar": {"version": "0.1.2.dev58+g81eb592.d20230316"},
                "ga4gh_vrs": {"version": "0.7.6"},
            }


class GetSequenceLocationResponse(BaseModel):
    """Describe response for the /locations/ endpoint"""

    location: Optional[SequenceLocation]


class RegisterVariationRequest(BaseModel):
    """Describe request structure for variation registration endpoint"""

    definition: StrictStr

    class Config:
        """Configure RegisterVariationRequest class"""

        schema_extra = {"example": {"definition": "BRAF V600E"}}


class RegisterVariationResponse(BaseModel):
    """Describe response for the variation registry endpoint"""

    messages: List[str]
    object: Optional[Dict]
    object_id: Optional[str]

    class Config:
        """Configure RegisterVariationResponse class"""

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type["RegisterVariationResponse"]) -> None:
            """Configure OpenAPI schema"""
            if "title" in schema.keys():
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

    messages: List[str]
    object: Optional[Dict]
    object_id: Optional[str]


class GetVariationResponse(BaseModel):
    """Describe response for the /variation get endpoint"""

    messages: List[StrictStr]
    data: Union[Allele, Text]

    class Config:
        """Configure GetVariationResponse class"""

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type["GetVariationResponse"]) -> None:
            """Configure OpenAPI schema"""
            if "title" in schema.keys():
                schema.pop("title", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("title", None)
            schema["example"] = {
                "messages": [],
                "data": {
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
            }


class SearchResponse(BaseModel):
    """Describe response for the /search endpoint"""

    variations: List[Allele]


class VariationStatisticType(str, Enum):
    """Define parameter values for variation statistics endpoint"""

    SUBSTITUTION = "substitution"
    DELETION = "deletion"
    INSERTION = "insertion"
    TEXT = "text"
    ALL = "all"


class AnyVarStatsResponse(BaseModel):
    """Describe response for the /stats endpoint"""

    variation_type: VariationStatisticType
    count: StrictInt
