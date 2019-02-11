import connexion
from connexion.resolver import RestyResolver
from flask import redirect
from pkg_resources import resource_filename


def create_app(debug=False):
    app = connexion.App(__name__, debug=debug)
    fn = resource_filename(__name__, "/openapi.yaml")
    app.add_api(fn, resolver=RestyResolver("variationsandbox"))

    @app.route('/')
    def index():
        return redirect("/ui")

    return app


if __name__ == "__main__":
    app = create_app(debug=True)
    app.run(host="localhost")
