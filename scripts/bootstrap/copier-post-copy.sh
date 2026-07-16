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
preferred_adapter="${5:-direct-platform}"
openspec_tools="${6:-none}"
init_git_repository="${7:-yes}"

root="$(project_root)"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

log "Project bootstrap started"
log "project_name=$project_name"
log "project_slug=$project_slug"
log "preferred_adapter=$preferred_adapter"

require_command openspec
require_command install

cd "$root"

if [ "$init_git_repository" = "yes" ] && [ ! -d "$root/.git" ]; then
  log "Initialize git repository"
  if [ "${DRY_RUN:-0}" != "1" ]; then
    git init >/dev/null
  fi
fi

cmd=(openspec init --tools "$openspec_tools")
log "Run OpenSpec init"
printf '%q ' "${cmd[@]}"
printf '\n'

if [ "${DRY_RUN:-0}" != "1" ]; then
  "${cmd[@]}"
  printf 'schema: spec-driven\n' >"$root/openspec/config.yaml"
fi

if [ -z "$template_src_path" ]; then
  die "template source path is empty"
fi

if [ "${DRY_RUN:-0}" != "1" ]; then
  sync_overlay_manifests \
    "$template_src_path" \
    "$root" \
    "$(overlay_manifest_file "$root")" \
    "$(overlay_manifest_file "$template_src_path")"
  append_project_agents_overlay "$root/AGENTS.md"
  seed_generated_project_surface_on_copy "$root" "$project_name" "$project_slug" "$project_description"
  write_overlay_source "$root" "$template_src_path"
  write_overlay_version "$root" "$(bootstrap_template_ref_or_fallback "$root" "$template_src_path")"
  "$root/scripts/llm/export-context.sh" --write >/dev/null
fi
