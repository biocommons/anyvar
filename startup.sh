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

# 4. Start the server
exec uvicorn anyvar.restapi.main:app --app-dir src
