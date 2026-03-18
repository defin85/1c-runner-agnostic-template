#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./agents-overlay.sh
source "$SCRIPT_DIR/agents-overlay.sh"

template_src_path="${1:-}"
init_beads="${2:-yes}"

root="$(project_root)"
cd "$root"

if [ -z "$template_src_path" ] || [ ! -f "$template_src_path/.github/workflows/ci.yml" ]; then
  printf 'error: template source path does not contain .github/workflows/ci.yml\n' >&2
  exit 1
fi

install -D -m 0644 "$template_src_path/.github/workflows/ci.yml" "$root/.github/workflows/ci.yml"

if [ ! -f "$root/AGENTS.md" ]; then
  log "Skip AGENTS.md overlay refresh because AGENTS.md is absent"
  exit 0
fi

append_project_agents_overlay "$root/AGENTS.md" "$init_beads"
