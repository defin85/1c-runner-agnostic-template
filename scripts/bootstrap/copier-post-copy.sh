#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./agents-overlay.sh
source "$SCRIPT_DIR/agents-overlay.sh"

template_src_path="${1:-}"
project_name="${2:-}"
project_slug="${3:-}"
preferred_adapter="${4:-direct-platform}"
openspec_tools="${5:-none}"
init_git_repository="${6:-yes}"
init_beads="${7:-yes}"
beads_prefix="${8:-}"

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

if [ "$init_beads" = "yes" ]; then
  require_command bd
fi

cd "$root"

if [ "$init_beads" = "yes" ] && [ "$init_git_repository" != "yes" ] && [ ! -d "$root/.git" ]; then
  die "beads requires a git repository; enable git init or disable beads"
fi

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
fi

if [ "$init_beads" = "yes" ]; then
  if [ -z "$beads_prefix" ]; then
    beads_prefix="$project_slug"
  fi

  if [ -z "$beads_prefix" ]; then
    die "beads prefix is empty; provide beads_prefix or project_slug"
  fi

  cmd=(bd init --stealth -p "$beads_prefix")
  log "Run beads init"
  printf '%q ' "${cmd[@]}"
  printf '\n'

  if [ "${DRY_RUN:-0}" != "1" ]; then
    "${cmd[@]}"
  fi
fi

if [ "${DRY_RUN:-0}" != "1" ]; then
  append_project_agents_overlay "$root/AGENTS.md" "$init_beads"
fi

if [ -z "$template_src_path" ] || [ ! -f "$template_src_path/.github/workflows/ci.yml" ]; then
  die "template source path does not contain .github/workflows/ci.yml"
fi

if [ "${DRY_RUN:-0}" != "1" ]; then
  install -D -m 0644 "$template_src_path/.github/workflows/ci.yml" "$root/.github/workflows/ci.yml"
fi
