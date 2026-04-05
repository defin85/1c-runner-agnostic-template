#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  printf 'usage: %s <skill-name> [args...]\n' "$0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ "$1" = "--readiness" ]; then
  shift
  bash "$SCRIPT_DIR/../python/run-python.sh" imported-skill-readiness "$@"
  exit $?
fi

bash "$SCRIPT_DIR/../python/run-python.sh" imported-skill "$@"
