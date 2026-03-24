#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./agents-overlay.sh
source "$SCRIPT_DIR/agents-overlay.sh"
# shellcheck source=./generated-project-surface.sh
source "$SCRIPT_DIR/generated-project-surface.sh"

template_src_path="${1:-}"
project_name="${2:-}"
project_slug="${3:-}"
project_description="${4:-}"
init_beads="${5:-yes}"

root="$(project_root)"
cd "$root"

[ -n "$template_src_path" ] || die "template source path is empty"

append_project_agents_overlay "$root/AGENTS.md" "$init_beads"
refresh_generated_project_surface_on_update "$root" "$project_name" "$project_slug" "$project_description"
"$root/scripts/llm/export-context.sh" --write >/dev/null
