import logging
import sys

import connexion
from flask import redirect
from connexion.resolver import RestyResolver
from pkg_resources import resource_filename


_logger = logging.getLogger(__name__)


app = connexion.App(__name__,
                    debug=True,
                    )
fn = resource_filename(__name__, "/_data/openapi/openapi.yaml")
app.add_api(fn, resolver=RestyResolver("variationsandbox"))


@app.route('/')
def index():
    return redirect("/ui")


if __name__ == "__main__":
    app.run(host="localhost")
