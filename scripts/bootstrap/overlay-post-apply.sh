#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./agents-overlay.sh
source "$SCRIPT_DIR/agents-overlay.sh"
# shellcheck source=./generated-project-surface.sh
source "$SCRIPT_DIR/generated-project-surface.sh"
# shellcheck source=../template/lib-overlay.sh
source "$SCRIPT_DIR/../template/lib-overlay.sh"

template_src_path="${1:-}"
project_name="${2:-}"
project_slug="${3:-}"
project_description="${4:-}"

root="$(project_root)"
cd "$root"

[ -n "$template_src_path" ] || die "template source path is empty"

# R22: these first steps run release code even when the previous update-template.sh of the project
# (v0.3.36 and earlier) applied the overlay. A target matrix with a missing source path or extension
# stops the update and returns the project work tree to HEAD; missing seed-once files come from the release.
bash "$root/scripts/python/run-python.sh" template-update-preflight --restore-on-failure
seed_missing_project_files "$template_src_path" "$root"

append_project_agents_overlay "$root/AGENTS.md"
refresh_generated_project_surface_on_update "$root" "$project_name" "$project_slug" "$project_description"
"$root/scripts/llm/export-context.sh" --write >/dev/null
