#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env BDD_RUN_CMD
    run_command_string "Run BDD checks via direct-platform adapter" "$BDD_RUN_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_BDD_RUN_CMD
    run_command_string "Run BDD checks via remote-windows adapter" "$WINDOWS_BDD_RUN_CMD"
    ;;
  vrunner)
    require_env VRUNNER_BDD_CMD
    run_command_string "Run BDD checks via vrunner adapter" "$VRUNNER_BDD_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
