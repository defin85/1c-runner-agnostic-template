#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  printf 'usage: %s <command> [args...]\n' "$0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

resolve_python() {
  if [ -n "${ONEC_PYTHON:-}" ]; then
    printf '%s\n' "$ONEC_PYTHON"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  printf 'error: Python 3.12+ was not found. Set ONEC_PYTHON or install python3/python.\n' >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"
cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m scripts.python.cli "$@"
