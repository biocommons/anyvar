import connexion
from connexion.resolver import RestyResolver
from pkg_resources import resource_filename


fn = resource_filename(__name__, "openapi.yaml")

app = connexion.App(__name__, debug=True,
                    specification_dir="openapi")
app.add_api(fn, resolver=RestyResolver("variationregistry.restservice.restapi"))

# e.g., http://0.0.0.0:9090/v0/ui/
app.run(port=9090)
