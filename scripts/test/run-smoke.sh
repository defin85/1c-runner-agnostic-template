#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env SMOKE_RUN_CMD
    run_command_string "Run smoke checks via direct-platform adapter" "$SMOKE_RUN_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_SMOKE_RUN_CMD
    run_command_string "Run smoke checks via remote-windows adapter" "$WINDOWS_SMOKE_RUN_CMD"
    ;;
  vrunner)
    require_env VRUNNER_SMOKE_CMD
    run_command_string "Run smoke checks via vrunner adapter" "$VRUNNER_SMOKE_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
