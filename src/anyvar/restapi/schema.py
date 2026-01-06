"""Provide response definitions to REST API endpoint."""

from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any

from ga4gh.vrs import (
    VRS_VERSION,
    models,
)
from ga4gh.vrs import (
    __version__ as vrs_python_version,
)
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from anyvar import __version__
from anyvar.utils import types
from anyvar.utils.liftover_utils import ReferenceAssembly
from anyvar.utils.types import (
    SupportedVariationType,
    VrsObject,
    VrsVariation,
)


class EndpointTag(str, Enum):
    """Denote endpoint group membership"""

    GENERAL = "General"
    VCF = "VCF Operations"
    VRS_OBJECTS = "VRS Objects"
    SEARCH = "Search"


class ServiceEnvironment(str, Enum):
    """Define current runtime environment."""

    DEV = "dev"
    PROD = "prod"
    TEST = "test"
    STAGING = "staging"


class ServiceOrganization(BaseModel):
    """Define service_info response for organization field"""

    name: str = Field(
        default="bioccommons",
        description="Name of the organization responsible for the service",
    )
    url: str = Field(
        default="https://biocommons.org",
        description="URL of the website of the organization (RFC 3986 format)",
    )


class ServiceType(BaseModel):
    """Define service_info response for type field"""

    group: str = Field(
        default="org.biocommons",
        description="Namespace in reverse domain name format. Use `org.ga4gh` for implementations compliant with official GA4GH specifications. For services with custom APIs not standardized by GA4GH, or implementations diverging from official GA4GH specifications, use a different namespace (e.g. your organization''s reverse domain name).",
    )
    artifact: str = Field(
        default="anyvar",
        description="Name of the API or GA4GH specification implemented. Official GA4GH types should be assigned as part of standards approval process. Custom artifacts are supported.",
    )
    version: str = __version__


class SpecMetadata(BaseModel):
    """Define substructure for reporting specification metadata."""

    vrs_version: str = VRS_VERSION


class ImplMetadata(BaseModel):
    """Define substructure for reporting metadata about internal software dependencies."""

    vrs_python_version: str = vrs_python_version


class CapabilitiesMetadata(BaseModel):
    """Define substructure for reporting metadata about service capabilities"""

    liftover_assemblies: list[str] = ["GRCh38", "GRCh37"]


class ServiceInfo(BaseModel):
    """Define response structure for GA4GH /service_info endpoint."""

    id: str = Field(
        default="org.biocommons.anyvar",
        description="Unique ID of this service. Reverse domain name notation is recommended, though not required. The identifier should attempt to be globally unique so it can be used in downstream aggregator services e.g. Service Registry.",
    )
    name: str = Field(
        default="AnyVar", description="Name of this service. Should be human readable."
    )
    type: ServiceType = Field(ServiceType(), description="Type of a GA4GH service")
    description: str = Field(
        default="Register and retrieve variations and associated annotations.",
        description="Description of the service. Should be human readable and provide information about the service.",
    )
    organization: ServiceOrganization = Field(
        default=ServiceOrganization(), description="Organization providing the service"
    )
    contactUrl: str = Field(  # noqa: N815
        default="mailto:alex.wagner@nationwidechildrens.org",
        description="URL of the contact for the provider of this service, e.g. a link to a contact form (RFC 3986 format), or an email (RFC 2368 format).",
    )
    documentationUrl: str = Field(  # noqa: N815
        default="https://github.com/biocommons/anyvar",
        description="URL of the documentation of this service (RFC 3986 format). This should help someone learn how to use your service, including any specifics required to access data, e.g. authentication.",
    )
    createdAt: datetime = Field(  # noqa: N815
        default=datetime.fromisoformat("2025-06-01T00:00:00Z"),
        description="Timestamp describing when the service was first deployed and available (RFC 3339 format)",
    )
    updatedAt: datetime = Field(  # noqa: N815
        default=datetime.fromisoformat("2025-06-01T00:00:00Z"),
        description="Timestamp describing when the service was last updated (RFC 3339 format)",
    )
    environment: ServiceEnvironment = Field(
        default=ServiceEnvironment.DEV,
        description="Environment the service is running in. Use this to distinguish between production, development and testing/staging deployments. Suggested values are prod, test, dev, staging. However this is advised and not enforced.",
    )
    version: str = __version__
    spec_metadata: SpecMetadata = SpecMetadata()
    impl_metadata: ImplMetadata = ImplMetadata()
    capabilities_metadata: CapabilitiesMetadata = CapabilitiesMetadata()


class TranslationResult(BaseModel):
    """Describe structure for translation success or failure"""

    variation: VrsVariation | None = None
    error: str | None = None


class VariationRequest(BaseModel):
    """Describe request structure for the PUT and POST /variation endpoints"""

    model_config = ConfigDict(use_enum_values=True)

    definition: StrictStr
    input_type: SupportedVariationType | None = None
    copies: int | None = None
    copy_change: models.CopyChange | None = None
    assembly_name: ReferenceAssembly | None = ReferenceAssembly.GRCH38


class AddAnnotationResponse(BaseModel):
    """Response for the POST /variation/{vrs_id}/annotations endpoint"""

    object: VrsObject | None
    object_id: str | None
    annotation_type: str | None
    annotation_value: Any | None
    annotation_id: int | None


class AddAnnotationRequest(BaseModel):
    """Request for the POST /variation/{vrs_id}/annotations endpoint.

    Used when the annotation is identified through the request path.
    """

    annotation_type: str
    annotation_value: Any


class GetAnnotationResponse(BaseModel):
    """Response for the GET /variation/{vrs_id}/annotations/{annotation_type} endpoint"""

    annotations: list[types.Annotation]


class AddMappingResponse(BaseModel):
    """Response for POST /variation/{vrs_id}/mappings endpoint"""

    model_config = ConfigDict(use_enum_values=True)

    source_object: VrsObject | None
    source_object_id: str
    dest_object: VrsObject | None
    dest_object_id: str
    mapping_type: types.VariationMappingType


class AddMappingRequest(BaseModel):
    """Request for the POST /variation/{vrs_id}/mappings endpoint"""

    model_config = ConfigDict(use_enum_values=True)

    dest_id: str
    mapping_type: types.VariationMappingType


class GetMappingResponse(BaseModel):
    """Request for the GET /variation/{vrs_id}/mappings endpoint"""

    mappings: Iterable[types.VariationMapping]


class RegisterVariationResponse(BaseModel):
    """Describe response for the PUT /variation, PUT /variations, and PUT /vrs_variation endpoints"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "input_variation": {
                        "definition": "NC_000007.13:g.36561662_36561663del",
                        "input_type": "Allele",
                        "copies": 0,
                        "copy_change": "complete genomic loss",
                        "assembly_name": None,
                    },
                    "messages": [],
                    "object": {
                        "id": "ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
                        "type": "Allele",
                        "digest": "d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
                        "location": {
                            "id": "ga4gh:SL.JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
                            "type": "SequenceLocation",
                            "digest": "JOFKL4nL5mRUlO_xLwQ8VOD1v7mxhs3I",
                            "sequenceReference": {
                                "type": "SequenceReference",
                                "refgetAccession": "SQ.IW78mgV5Cqf6M24hy52hPjyyo5tCCd86",
                            },
                            "start": 36561661,
                            "end": 36561663,
                        },
                        "state": {
                            "type": "ReferenceLengthExpression",
                            "length": 0,
                            "sequence": "",
                            "repeatSubunitLength": 2,
                        },
                    },
                    "object_id": "ga4gh:VA.d6ru7RcuVO0-v3TtPFX5fZz-GLQDhMVb",
                }
            ]
        }
    )

    input_variation: VariationRequest | VrsVariation
    messages: list[str] = []
    object: types.VrsVariation | None = None
    object_id: str | None = None


class GetObjectResponse(BaseModel):
    """Describe response for the GET /variation endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
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
            ]
        }
    )

    messages: list[StrictStr]
    data: VrsObject | None = None


class SearchResponse(BaseModel):
    """Describe response for the GET /search endpoint"""

    variations: list[models.Variation]


class RunStatusResponse(BaseModel):
    """Represents the response for triggering or checking the status of a run
    at the GET /vcf/{run_id} endpoint.
    """

    run_id: str  # Run ID
    status: str  # Run status
    status_message: str | None = None  # Detailed status message for failures


class ErrorResponse(BaseModel):
    """Represents an error message"""

    error: str  # Error message
    error_code: str | None = None  # error code
