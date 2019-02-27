import connexion
from connexion.resolver import RestyResolver
from flask import redirect
from pkg_resources import resource_filename



spec_dir = "." # "_data/openapi"
spec_fn = resource_filename(__name__, spec_dir + "/openapi.yaml")
app = connexion.FlaskApp(__name__, debug=True)
app.add_api(spec_fn, resolver=RestyResolver("anyvar"))

@app.route('/')
def index():
    return redirect("/ui")


if __name__ == "__main__":
    app.run(host="localhost",
        extra_files=[spec_fn])
