#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command find
require_command rg

root="$(project_root)"
context_dir="$root/automation/context"
tree_file="$context_dir/generated-project-tree.txt"
source_file="$context_dir/generated-source-files.txt"

ensure_dir "$context_dir"

{
  printf 'Generated at: %s\n' "$(date -Iseconds)"
  printf 'Root: %s\n' "$root"
  printf '\n'
  find "$root" -maxdepth 3 -type d | sort
} >"$tree_file"

{
  printf 'Generated at: %s\n' "$(date -Iseconds)"
  printf 'Root: %s\n' "$root"
  printf '\n'
  if [ -d "$root/openspec" ]; then
    rg --files "$root/src" "$root/tests" "$root/features" "$root/openspec" | sort
  else
    rg --files "$root/src" "$root/tests" "$root/features" | sort
  fi
} >"$source_file"

log "Wrote context files"
printf '%s\n' "$tree_file"
printf '%s\n' "$source_file"
