Contributing to AnyVar
======================

First, clone the repo and install developer dependencies: ::

    git clone https://github.com/biocommons/anyvar.git
    cd anyvar
    make devready
    source venv/bin/activate

Then, start the REST server: ::

    python -m anyvar.restapi

In another shell instance, verify that the server is processing requests: ::

    curl http://localhost:5000/info


TODO

 * add style things
 * add testing notes
