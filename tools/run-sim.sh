#!/bin/sh
# Run the DroidOS reference brain in simulation on a developer machine (spec §26).
# Unlike build-image.sh, this IS runnable wherever Python 3.10+ is available.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
export DROIDOS_STATE="${DROIDOS_STATE:-$ROOT/run-state}"

PY="${PYTHON:-python3}"

echo "DroidOS reference brain (simulation), state: $DROIDOS_STATE"
"$PY" -m droidos.cli.droidctl status
echo
"$PY" -m droidos.cli.droid "$@"
