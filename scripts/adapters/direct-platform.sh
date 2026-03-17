#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  printf 'usage: %s <command> [args...]\n' "$0" >&2
  exit 1
fi

exec "$@"
