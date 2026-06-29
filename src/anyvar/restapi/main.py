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
from anyvar.restapi.categorical_variants_router import catvar_router
from anyvar.restapi.meta_router import meta_router
from anyvar.restapi.objects_router import objects_router
from anyvar.restapi.schema import (
    EndpointTag,
    ServiceInfo,
)
from anyvar.restapi.variations_router import variations_router
from anyvar.restapi.vcf_router import vcf_router

load_dotenv()
_logger = logging.getLogger(__name__)


async def _load_yaml_mapping(
    config_path: pathlib.Path,
    config_description: str,
) -> dict | None:
    """Load a YAML config file, requiring a top-level mapping."""
    try:
        async with await anyio.open_file(config_path) as f:
            contents = await f.read()
    except (OSError, UnicodeError):
        _logger.exception(
            "Error reading %s from %s. Using default configs",
            config_description,
            config_path,
        )
        return None

    try:
        config = yaml.safe_load(contents)
    except yaml.YAMLError:
        _logger.exception(
            "Error parsing %s from %s. Using default configs",
            config_description,
            config_path,
        )
        return None

    if not isinstance(config, dict):
        _logger.error(
            "%s at %s must be a YAML mapping, got %s. Using default configs",
            config_description,
            config_path,
            type(config).__name__,
        )
        return None

    return config


def _get_config_file_path(env_var: str) -> pathlib.Path | None:
    """Return config file path from an environment variable, if valid."""
    config_file = os.environ.get(env_var)
    if not config_file:
        return None

    config_path = pathlib.Path(config_file)
    if config_path.is_file():
        return config_path

    _logger.warning("%s is set to %s, but it is not a file.", env_var, config_file)
    return None


async def _configure_logging() -> None:
    """Configure logging from file if available."""
    logging_config_file = _get_config_file_path("ANYVAR_LOGGING_CONFIG")
    if logging_config_file is None:
        _logger.info("Logging with default configs.")
        return

    config = await _load_yaml_mapping(logging_config_file, "logging configuration")
    if config is None:
        return

    try:
        logging.config.dictConfig(config)
    except Exception:
        _logger.exception(
            "Error in logging configuration at %s. Using default configs",
            logging_config_file,
        )
        return


async def _load_service_info() -> ServiceInfo:
    """Load service-info configs from file or return defaults"""
    service_info_config_file = _get_config_file_path("ANYVAR_SERVICE_INFO")
    if service_info_config_file is None:
        _logger.warning("Falling back on default service description")
        return ServiceInfo()

    service_info = await _load_yaml_mapping(
        service_info_config_file, "service info definition"
    )
    if service_info is None:
        return ServiceInfo()

    try:
        return ServiceInfo.model_validate(service_info)
    except ValueError:
        _logger.exception(
            "Error loading from service info description at %s. Using default configs",
            service_info_config_file,
        )
        return ServiceInfo()


@asynccontextmanager
async def app_lifespan(param_app: FastAPI):  # noqa: ANN201
    """Perform resource initialization/teardown"""
    await _configure_logging()
    param_app.state.service_info = await _load_service_info()

    # create anyvar instance
    storage = anyvar.anyvar.create_storage()
    translator = anyvar.anyvar.create_translator()
    projector = anyvar.anyvar.create_projector(translator)
    anyvar_instance = AnyVar(
        object_store=storage, translator=translator, projector=projector
    )

    # associate anyvar with the app state
    param_app.state.anyvar = anyvar_instance

    # enclose in try/finally to ensure teardown
    try:
        yield
    finally:
        storage.close()
        if projector is not None:
            projector.close()


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


app.include_router(meta_router, tags=[EndpointTag.META])
app.include_router(vcf_router, tags=[EndpointTag.VCF])
app.include_router(variations_router, tags=[EndpointTag.VARIATIONS])
app.include_router(objects_router, tags=[EndpointTag.VRS_OBJECTS])
app.include_router(
    catvar_router,
    prefix="/categorical_variants",
    tags=[EndpointTag.CATEGORICAL_VARIANTS],
)
