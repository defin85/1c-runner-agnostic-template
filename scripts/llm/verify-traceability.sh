#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
changes_dir="$root/openspec/changes"

if [ ! -d "$changes_dir" ]; then
  printf 'error: changes directory not found: %s\n' "$changes_dir" >&2
  printf 'hint: run openspec init in the project root\n' >&2
  exit 1
fi

status=0

while IFS= read -r change_dir; do
  [ "$change_dir" = "$changes_dir" ] && continue
  spec_count="$(find "$change_dir/specs" -mindepth 2 -maxdepth 2 -type f -name spec.md 2>/dev/null | wc -l | tr -d ' ')"

  if [ ! -f "$change_dir/proposal.md" ]; then
    printf 'missing proposal.md: %s\n' "$change_dir" >&2
    status=1
  fi

  if [ "$spec_count" -eq 0 ]; then
    printf 'missing capability spec delta under specs/*/spec.md: %s\n' "$change_dir" >&2
    status=1
  fi

  if [ ! -f "$change_dir/tasks.md" ]; then
    printf 'missing tasks.md: %s\n' "$change_dir" >&2
    status=1
  fi

  if [ ! -f "$change_dir/traceability.md" ]; then
    printf 'missing traceability.md: %s\n' "$change_dir" >&2
    status=1
  fi
done < <(find "$changes_dir" -mindepth 1 -maxdepth 1 -type d ! -name archive | sort)

if [ "$status" -eq 0 ]; then
  log "Traceability layout looks consistent"
fi

exit "$status"
