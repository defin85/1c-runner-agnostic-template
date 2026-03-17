#!/usr/bin/env bash
set -euo pipefail

if ! command -v vrunner >/dev/null 2>&1; then
  printf 'error: vrunner is not installed or not in PATH\n' >&2
  exit 1
fi

exec vrunner "$@"
