#!/usr/bin/env bash
set -euo pipefail

# Operator-host tools of the optional customer-site-operations module (VDI in Xpra, typed commands, transfers).
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SITE_OPERATOR_CWD="$PWD" exec "$script_dir/../python/run-python.sh" "site-operator" "$@"
