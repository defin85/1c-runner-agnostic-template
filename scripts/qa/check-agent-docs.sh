#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
status=0

require_markdown_link() {
  local rel="$1"
  local target="$2"

  if ! grep -Fq -- "]($target)" "$root/$rel"; then
    printf 'missing required markdown link in %s: %s\n' "$rel" "$target" >&2
    status=1
  fi
}

require_path() {
  local rel="$1"
  if [ ! -e "$root/$rel" ]; then
    printf 'missing agent-facing path: %s\n' "$rel" >&2
    status=1
  fi
}

require_contains() {
  local rel="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$root/$rel"; then
    printf 'missing expected text in %s: %s\n' "$rel" "$expected" >&2
    status=1
  fi
}

normalize_markdown_anchor() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[`"]//g; s/[[:space:]]+/-/g; s/[^a-z0-9._-]//g; s/-+/-/g; s/^-//; s/-$//'
}

anchor_exists() {
  local target_file="$1"
  local anchor="$2"
  local normalized

  normalized="$(normalize_markdown_anchor "$anchor")"
  if [ -z "$normalized" ]; then
    return 1
  fi

  while IFS= read -r heading; do
    heading="$(printf '%s' "$heading" | sed -E 's/^#{1,6}[[:space:]]+//')"
    if [ "$(normalize_markdown_anchor "$heading")" = "$normalized" ]; then
      return 0
    fi
  done < <(grep -E '^#{1,6}[[:space:]]+' "$target_file" || true)

  return 1
}

check_markdown_links() {
  local rel="$1"
  local abs="$root/$rel"
  local base_dir
  base_dir="$(dirname "$abs")"

  while IFS= read -r match; do
    [ -z "$match" ] && continue

    local line="${match%%:*}"
    local link="${match#*:}"
    local target="${link#*](}"
    target="${target%)}"

    case "$link" in
      !*) continue ;;
    esac

    case "$target" in
      http://*|https://*|mailto:*|tel:*) continue ;;
    esac

    local target_path="$target"
    local anchor=""
    if [[ "$target" == *"#"* ]]; then
      target_path="${target%%#*}"
      anchor="${target#*#}"
    fi

    local resolved_path
    if [ -z "$target_path" ]; then
      resolved_path="$abs"
    else
      resolved_path="$(canonical_path "$base_dir/$target_path")"
    fi

    if [ ! -e "$resolved_path" ]; then
      printf 'broken markdown link in %s:%s: %s\n' "$rel" "$line" "$target" >&2
      status=1
      continue
    fi

    if [ -n "$anchor" ] && { [ ! -f "$resolved_path" ] || ! anchor_exists "$resolved_path" "$anchor"; }; then
      printf 'missing markdown anchor in %s:%s: %s\n' "$rel" "$line" "$target" >&2
      status=1
    fi
  done < <(grep -nEo '!\[[^][]*\]\([^)]*\)|\[[^][]+\]\([^)]*\)' "$abs" || true)
}

check_no_line_specific_links() {
  local rel="$1"
  if grep -nE '\]\([^)]*(#L[0-9]+|:[0-9]+)\)' "$root/$rel" >/dev/null; then
    printf 'line-specific links are not allowed in durable docs: %s\n' "$rel" >&2
    status=1
  fi
}

is_source_repo() {
  [ -f "$root/openspec/specs/agent-runtime-toolkit/spec.md" ] && \
    [ -f "$root/openspec/specs/project-scoped-skills/spec.md" ] && \
    [ -f "$root/openspec/specs/template-ci-contours/spec.md" ]
}

require_no_placeholder_pattern() {
  local rel="$1"
  local pattern="$2"

  if grep -nE -- "$pattern" "$root/$rel" >/dev/null; then
    printf 'unexpected placeholder or template note in %s: %s\n' "$rel" "$pattern" >&2
    status=1
  fi
}

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/agent/index.md \
  docs/agent/architecture.md \
  docs/agent/generated-project-index.md \
  docs/agent/generated-project-verification.md \
  docs/agent/source-vs-generated.md \
  docs/agent/verify.md \
  docs/agent/review.md \
  docs/template-maintenance.md \
  docs/exec-plans/README.md \
  docs/exec-plans/active/.gitkeep \
  docs/exec-plans/completed/.gitkeep \
  .codex/README.md \
  .agents/skills/README.md \
  .claude/skills/README.md \
  automation/context/templates/generated-project-project-map.md \
  automation/context/templates/generated-project-metadata-index.json; do
  require_path "$rel"
done

require_markdown_link "docs/README.md" "agent/index.md"
require_markdown_link "docs/agent/index.md" "../../AGENTS.md"
require_markdown_link "docs/agent/index.md" "architecture.md"
require_markdown_link "docs/agent/index.md" "generated-project-index.md"
require_markdown_link "docs/agent/index.md" "source-vs-generated.md"
require_markdown_link "docs/agent/index.md" "verify.md"
require_markdown_link "docs/agent/index.md" "review.md"
require_markdown_link "docs/agent/index.md" "../template-maintenance.md"
require_markdown_link "docs/agent/index.md" "../exec-plans/README.md"
require_markdown_link "docs/agent/index.md" "../../.agents/skills/README.md"
require_markdown_link "docs/agent/index.md" "../../.codex/README.md"
require_markdown_link ".codex/README.md" "../docs/agent/index.md"
require_markdown_link ".codex/README.md" "../docs/agent/generated-project-index.md"
require_markdown_link ".codex/README.md" "../.agents/skills/README.md"
require_markdown_link ".agents/skills/README.md" "../../.claude/skills/README.md"
require_markdown_link ".claude/skills/README.md" "../../.agents/skills/README.md"
require_contains "docs/agent/index.md" "docs/agent/architecture.md"
require_contains "docs/agent/index.md" "docs/agent/generated-project-index.md"
require_contains "docs/agent/index.md" "docs/agent/source-vs-generated.md"
require_contains "docs/agent/index.md" "docs/agent/verify.md"
require_contains "docs/agent/index.md" "docs/agent/review.md"
require_contains "docs/agent/index.md" "docs/exec-plans/README.md"
require_contains "docs/agent/generated-project-index.md" "seed-once / project-owned"
require_contains "docs/agent/generated-project-index.md" "generated-derived"
require_contains "docs/agent/generated-project-index.md" "copier update"
require_contains "docs/agent/source-vs-generated.md" "template-managed"
require_contains "docs/agent/source-vs-generated.md" "generated-derived"
require_contains "docs/agent/verify.md" "make agent-verify"
require_contains "docs/agent/generated-project-verification.md" "Safe Local"
require_contains "docs/agent/generated-project-verification.md" "make export-context-preview"
require_contains "docs/agent/generated-project-verification.md" "make export-context-check"
require_contains "docs/agent/generated-project-verification.md" "Profile-Required"
require_contains "docs/agent/generated-project-verification.md" "Provisioned / Self-Hosted 1C"
require_contains "docs/agent/generated-project-verification.md" "./scripts/llm/export-context.sh --write"
require_contains "docs/template-maintenance.md" "template maintenance"
require_contains "docs/template-maintenance.md" "make template-check-update"
require_contains "docs/template-maintenance.md" "make template-update"
require_contains "docs/template-maintenance.md" "./scripts/template/check-update.sh"
require_contains "docs/template-maintenance.md" "./scripts/template/update-template.sh"
require_contains "docs/template-maintenance.md" "./scripts/llm/export-context.sh --write"
require_contains "docs/template-maintenance.md" "tests/smoke/copier-update-ready.sh"
require_contains ".agents/skills/README.md" ".claude/skills/"
require_contains ".claude/skills/README.md" ".agents/skills/"

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/agent/index.md \
  docs/agent/architecture.md \
  docs/agent/generated-project-index.md \
  docs/agent/generated-project-verification.md \
  docs/agent/source-vs-generated.md \
  docs/agent/verify.md \
  docs/agent/review.md \
  docs/template-maintenance.md \
  docs/exec-plans/README.md \
  .codex/README.md \
  .agents/skills/README.md \
  .claude/skills/README.md; do
  check_no_line_specific_links "$rel"
  check_markdown_links "$rel"
done

if is_source_repo; then
  require_markdown_link "AGENTS.md" "docs/agent/index.md"
  require_markdown_link "AGENTS.md" "docs/agent/architecture.md"
  require_markdown_link "AGENTS.md" "docs/agent/verify.md"
  require_markdown_link "AGENTS.md" "docs/exec-plans/README.md"
  require_markdown_link "README.md" "docs/agent/index.md"
  require_markdown_link "README.md" "docs/template-maintenance.md"
  require_contains "README.md" "1c-runner-agnostic-template"
  require_contains "README.md" "automation/context/templates/"

  for rel in \
    automation/context/template-source-project-map.md \
    automation/context/template-source-metadata-index.json \
    automation/context/template-source-tree.txt \
    automation/context/template-source-source-files.txt; do
    require_path "$rel"
  done

  if grep -RInE '\{\{|<описание|<context-|Обновите этот файл' \
    --exclude='template-source-tree.txt' \
    --exclude='template-source-source-files.txt' \
    --exclude-dir='templates' \
    "$root/automation/context" >/dev/null; then
    printf 'live automation context contains placeholders or template notes\n' >&2
    status=1
  fi

  if ! "$root/scripts/llm/export-context.sh" --check; then
    status=1
  fi
else
  for rel in \
    automation/context/project-map.md \
    automation/context/source-tree.generated.txt \
    automation/context/metadata-index.generated.json \
    openspec/project.md; do
    require_path "$rel"
  done

  require_markdown_link "AGENTS.md" "docs/agent/generated-project-index.md"
  require_markdown_link "AGENTS.md" "automation/context/project-map.md"
  require_markdown_link "AGENTS.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "AGENTS.md" "docs/template-maintenance.md"
  require_markdown_link "README.md" "docs/agent/generated-project-index.md"
  require_markdown_link "README.md" "automation/context/project-map.md"
  require_markdown_link "README.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "README.md" "docs/template-maintenance.md"

  require_contains "AGENTS.md" "generated 1С-project"
  require_contains "AGENTS.md" "generated-project-first onboarding path"
  require_contains "README.md" "generated 1С-проект"
  require_contains "README.md" "Ownership Classes"
  require_contains "automation/context/project-map.md" "Ownership Model"
  require_contains "automation/context/project-map.md" "generated-derived"
  require_contains "openspec/project.md" "generated 1С-проект"

  require_no_placeholder_pattern "README.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "automation/context/project-map.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "openspec/project.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "README.md" 'template source repo'
  require_no_placeholder_pattern "automation/context/project-map.md" 'template source repo'

  if ! "$root/scripts/llm/export-context.sh" --check; then
    status=1
  fi
fi

if [ "$status" -eq 0 ]; then
  log "Agent-facing docs and context look consistent"
fi

exit "$status"
