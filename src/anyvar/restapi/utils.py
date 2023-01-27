"""Provide miscellaneous helper functions for AnyVar web app"""
import logging
from pathlib import Path
import re
import importlib.resources
import tempfile
from typing import Generator

from ga4gh.vrs import schema_path


_logger = logging.getLogger("anyvar_api")


def generate_openapi_yaml():
    """Replace relative files in $ref with local file paths

    """
    with importlib.resources.path("anyvar.restapi._data", "openapi.yaml") as p:
        spec_fn = p
    ref_map = {
        "vr.json": schema_path,
        # TODO: jsonapi isn't implemented yet
        # "jsonapi.json": spec_dir + "/jsonapi.json",
        }
    ref_re = re.compile(r"""^(\s+\$ref:\s+["']file:)(\w[^#]+)(#)""", re.MULTILINE)
    with open(spec_fn) as spec_f:
        finished_spec = ref_re.sub(lambda m: m.group(1) + "//" + ref_map[m.group(2)] + m.group(3), spec_f.read())

    return finished_spec


def get_tmp_openapi_yaml() -> Path:
    """Stand up a complete OpenAPI specification file in a temporary location.

    """
    openapi_fn = Path(tempfile.gettempdir()) / "openapi.yaml"
    with open(openapi_fn, "w") as f:
        f.write(generate_openapi_yaml())

    _logger.info(f"Wrote {openapi_fn}")

    return openapi_fn
