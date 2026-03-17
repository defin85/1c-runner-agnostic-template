#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./agents-overlay.sh
source "$SCRIPT_DIR/agents-overlay.sh"

init_beads="${1:-yes}"

root="$(project_root)"
cd "$root"

if [ ! -f "$root/AGENTS.md" ]; then
  log "Skip AGENTS.md overlay refresh because AGENTS.md is absent"
  exit 0
fi

append_project_agents_overlay "$root/AGENTS.md" "$init_beads"
