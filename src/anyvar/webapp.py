import connexion
from connexion.resolver import RestyResolver
from flask import redirect
from pkg_resources import resource_filename


spec_dir = "."
spec_fn = resource_filename(__name__, spec_dir + "/openapi.yaml")
cxapp = connexion.FlaskApp(__name__, debug=True)
cxapp.add_api(spec_fn,
            validate_responses=True,
            strict_validation=True,
            resolver=RestyResolver("anyvar"))

@cxapp.route('/')
def index():
    return redirect("/ui")


if __name__ == "__main__":
    cxapp.run(host="localhost",
            extra_files=[spec_fn])
