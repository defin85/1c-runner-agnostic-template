#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command find

root="$(project_root)"
context_dir="$root/automation/context"
tree_file="$context_dir/template-source-tree.txt"
source_file="$context_dir/template-source-source-files.txt"
check_mode="${1:-}"

ensure_dir "$context_dir"

if [ -n "$check_mode" ] && [ "$check_mode" != "--check" ]; then
  die "usage: ./scripts/llm/export-context.sh [--check]"
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
tmp_tree="$tmpdir/template-source-tree.txt"
tmp_source="$tmpdir/template-source-source-files.txt"

{
  printf '# Template Source Tree\n\n'
  find "$root" -maxdepth 3 -type d \
    ! -path "$root/.git" \
    ! -path "$root/.git/*" \
    ! -path "$root/.beads" \
    ! -path "$root/.beads/*" \
    | sed "s|^$root|.|" \
    | LC_ALL=C sort
} >"$tmp_tree"

{
  printf '# Template Source Files\n\n'
  for path in AGENTS.md README.md Makefile copier.yml .agents .claude .codex .github automation docs env features openspec scripts src tests; do
    if [ -d "$root/$path" ]; then
      find "$root/$path" -type f
    elif [ -f "$root/$path" ]; then
      printf '%s\n' "$root/$path"
    fi
  done | sed "s|^$root/|./|" | LC_ALL=C sort -u
} >"$tmp_source"

if [ "$check_mode" = "--check" ]; then
  status=0

  for pair in "$tree_file:$tmp_tree" "$source_file:$tmp_source"; do
    target="${pair%%:*}"
    expected="${pair##*:}"

    if [ ! -f "$target" ]; then
      printf 'missing context file: %s\n' "$target" >&2
      status=1
      continue
    fi

    if ! cmp -s "$target" "$expected"; then
      printf 'stale context file: %s\n' "$target" >&2
      status=1
    fi
  done

  exit "$status"
fi

install -D -m 0644 "$tmp_tree" "$tree_file"
install -D -m 0644 "$tmp_source" "$source_file"

log "Wrote context files"
printf '%s\n' "$tree_file"
printf '%s\n' "$source_file"
