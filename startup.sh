set -euo pipefail
cd "$(dirname "$0")"

# 1. Create venv if it doesn't already exist
if [ ! -d "$VEDIR" ]; then
	make venv/$PYV
fi;

# 2. Source the venv if it hasn't already been activated
if [ -z "${VIRTUAL_ENV:-}" ]; then
	. "$VEDIR/bin/activate"
fi;

# 3. Start the server
if [ "${DEV_MODE:-false}" = "true" ]; then
  exec uvicorn anyvar.restapi.main:app --app-dir src --reload
else
  exec uvicorn anyvar.restapi.main:app
fi
