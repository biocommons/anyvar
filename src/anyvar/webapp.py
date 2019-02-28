import connexion
from connexion.resolver import RestyResolver
from flask import redirect
from pkg_resources import resource_filename


spec_dir = resource_filename(__name__, ".")
spec_fn = spec_dir + "/webapp.yaml"
cxapp = connexion.App(__name__, debug=True, specification_dir=spec_dir)
cxapp.add_api(spec_fn,
            validate_responses=True,
            strict_validation=True,
            resolver=RestyResolver("anyvar"))

@cxapp.route('/')
def index():
    return redirect("/ui")


if __name__ == "__main__":
    cxapp.run(host="localhost",
              extra_files=[spec_fn],
              processes=1)
