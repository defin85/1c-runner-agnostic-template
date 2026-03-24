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

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/agent/index.md \
  docs/agent/architecture.md \
  docs/agent/source-vs-generated.md \
  docs/agent/verify.md \
  docs/agent/review.md \
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

require_markdown_link "AGENTS.md" "docs/agent/index.md"
require_markdown_link "AGENTS.md" "docs/agent/architecture.md"
require_markdown_link "AGENTS.md" "docs/agent/verify.md"
require_markdown_link "AGENTS.md" "docs/exec-plans/README.md"
require_markdown_link "README.md" "docs/agent/index.md"
require_markdown_link "docs/README.md" "agent/index.md"
require_markdown_link "docs/agent/index.md" "../../AGENTS.md"
require_markdown_link "docs/agent/index.md" "architecture.md"
require_markdown_link "docs/agent/index.md" "source-vs-generated.md"
require_markdown_link "docs/agent/index.md" "verify.md"
require_markdown_link "docs/agent/index.md" "review.md"
require_markdown_link "docs/agent/index.md" "../exec-plans/README.md"
require_markdown_link "docs/agent/index.md" "../../.agents/skills/README.md"
require_markdown_link "docs/agent/index.md" "../../.codex/README.md"
require_markdown_link ".codex/README.md" "../docs/agent/index.md"
require_markdown_link ".codex/README.md" "../.agents/skills/README.md"
require_markdown_link ".agents/skills/README.md" "../../.claude/skills/README.md"
require_markdown_link ".claude/skills/README.md" "../../.agents/skills/README.md"
require_contains "README.md" "template source repo"
require_contains "README.md" "automation/context/templates/"
require_contains "docs/agent/index.md" "docs/agent/architecture.md"
require_contains "docs/agent/index.md" "docs/agent/source-vs-generated.md"
require_contains "docs/agent/index.md" "docs/agent/verify.md"
require_contains "docs/agent/index.md" "docs/agent/review.md"
require_contains "docs/agent/index.md" "docs/exec-plans/README.md"
require_contains "docs/agent/verify.md" "make agent-verify"
require_contains ".agents/skills/README.md" ".claude/skills/"
require_contains ".claude/skills/README.md" ".agents/skills/"

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/agent/index.md \
  docs/agent/architecture.md \
  docs/agent/source-vs-generated.md \
  docs/agent/verify.md \
  docs/agent/review.md \
  docs/exec-plans/README.md \
  .codex/README.md \
  .agents/skills/README.md \
  .claude/skills/README.md; do
  check_no_line_specific_links "$rel"
  check_markdown_links "$rel"
done

if is_source_repo; then
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
fi

if [ "$status" -eq 0 ]; then
  log "Agent-facing docs and context look consistent"
fi

exit "$status"
