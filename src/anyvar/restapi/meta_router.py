"""Provide routers for service metadata operations"""

from fastapi import APIRouter, Request

from anyvar.restapi.schema import ServiceInfo

meta_router = APIRouter()


@meta_router.get(
    "/service-info",
    summary="Get basic service information",
    description="Retrieve service metadata, such as versioning and contact info. Structured in conformance with the [GA4GH service info API specification](https://www.ga4gh.org/product/service-info/)",
)
def service_info(
    request: Request,
) -> ServiceInfo:
    """Provide service info per GA4GH Service Info spec"""
    return request.app.state.service_info
