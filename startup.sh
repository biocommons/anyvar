# 1. Create venv if it doesn't already exist
if [ ! -d "$VEDIR" ]; then
	make venv/$PYV
fi;

# 2. Source the venv if it hasn't already been activated
if [ -z "$$VIRTUAL_ENV" ]; then
	. "$VEDIR/bin/activate"
fi;

# 3. Load .env if present
if [ -f .env ]; then
	set -a;
	. .env;
	set +a;
fi;

# 4. Start the server
uvicorn anyvar.restapi.main:app
