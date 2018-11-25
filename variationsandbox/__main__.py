import connexion
from connexion.resolver import RestyResolver
from jinja2 import Template
from pkg_resources import resource_filename


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
    """adds subservice to app. `prefix` refers to directory, module name,
and path component in openapi spec -- all must agree."""
    fn = resource_filename(__name__, prefix + "/openapi.yaml")
    app.add_api(fn, resolver=RestyResolver("variationsandbox." + prefix))
    subservices.append(prefix)


app = connexion.App(__name__, debug=True)
_add_subservice(app, "car")
_add_subservice(app, "vr")

@app.route('/')
def index():
    return jinja_template.render(subservices=subservices)

# e.g., http://0.0.0.0:9090/v0/ui/
app.run(port=9090)
