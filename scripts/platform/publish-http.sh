#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

adapter="${RUNNER_ADAPTER:-direct-platform}"

case "$adapter" in
  direct-platform)
    require_env PUBLISH_HTTP_CMD
    run_command_string "Publish HTTP service via direct-platform adapter" "$PUBLISH_HTTP_CMD"
    ;;
  remote-windows)
    require_env WINDOWS_PUBLISH_HTTP_CMD
    run_command_string "Publish HTTP service via remote-windows adapter" "$WINDOWS_PUBLISH_HTTP_CMD"
    ;;
  vrunner)
    require_env VRUNNER_PUBLISH_HTTP_CMD
    run_command_string "Publish HTTP service via vrunner adapter" "$VRUNNER_PUBLISH_HTTP_CMD"
    ;;
  *)
    printf 'error: unsupported RUNNER_ADAPTER: %s\n' "$adapter" >&2
    exit 1
    ;;
esac
