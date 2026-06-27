#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-bdd.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --target <id>      Target infobase id for multi-target repositories
  --run-root <dir>   Directory for summary.json and command logs
  --dry-run          Resolve adapter/profile and write dry-run summary only
  -h, --help         Show this help

For warmed BDD profiles:
  ONEC_BDD_MANIFEST=<file>    Manifest with feature paths
  ONEC_BDD_FEATURES=<list>    Newline- or comma-separated feature paths
EOF
}

if capability_help_requested "$@"; then
  usage
  exit 0
fi

run_profile_capability \
  "run-bdd" \
  "Run BDD checks" \
  "prepare_required_profile_command" \
  "$@"
