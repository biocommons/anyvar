import connexion
from connexion.resolver import RestyResolver
from flask import redirect
from pkg_resources import resource_filename


def create_app(debug=False):
    cxapp = connexion.App(__name__, debug=debug)
    fn = resource_filename(__name__, "/openapi.yaml")
    cxapp.add_api(fn, resolver=RestyResolver("variationsandbox"))

    @cxapp.route('/')
    def index():
        return redirect("/ui")

    return cxapp


if __name__ == "__main__":
    cxapp = create_app(debug=True)
    cxapp.run(host="localhost")
