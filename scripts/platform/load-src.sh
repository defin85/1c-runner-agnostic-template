#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env LOAD_SRC_CMD
    run_command_string "Load source tree via direct-platform adapter" "$LOAD_SRC_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_LOAD_SRC_CMD
    run_command_string "Load source tree via remote-windows adapter" "$WINDOWS_LOAD_SRC_CMD"
    ;;
  vrunner)
    require_env VRUNNER_LOAD_SRC_CMD
    run_command_string "Load source tree via vrunner adapter" "$VRUNNER_LOAD_SRC_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
