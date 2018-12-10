import logging
import sys

import connexion
from connexion.resolver import RestyResolver
from jinja2 import Template
from pkg_resources import resource_filename


_logger = logging.getLogger(__name__)


jinja_template = Template("""
<!DOCTYPE html>
<html>
<head>
 <title>Variation Sandbox</title>
</head>
<body>
<h1>Variation Sandbox</h1>
<ul>
 {% for svc in subservices %}
 <li><a href="{{svc}}/ui">{{svc}}</a></li>
 {% endfor %}
 </ul>
 
</body>
</html>
""")


subservices = []
def _add_subservice(app, prefix):
    """adds subservice to app. `prefix` refers to three components:
    module name, and path component in openapi spec.

    """
    fn = resource_filename(__name__, prefix + "/openapi.yaml")
    fn = "/home/reece/projects/variation-sandbox/variationsandbox/" + prefix + "/openapi.yaml"
    app.add_api(fn, resolver=RestyResolver("variationsandbox." + prefix))
    subservices.append(prefix)


app = connexion.App(__name__,
                    debug=True,
                    # server="tornado",
                    )
_add_subservice(app, "car")
_add_subservice(app, "vr")

@app.route('/')
def index():
    return jinja_template.render(subservices=subservices)


if __name__ == "__main__":
    # e.g., http://0.0.0.0:9090/v0/ui/
    app.run(port=9000)
