"""anyvar prototype app

"""
import coloredlogs
import connexion
from connexion.resolver import RestyResolver
from flask import Flask, redirect

from anyvar.restapi.utils import get_tmp_openapi_yaml

from .uidoc import rapidoc_template, redoc_template


def create_app() -> Flask:
    """Construct Flask app instance. Uses generated schema stashed in tempfile.

    """
    coloredlogs.install(level="INFO")
    spec_fn = get_tmp_openapi_yaml()

    cxapp = connexion.App(__name__, debug=True, specification_dir=spec_fn.parent)
    cxapp.add_api(spec_fn,
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

    return cxapp.app  # type: ignore


if __name__ == "__main__":
    cxapp = create_app()
    cxapp.run(host="0.0.0.0", processes=1)
