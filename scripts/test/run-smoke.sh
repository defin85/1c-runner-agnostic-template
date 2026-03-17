#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-smoke.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>   Directory for summary.json and command logs
  --dry-run          Resolve adapter/profile and write dry-run summary only
  -h, --help         Show this help
EOF
}

if capability_help_requested "$@"; then
  usage
  exit 0
fi

run_adapter_capability \
  "run-smoke" \
  "Run smoke checks" \
  "SMOKE_RUN_CMD" \
  "WINDOWS_SMOKE_RUN_CMD" \
  "VRUNNER_SMOKE_CMD" \
  "$@"
