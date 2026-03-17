#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env CREATE_IB_CMD
    run_command_string "Create infobase via direct-platform adapter" "$CREATE_IB_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_CREATE_IB_CMD
    run_command_string "Create infobase via remote-windows adapter" "$WINDOWS_CREATE_IB_CMD"
    ;;
  vrunner)
    require_env VRUNNER_CREATE_IB_CMD
    run_command_string "Create infobase via vrunner adapter" "$VRUNNER_CREATE_IB_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
