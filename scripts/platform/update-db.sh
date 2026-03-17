#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/update-db.sh [options]

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

run_profile_capability \
  "update-db" \
  "Update DB configuration" \
  "prepare_update_db_command" \
  "$@"
