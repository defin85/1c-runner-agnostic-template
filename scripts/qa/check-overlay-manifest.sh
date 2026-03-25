#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
manifest="$root/automation/context/template-managed-paths.txt"
expected_file="$(mktemp)"
actual_file="$(mktemp)"
trap 'rm -f "$expected_file" "$actual_file"' EXIT

[ -f "$manifest" ] || die "overlay manifest is missing: $manifest"

if [ ! -f "$root/automation/context/template-source-project-map.md" ]; then
  if awk '
    /^(openspec\/|tooling\/|AGENTS\.md$|README\.md$|copier\.yml$)/ { exit 0 }
    /^src\// && $0 != "src/AGENTS.md" { exit 0 }
    END { exit 1 }
  ' "$manifest"; then
    printf 'generated-project overlay manifest must not manage source-only or project-owned paths\n' >&2
    exit 1
  fi

  log "Generated-project overlay manifest looks safe"
  exit 0
fi

git -C "$root" ls-files --cached --others --exclude-standard \
  | awk '
      /^\[\[\[ _copier_conf\.answers_file \]\]\]$/ { next }
      /^AGENTS\.md$/ { next }
      /^CLAUDE\.md$/ { next }
      /^README\.md$/ { next }
      /^copier\.yml$/ { next }
      /^openspec\// { next }
      /^\.claude\/commands\// { next }
      /^tooling\// { next }
      /^automation\/context\/template-source-(metadata-index\.json|project-map\.md|source-files\.txt|tree\.txt)$/ { next }
      /^src\// && $0 != "src/AGENTS.md" { next }
      { print }
    ' \
  | LC_ALL=C sort >"$expected_file"

sed \
  -e '/^[[:space:]]*#/d' \
  -e '/^[[:space:]]*$/d' \
  "$manifest" \
  | LC_ALL=C sort >"$actual_file"

if ! diff -u "$expected_file" "$actual_file"; then
  printf 'overlay manifest drift detected: %s\n' "$manifest" >&2
  exit 1
fi

log "Overlay manifest matches tracked template-managed files"
