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
    automation/context/metadata-index.generated.json,
    and automation/context/hotspots-summary.generated.md.
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
    if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      for path in AGENTS.md README.md Makefile copier.yml .agents .claude .codex .github automation docs env features openspec scripts src tests; do
        git -C "$root" ls-files -- "$path"
      done | sed 's|^|./|' | LC_ALL=C sort -u
    else
      for path in AGENTS.md README.md Makefile copier.yml .agents .claude .codex .github automation docs env features openspec scripts src tests; do
        if [ -d "$root/$path" ]; then
          find "$root/$path" -type f
        elif [ -f "$root/$path" ]; then
          printf '%s\n' "$root/$path"
        fi
      done | sed "s|^$root/|./|" | LC_ALL=C sort -u
    fi
  } >"$1"
}

is_generated_local_private_relpath() {
  local relpath="$1"

  case "$relpath" in
    ./env/local.json|./env/wsl.json|./env/ci.json|./env/windows-executor.json)
      return 0
      ;;
    ./env/.local|./env/.local/*)
      return 0
      ;;
    ./.codex/*)
      case "$relpath" in
        ./.codex/.gitkeep|./.codex/README.md|./.codex/config.toml)
          return 1
          ;;
        *)
          return 0
          ;;
      esac
      ;;
  esac

  return 1
}

emit_generated_tree_entries() {
  local relpath

  while IFS= read -r relpath; do
    [ -n "$relpath" ] || continue

    if is_generated_local_private_relpath "$relpath"; then
      continue
    fi

    printf '%s\n' "$relpath"
  done < <(
    find "$root" -maxdepth 4 \( -type d -o -type f \) \
      ! -path "$root/.git" \
      ! -path "$root/.git/*" \
      ! -path "$root/.beads" \
      ! -path "$root/.beads/*" \
      ! -path "$root/.agent-browser" \
      ! -path "$root/.agent-browser/*" \
      ! -path "$root/automation/context/source-tree.generated.txt" \
      ! -path "$root/automation/context/metadata-index.generated.json" \
      ! -path "$root/automation/context/hotspots-summary.generated.md" \
      | sed "s|^$root|.|" \
      | LC_ALL=C sort
  )
}

render_generated_tree() {
  {
    printf '# Generated Project Tree\n\n'
    emit_generated_tree_entries
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
  local attr_name=""

  if [ ! -f "$config_xml" ]; then
    return 0
  fi

  attr_name="$(sed -n 's/.*name="\([^"]*\)".*/\1/p' "$config_xml" | head -n 1)"
  if [ -n "$attr_name" ]; then
    printf '%s' "$attr_name"
    return 0
  fi

  sed -n 's/.*<Name>\([^<]*\)<\/Name>.*/\1/p' "$config_xml" | head -n 1
}

configuration_attr() {
  local attr="$1"
  local config_xml="$root/src/cf/Configuration.xml"

  if [ ! -f "$config_xml" ]; then
    return 0
  fi

  {
    grep -o "${attr}=\"[^\"]*\"" "$config_xml" || true
  } | head -n 1 | sed -e "s/^${attr}=\"//" -e 's/\"$//'
}

list_inventory_entries() {
  local rel="$1"

  if [ ! -d "$root/$rel" ]; then
    return 0
  fi

  find "$root/$rel" -mindepth 1 -maxdepth 1 \( -type d -o -type f \) \
    | sed "s|^$root/||" \
    | LC_ALL=C sort
}

count_inventory_entries() {
  local rel="$1"

  list_inventory_entries "$rel" | awk 'END { print NR + 0 }'
}

file_checksum() {
  local path="$1"

  require_command cksum
  cksum "$path" | awk '{printf "%s/%s", $1, $2}'
}

emit_markdown_examples() {
  local rel="$1"
  local limit="${2:-3}"
  local entry=""
  local count=0

  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    printf -- '- `%s`\n' "$entry"
    count=$((count + 1))
    if [ "$count" -ge "$limit" ]; then
      return 0
    fi
  done < <(list_inventory_entries "$rel")

  if [ "$count" -eq 0 ]; then
    printf -- '- none\n'
  fi
}

render_generated_metadata() {
  local target_file="$1"
  local config_name
  local config_uuid
  local has_config_xml="false"

  if [ -f "$root/src/cf/Configuration.xml" ]; then
    has_config_xml="true"
  fi

  config_name="$(configuration_name)"
  config_uuid="$(configuration_attr uuid)"

  {
    printf '{\n'
    printf '  "repositoryRole": "generated-project",\n'
    printf '  "inventoryRole": "generated-derived",\n'
    printf '  "authoritativeDocs": {\n'
    printf '    "generatedProjectIndex": "docs/agent/generated-project-index.md",\n'
    printf '    "projectMap": "automation/context/project-map.md",\n'
    printf '    "verification": "docs/agent/generated-project-verification.md",\n'
    printf '    "review": "docs/agent/review.md",\n'
    printf '    "envReadme": "env/README.md",\n'
    printf '    "runtimeProfilePolicy": "automation/context/runtime-profile-policy.json",\n'
    printf '    "runtimeSupportMatrixJson": "automation/context/runtime-support-matrix.json",\n'
    printf '    "runtimeSupportMatrixMarkdown": "automation/context/runtime-support-matrix.md",\n'
    printf '    "hotspotsSummary": "automation/context/hotspots-summary.generated.md",\n'
    printf '    "skills": ".agents/skills/README.md",\n'
    printf '    "codexGuide": ".codex/README.md",\n'
    printf '    "executionPlans": "docs/exec-plans/README.md",\n'
    printf '    "templateMaintenance": "docs/template-maintenance.md"\n'
    printf '  },\n'
    printf '  "configuration": {\n'
    printf '    "xmlPath": "src/cf/Configuration.xml",\n'
    printf '    "present": %s,\n' "$has_config_xml"
    printf '    "name": "%s",\n' "$(json_escape "$config_name")"
    printf '    "uuid": "%s"\n' "$(json_escape "$config_uuid")"
    printf '  },\n'
    printf '  "sourceRoots": {\n'
    printf '    "configuration": "src/cf",\n'
    printf '    "extensions": "src/cfe",\n'
    printf '    "externalProcessors": "src/epf",\n'
    printf '    "reports": "src/erf"\n'
    printf '  },\n'
    printf '  "entrypointInventory": {\n'
    printf '    "configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"],\n'
    printf '    "httpServices": '
    list_inventory_entries "src/cf/HTTPServices" | write_json_array_from_stdin
    printf ',\n'
    printf '    "webServices": '
    list_inventory_entries "src/cf/WebServices" | write_json_array_from_stdin
    printf ',\n'
    printf '    "scheduledJobs": '
    list_inventory_entries "src/cf/ScheduledJobs" | write_json_array_from_stdin
    printf ',\n'
    printf '    "commonModules": '
    list_inventory_entries "src/cf/CommonModules" | write_json_array_from_stdin
    printf ',\n'
    printf '    "subsystems": '
    list_inventory_entries "src/cf/Subsystems" | write_json_array_from_stdin
    printf ',\n'
    printf '    "extensions": '
    list_inventory_entries "src/cfe" | write_json_array_from_stdin
    printf ',\n'
    printf '    "externalProcessors": '
    list_inventory_entries "src/epf" | write_json_array_from_stdin
    printf ',\n'
    printf '    "reports": '
    list_inventory_entries "src/erf" | write_json_array_from_stdin
    printf '\n'
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

render_generated_hotspots_summary() {
  local target_file="$1"
  local metadata_file="$2"
  local tree_file="$3"
  local config_name=""
  local config_uuid=""
  local metadata_checksum=""
  local tree_checksum=""

  config_name="$(configuration_name)"
  config_uuid="$(configuration_attr uuid)"
  metadata_checksum="$(file_checksum "$metadata_file")"
  tree_checksum="$(file_checksum "$tree_file")"

  if [ -z "$config_name" ]; then
    config_name="(unknown)"
  fi

  {
    printf '# Generated Hotspots Summary\n\n'
    printf 'Этот файл является generated-derived summary-first картой для первого часа работы агента.\n'
    printf 'Raw inventory остаётся в `automation/context/metadata-index.generated.json`, а curated truth — в `automation/context/project-map.md`.\n\n'

    printf '## Identity\n\n'
    printf -- '- Repository role: `generated-project`\n'
    printf -- '- Configuration name: `%s`\n' "$config_name"
    printf -- '- Configuration UUID: `%s`\n' "${config_uuid:-unknown}"
    printf -- '- Configuration XML: `%s`\n' "$( [ -f "$root/src/cf/Configuration.xml" ] && printf 'present' || printf 'missing' )"

    printf '\n## Freshness\n\n'
    printf -- '- Refresh command: `./scripts/llm/export-context.sh --write`\n'
    printf -- '- Check command: `./scripts/llm/export-context.sh --check`\n'
    printf -- '- `metadata-index.generated.json` checksum: `%s`\n' "$metadata_checksum"
    printf -- '- `source-tree.generated.txt` checksum: `%s`\n' "$tree_checksum"

    printf '\n## High-Signal Counts\n\n'
    printf '| Area | Count |\n'
    printf '| --- | ---: |\n'
    printf '| HTTP services | %s |\n' "$(count_inventory_entries "src/cf/HTTPServices")"
    printf '| Web services | %s |\n' "$(count_inventory_entries "src/cf/WebServices")"
    printf '| Scheduled jobs | %s |\n' "$(count_inventory_entries "src/cf/ScheduledJobs")"
    printf '| Common modules | %s |\n' "$(count_inventory_entries "src/cf/CommonModules")"
    printf '| Subsystems | %s |\n' "$(count_inventory_entries "src/cf/Subsystems")"
    printf '| Extensions | %s |\n' "$(count_inventory_entries "src/cfe")"
    printf '| External processors | %s |\n' "$(count_inventory_entries "src/epf")"
    printf '| Reports | %s |\n' "$(count_inventory_entries "src/erf")"

    printf '\n## Representative Entrypoints\n\n'
    printf '### HTTP Services\n\n'
    emit_markdown_examples "src/cf/HTTPServices"
    printf '\n### Web Services\n\n'
    emit_markdown_examples "src/cf/WebServices"
    printf '\n### Scheduled Jobs\n\n'
    emit_markdown_examples "src/cf/ScheduledJobs"
    printf '\n### Common Modules\n\n'
    emit_markdown_examples "src/cf/CommonModules"
    printf '\n### Subsystems\n\n'
    emit_markdown_examples "src/cf/Subsystems"

    printf '\n## Task-to-Path Routing\n\n'
    printf -- '- Integration and service edges -> `src/cf/HTTPServices`, `src/cf/WebServices`\n'
    printf -- '- Background and scheduled execution -> `src/cf/ScheduledJobs`\n'
    printf -- '- Shared business logic and reusable helpers -> `src/cf/CommonModules`\n'
    printf -- '- Navigation and product surface map -> `src/cf/Subsystems`\n'
    printf -- '- Extension-owned behavior -> `src/cfe`\n'
    printf -- '- External processors and reports -> `src/epf`, `src/erf`\n'

    printf '\n## Follow-Up Routers\n\n'
    printf -- '- Curated project truth: `automation/context/project-map.md`\n'
    printf -- '- Runtime profile policy: `automation/context/runtime-profile-policy.json`\n'
    printf -- '- Runtime support matrix: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`\n'
    printf -- '- Raw inventory for deeper narrowing: `automation/context/metadata-index.generated.json`\n'
    printf -- '- Verification matrix: `docs/agent/generated-project-verification.md`\n'
    printf -- '- Repeatable workflows and Codex guide: `.agents/skills/README.md`, `.codex/README.md`\n'
    printf -- '- Long-running plans: `docs/exec-plans/README.md`\n'
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
  summary_file="$context_dir/hotspots-summary.generated.md"
  tmp_tree="$tmpdir/source-tree.generated.txt"
  tmp_metadata="$tmpdir/metadata-index.generated.json"
  tmp_summary="$tmpdir/hotspots-summary.generated.md"

  render_generated_tree "$tmp_tree"
  render_generated_metadata "$tmp_metadata"
  render_generated_hotspots_summary "$tmp_summary" "$tmp_metadata" "$tmp_tree"

  targets=(
    "$tree_file:$tmp_tree"
    "$metadata_file:$tmp_metadata"
    "$summary_file:$tmp_summary"
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
