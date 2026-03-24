#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command find

root="$(project_root)"
context_dir="$root/automation/context"
mode="${1:---help}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/llm/export-context.sh --help
  ./scripts/llm/export-context.sh --preview
  ./scripts/llm/export-context.sh --check
  ./scripts/llm/export-context.sh --write

Modes:
  --help     Show this contract and exit without writing files.
  --preview  Print the would-be context artifacts to stdout without writing files.
  --check    Compare checked-in context artifacts with freshly rendered output.
  --write    Refresh checked-in context artifacts in place.

Repo behavior:
  - Template source repo refreshes automation/context/template-source-tree.txt
    and automation/context/template-source-source-files.txt.
  - Generated repo refreshes automation/context/source-tree.generated.txt
    and automation/context/metadata-index.generated.json.
EOF
}

is_source_repo() {
  [ -f "$root/openspec/specs/agent-runtime-toolkit/spec.md" ] && \
    [ -f "$root/openspec/specs/project-scoped-skills/spec.md" ] && \
    [ -f "$root/openspec/specs/template-ci-contours/spec.md" ]
}

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

render_source_tree() {
  {
    printf '# Template Source Tree\n\n'
    find "$root" -maxdepth 3 -type d \
      ! -path "$root/.git" \
      ! -path "$root/.git/*" \
      ! -path "$root/.beads" \
      ! -path "$root/.beads/*" \
      | sed "s|^$root|.|" \
      | LC_ALL=C sort
  } >"$1"
}

render_source_files() {
  {
    printf '# Template Source Files\n\n'
    for path in AGENTS.md README.md Makefile copier.yml .agents .claude .codex .github automation docs env features openspec scripts src tests; do
      if [ -d "$root/$path" ]; then
        find "$root/$path" -type f
      elif [ -f "$root/$path" ]; then
        printf '%s\n' "$root/$path"
      fi
    done | sed "s|^$root/|./|" | LC_ALL=C sort -u
  } >"$1"
}

render_generated_tree() {
  {
    printf '# Generated Project Tree\n\n'
    find "$root" -maxdepth 4 \( -type d -o -type f \) \
      ! -path "$root/.git" \
      ! -path "$root/.git/*" \
      ! -path "$root/.beads" \
      ! -path "$root/.beads/*" \
      ! -path "$root/.agent-browser" \
      ! -path "$root/.agent-browser/*" \
      ! -path "$root/automation/context/source-tree.generated.txt" \
      ! -path "$root/automation/context/metadata-index.generated.json" \
      ! -path "$root/env/.local" \
      ! -path "$root/env/.local/*" \
      | sed "s|^$root|.|" \
      | LC_ALL=C sort
  } >"$1"
}

list_top_level_entries() {
  local rel="$1"

  if [ ! -d "$root/$rel" ]; then
    return 0
  fi

  find "$root/$rel" -mindepth 1 -maxdepth 1 \( -type d -o -type f \) -printf '%f\n' \
    | LC_ALL=C sort
}

count_files() {
  local rel="$1"

  if [ ! -d "$root/$rel" ]; then
    printf '0'
    return 0
  fi

  find "$root/$rel" -type f | wc -l | tr -d ' '
}

count_dirs() {
  local rel="$1"

  if [ ! -d "$root/$rel" ]; then
    printf '0'
    return 0
  fi

  find "$root/$rel" -type d | wc -l | tr -d ' '
}

write_json_array_from_stdin() {
  local first=1
  local line

  printf '['
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if [ "$first" -eq 0 ]; then
      printf ', '
    fi
    first=0
    printf '"%s"' "$(json_escape "$line")"
  done
  printf ']'
}

configuration_name() {
  local config_xml="$root/src/cf/Configuration.xml"

  if [ ! -f "$config_xml" ]; then
    return 0
  fi

  sed -n 's/.*name="\([^"]*\)".*/\1/p' "$config_xml" | head -n 1
}

render_generated_metadata() {
  local target_file="$1"
  local config_name

  config_name="$(configuration_name)"

  {
    printf '{\n'
    printf '  "repositoryRole": "generated-project",\n'
    printf '  "inventoryRole": "generated-derived",\n'
    printf '  "authoritativeDocs": {\n'
    printf '    "generatedProjectIndex": "docs/agent/generated-project-index.md",\n'
    printf '    "projectMap": "automation/context/project-map.md",\n'
    printf '    "verification": "docs/agent/generated-project-verification.md",\n'
    printf '    "templateMaintenance": "docs/template-maintenance.md"\n'
    printf '  },\n'
    printf '  "configuration": {\n'
    printf '    "xmlPath": "src/cf/Configuration.xml",\n'
    printf '    "name": "%s"\n' "$(json_escape "$config_name")"
    printf '  },\n'
    printf '  "sourceRoots": {\n'
    printf '    "configuration": "src/cf",\n'
    printf '    "extensions": "src/cfe",\n'
    printf '    "externalProcessors": "src/epf",\n'
    printf '    "reports": "src/erf"\n'
    printf '  },\n'
    printf '  "topLevelEntries": {\n'
    printf '    "cf": '
    list_top_level_entries "src/cf" | write_json_array_from_stdin
    printf ',\n'
    printf '    "cfe": '
    list_top_level_entries "src/cfe" | write_json_array_from_stdin
    printf ',\n'
    printf '    "epf": '
    list_top_level_entries "src/epf" | write_json_array_from_stdin
    printf ',\n'
    printf '    "erf": '
    list_top_level_entries "src/erf" | write_json_array_from_stdin
    printf '\n'
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "cf": { "files": %s, "dirs": %s },\n' "$(count_files "src/cf")" "$(count_dirs "src/cf")"
    printf '    "cfe": { "files": %s, "dirs": %s },\n' "$(count_files "src/cfe")" "$(count_dirs "src/cfe")"
    printf '    "epf": { "files": %s, "dirs": %s },\n' "$(count_files "src/epf")" "$(count_dirs "src/epf")"
    printf '    "erf": { "files": %s, "dirs": %s }\n' "$(count_files "src/erf")" "$(count_dirs "src/erf")"
    printf '  }\n'
    printf '}\n'
  } >"$target_file"
}

preview_targets() {
  local pair target_file rendered_file

  for pair in "$@"; do
    target_file="${pair%%:*}"
    rendered_file="${pair##*:}"
    printf '=== %s ===\n' "${target_file#$root/}"
    cat "$rendered_file"
    printf '\n'
  done
}

check_targets() {
  local status=0
  local pair target_file rendered_file

  for pair in "$@"; do
    target_file="${pair%%:*}"
    rendered_file="${pair##*:}"

    if [ ! -f "$target_file" ]; then
      printf 'missing context file: %s\n' "$target_file" >&2
      status=1
      continue
    fi

    if ! cmp -s "$target_file" "$rendered_file"; then
      printf 'stale context file: %s\n' "$target_file" >&2
      status=1
    fi
  done

  return "$status"
}

write_targets() {
  local pair target_file rendered_file

  for pair in "$@"; do
    target_file="${pair%%:*}"
    rendered_file="${pair##*:}"
    install -D -m 0644 "$rendered_file" "$target_file"
    printf '%s\n' "$target_file"
  done
}

case "$mode" in
  --help|--preview|--check|--write) ;;
  *)
    die "unknown mode: $mode"
    ;;
esac

if [ "$mode" = "--help" ]; then
  usage
  exit 0
fi

ensure_dir "$context_dir"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

if is_source_repo; then
  repo_role="template-source"
  tree_file="$context_dir/template-source-tree.txt"
  source_file="$context_dir/template-source-source-files.txt"
  tmp_tree="$tmpdir/template-source-tree.txt"
  tmp_source="$tmpdir/template-source-source-files.txt"

  render_source_tree "$tmp_tree"
  render_source_files "$tmp_source"

  targets=(
    "$tree_file:$tmp_tree"
    "$source_file:$tmp_source"
  )
else
  repo_role="generated-project"
  tree_file="$context_dir/source-tree.generated.txt"
  metadata_file="$context_dir/metadata-index.generated.json"
  tmp_tree="$tmpdir/source-tree.generated.txt"
  tmp_metadata="$tmpdir/metadata-index.generated.json"

  render_generated_tree "$tmp_tree"
  render_generated_metadata "$tmp_metadata"

  targets=(
    "$tree_file:$tmp_tree"
    "$metadata_file:$tmp_metadata"
  )
fi

case "$mode" in
  --preview)
    log "Preview context artifacts for $repo_role"
    preview_targets "${targets[@]}"
    ;;
  --check)
    check_targets "${targets[@]}"
    ;;
  --write)
    log "Wrote context artifacts for $repo_role"
    write_targets "${targets[@]}"
    ;;
esac
