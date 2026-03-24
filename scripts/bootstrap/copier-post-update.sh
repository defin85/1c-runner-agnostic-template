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

if [ -z "$template_src_path" ]; then
  printf 'error: template source path is empty\n' >&2
  exit 1
fi

for asset in copier.yml .github/workflows/ci.yml; do
  if [ ! -f "$template_src_path/$asset" ]; then
    printf 'error: template source path does not contain %s\n' "$asset" >&2
    exit 1
  fi

  install -D -m 0644 "$template_src_path/$asset" "$root/$asset"
done

sync_template_nested_readmes "$template_src_path" "$root"
append_project_agents_overlay "$root/AGENTS.md" "$init_beads"
refresh_generated_project_surface_on_update "$root" "$project_name" "$project_slug" "$project_description"
"$root/scripts/llm/export-context.sh" --write >/dev/null
