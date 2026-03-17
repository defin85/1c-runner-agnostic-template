#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env UPDATE_DB_CMD
    run_command_string "Update DB configuration via direct-platform adapter" "$UPDATE_DB_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_UPDATE_DB_CMD
    run_command_string "Update DB configuration via remote-windows adapter" "$WINDOWS_UPDATE_DB_CMD"
    ;;
  vrunner)
    require_env VRUNNER_UPDATE_DB_CMD
    run_command_string "Update DB configuration via vrunner adapter" "$VRUNNER_UPDATE_DB_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
