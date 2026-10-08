#!/usr/bin/env bash
set -euo pipefail

# Bounded technological log of one observed launch: status, cursor read, restore of logcfg.xml.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/../python/run-python.sh" "technological-log" "$@"
