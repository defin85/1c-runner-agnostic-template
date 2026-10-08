#!/usr/bin/env bash
set -euo pipefail

# Interactive 1C client of the runtime-profile infobase: start/screenshot/key/click/status/stop.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/../python/run-python.sh" "run-client" "$@"
