"""anyvar prototype app

"""

import logging

from pkg_resources import resource_filename

import coloredlogs
from ga4gh.vrs import schema_path

from .uidoc import redoc_template, rapidoc_template
from .utils import replace_dollar_ref

from tempfile import TemporaryDirectory
import connexion
from connexion.resolver import RestyResolver
from flask import redirect

_logger = logging.getLogger(__name__)


def generate_openapi_yaml():
    """Replace relative files in $ref with local file paths and write to temporary file

    """

    spec_dir = resource_filename(__name__, "_data")
    spec_fn = spec_dir + "/openapi.yaml"
    ref_map = {
        "vr.json": schema_path,
        # jsonapi isn't implemented yet
        # "jsonapi.json": spec_dir + "/jsonapi.json",
        }
    return replace_dollar_ref(open(spec_fn).read(), ref_map)


def run(actually_run=True):

    td = TemporaryDirectory()
    tmpdir = td.name
    openapi_fn = tmpdir + "/openapi.yaml"
    open(openapi_fn, "w").write(generate_openapi_yaml())
    _logger.info(f"Wrote {openapi_fn}")

    cxapp = connexion.App(__name__, debug=True, specification_dir=tmpdir)
    cxapp.add_api(openapi_fn,
                  validate_responses=True,
                  strict_validation=True,
                  resolver=RestyResolver("anyvar.restapi.routes"))

    @cxapp.route('/redoc')
    def redoc():
        return redoc_template, 200

    @cxapp.route('/rapidoc')
    def rapidoc():
        return rapidoc_template, 200

    @cxapp.route('/')
    def index():
        return redirect("/ui")

    if actually_run:
        cxapp.run(host="0.0.0.0",
                  processes=1)
    else:
        return cxapp.app


if __name__ == "__main__":
    coloredlogs.install(level="INFO")
    run()

