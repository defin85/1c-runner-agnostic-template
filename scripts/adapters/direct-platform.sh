#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

if [ "$#" -eq 0 ]; then
  printf 'usage: %s <command> [args...]\n' "$0" >&2
  exit 1
fi

command_name="${1##*/}"
if [ "${ONEC_DIRECT_PLATFORM_XVFB_ENABLED:-0}" = "1" ]; then
  case "$command_name" in
    1cv8|1cv8c)
      require_command xvfb-run
      require_command xauth
      if [ -n "${ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS:-}" ]; then
        exec xvfb-run -a --error-file=/dev/stderr --server-args="${ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS}" "$@"
      fi
      exec xvfb-run -a --error-file=/dev/stderr "$@"
      ;;
  esac
fi

exec "$@"
