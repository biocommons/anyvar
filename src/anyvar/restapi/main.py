"""Provide core route definitions for REST service."""

import logging
import logging.config
import os
import pathlib
from contextlib import asynccontextmanager

import anyio
import yaml
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
)

import anyvar
from anyvar import AnyVar
from anyvar.restapi.auth import get_token_auth_dependency
from anyvar.restapi.meta_router import meta_router
from anyvar.restapi.objects_router import objects_router
from anyvar.restapi.schema import (
    EndpointTag,
    ServiceInfo,
)
from anyvar.restapi.search_router import search_router
from anyvar.restapi.vcf_router import vcf_router

load_dotenv()
_logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(param_app: FastAPI):  # noqa: ANN201
    """Perform resource initialization/teardown"""
    # Configure logging from file or use default
    logging_config_file = os.environ.get("ANYVAR_LOGGING_CONFIG", None)
    if logging_config_file and pathlib.Path(logging_config_file).is_file():
        async with await anyio.open_file(logging_config_file) as f:
            try:
                contents = await f.read()
                config = yaml.safe_load(contents)
                logging.config.dictConfig(config)
                _logger.info("Logging using configs set from %s", logging_config_file)
            except Exception:
                _logger.exception(
                    "Error in Logging Configuration. Using default configs"
                )
    else:
        _logger.info("Logging with default configs.")

    # Override default service-info parameters
    service_info_config_file = os.environ.get("ANYVAR_SERVICE_INFO")
    if service_info_config_file and pathlib.Path(service_info_config_file).is_file():
        async with await anyio.open_file(service_info_config_file) as f:
            try:
                contents = await f.read()
                service_info = yaml.safe_load(contents)
                param_app.state.service_info = ServiceInfo(**service_info)
                _logger.info(
                    "Assigning service info values from %s", service_info_config_file
                )
            except Exception:
                _logger.exception(
                    "Error loading from service info description at %s. Using default configs",
                    service_info_config_file,
                )
                param_app.state.service_info = ServiceInfo()
    else:
        _logger.warning("Falling back on default service description.")
        param_app.state.service_info = ServiceInfo()

    # create anyvar instance
    storage = anyvar.anyvar.create_storage()
    translator = anyvar.anyvar.create_translator()
    anyvar_instance = AnyVar(object_store=storage, translator=translator)

    # associate anyvar with the app state
    param_app.state.anyvar = anyvar_instance
    yield

    # close storage connector on shutdown
    storage.close()


app = FastAPI(
    title="AnyVar",
    version=anyvar.__version__,
    docs_url="/",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"tryItOutEnabled": True},
    description="Register and retrieve VRS value objects.",
    lifespan=app_lifespan,
    dependencies=[Depends(get_token_auth_dependency())],
)


app.include_router(vcf_router, tags=[EndpointTag.VCF])
app.include_router(search_router, tags=[EndpointTag.SEARCH])
app.include_router(meta_router, tags=[EndpointTag.META])
app.include_router(objects_router, tags=[EndpointTag.VRS_OBJECTS])
