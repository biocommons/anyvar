"""anyvar prototype app

"""

from pkg_resources import resource_filename
from tempfile import TemporaryDirectory

import coloredlogs
import connexion
from connexion.resolver import RestyResolver
from flask import Flask, redirect
from ga4gh.vr import schema_path

from .uidoc import redoc_template, rapidoc_template
from .utils import replace_dollar_ref



def start_vr_server(port=5000):
    app = Flask(__name__)
    @app.route('/vr.json')
    def vr_schema():
        schema = open(schema_path).read()
        return schema, 200, {"Content-Type": "application/json; charset=utf-8"}
    app.run()


def generate_openapi_yaml():
    """Replace relative files in $ref with local file paths and write to temporary file

    """

    ref_map = {
        "vr.json": schema_path
        }
    spec_dir = resource_filename(__name__, "_data")
    spec_fn = spec_dir + "/webapp.yaml"
    return replace_dollar_ref(open(spec_fn).read(), ref_map)


if __name__ == "__main__":
    coloredlogs.install(level="INFO")

    tmpdir = TemporaryDirectory()
    openapi_fn = tmpdir.name + "/openapi.yaml"
    open(openapi_fn, "w").write(generate_openapi_yaml())

    cxapp = connexion.App(__name__, debug=True, specification_dir=tmpdir.name)
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

    cxapp.run(host="0.0.0.0",
              processes=1)
