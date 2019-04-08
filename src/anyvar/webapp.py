"""start anyvar development app

Starting AnyVar for development is tricky for a couple of reasons.

Connexion and underlying libraries don't support local *file* `$ref`s,
but using http refs does work. 

Practically, this means that splitting a schema into components
requires using a local development server for the $ref'd components.

Furthermore, connexion validates the openapi schema before the server
is up, so you can't serve subschemas via connexion initially.

So, the startup process below is:

  1. start a flask app on :5000 to serve /vmc.json

  2. create the connexion app with the openapi schema.  Connexion
     validates using vmc.json on :5000.

  3. shutdown the flask app.

  4. add a route for /vmc.json (and /ui) to the connexion app.

  5. start the connexion app

"""


from multiprocessing import Process
from pkg_resources import resource_filename

import connexion
from connexion.resolver import RestyResolver
from flask import Flask, redirect

from vmc import schema_path

from anyvar.uidoc import redoc_template, rapidoc_template


def start_vmc_server(port=5000):
    app = Flask(__name__)
    @app.route('/vmc.json')
    def vmc_schema():
        schema = open(schema_path).read()
        return schema, 200, {"Content-Type": "application/json; charset=utf-8"}
    app.run()



if __name__ == "__main__":
    p = Process(target=start_vmc_server)
    p.start()
    
    spec_dir = resource_filename(__name__, "_data")
    spec_fn = spec_dir + "/webapp.yaml"
    cxapp = connexion.App(__name__, debug=True, specification_dir=spec_dir)
    cxapp.add_api(spec_fn,
                  validate_responses=True,
                  strict_validation=True,
                  resolver=RestyResolver("anyvar.routes"))

    @cxapp.route("/vmc.json")
    def vmc_schema():
        schema = open(schema_path).read()
        return schema, 200, {"Content-Type": "application/json; charset=utf-8"}

    @cxapp.route('/redoc')
    def redoc():
        return redoc_template, 200

    @cxapp.route('/rapidoc')
    def rapidoc():
        return rapidoc_template, 200

    @cxapp.route('/')
    def index():
        return redirect("/ui")

    p.terminate()

    cxapp.run(host="0.0.0.0",
              extra_files=[spec_fn, schema_path],
              processes=1)
