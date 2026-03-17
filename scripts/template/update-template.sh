#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_clean_git_worktree() {
  local root="$1"

  if ! git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "copier update requires a git repository"
  fi

  if [ -n "$(git -C "$root" status --porcelain)" ]; then
    die "git working tree is dirty; commit or stash changes before copier update"
  fi
}

require_command copier

root="$(project_root)"
require_clean_git_worktree "$root"
cd "$root"

cmd=(copier update --trust)

if [ "$#" -eq 0 ]; then
  cmd+=(--defaults)
else
  cmd+=("$@")
fi

log "Update project from template"
printf '%q ' "${cmd[@]}"
printf '\n'

"${cmd[@]}"
