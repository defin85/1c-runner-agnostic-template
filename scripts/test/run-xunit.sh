#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env XUNIT_RUN_CMD
    run_command_string "Run xUnit checks via direct-platform adapter" "$XUNIT_RUN_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_XUNIT_RUN_CMD
    run_command_string "Run xUnit checks via remote-windows adapter" "$WINDOWS_XUNIT_RUN_CMD"
    ;;
  vrunner)
    require_env VRUNNER_XUNIT_CMD
    run_command_string "Run xUnit checks via vrunner adapter" "$VRUNNER_XUNIT_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
