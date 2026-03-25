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

require_absent_regex() {
  local rel="$1"
  local pattern="$2"
  local message="$3"

  if grep -Eq -- "$pattern" "$root/$rel"; then
    printf '%s: %s\n' "$message" "$rel" >&2
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

has_git_remote() {
  git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  git -C "$root" remote | grep -q .
}

check_generated_private_leaks() {
  local relpath

  while IFS= read -r relpath; do
    case "$relpath" in
      ./env/local.json|./env/wsl.json|./env/ci.json|./env/windows-executor.json)
        printf 'local-private path leaked into generated context: %s\n' "${relpath#./}" >&2
        status=1
        ;;
      ./env/.local|./env/.local/*)
        printf 'local-private path leaked into generated context: %s\n' "${relpath#./}" >&2
        status=1
        ;;
      ./.codex/*)
        case "$relpath" in
          ./.codex/.gitkeep|./.codex/README.md|./.codex/config.toml) ;;
          *)
            printf 'local-private path leaked into generated context: %s\n' "${relpath#./}" >&2
            status=1
            ;;
        esac
        ;;
    esac
  done <"$root/automation/context/source-tree.generated.txt"

  if grep -Eq '"env/(local|wsl|ci|windows-executor)\.json"|env/\.local/' \
    "$root/automation/context/metadata-index.generated.json"; then
    printf 'generated metadata leaked local-private runtime profile paths\n' >&2
    status=1
  fi
}

check_generated_metadata_contract() {
  local metadata_file="$root/automation/context/metadata-index.generated.json"

  require_contains "automation/context/metadata-index.generated.json" "\"entrypointInventory\""
  require_contains "automation/context/metadata-index.generated.json" "\"configurationRoots\""
  require_contains "automation/context/metadata-index.generated.json" "\"httpServices\""
  require_contains "automation/context/metadata-index.generated.json" "\"webServices\""
  require_contains "automation/context/metadata-index.generated.json" "\"scheduledJobs\""
  require_contains "automation/context/metadata-index.generated.json" "\"commonModules\""
  require_contains "automation/context/metadata-index.generated.json" "\"subsystems\""
  require_contains "automation/context/metadata-index.generated.json" "\"review\""
  require_contains "automation/context/metadata-index.generated.json" "\"envReadme\""
  require_contains "automation/context/metadata-index.generated.json" "\"skills\""
  require_contains "automation/context/metadata-index.generated.json" "\"codexGuide\""
  require_contains "automation/context/metadata-index.generated.json" "\"executionPlans\""

  if [ -f "$root/src/cf/Configuration.xml" ]; then
    if grep -Fq '"name": ""' "$metadata_file"; then
      printf 'generated metadata leaves configuration.name empty despite src/cf/Configuration.xml\n' >&2
      status=1
    fi

    if ! grep -Fq '"present": true' "$metadata_file"; then
      printf 'generated metadata does not mark src/cf/Configuration.xml as present\n' >&2
      status=1
    fi
  fi
}

check_generated_closeout_contract() {
  require_contains "AGENTS.md" "local-only"
  require_contains "AGENTS.md" "remote-backed"
  require_contains "README.md" "local-only"
  require_contains "README.md" "remote-backed"
  require_contains "docs/agent/generated-project-index.md" "local-only"
  require_contains "docs/agent/generated-project-index.md" "remote-backed"
  require_contains ".codex/README.md" "local-only"
  require_contains ".codex/README.md" "remote-backed"

  if ! has_git_remote; then
    local rel
    for rel in AGENTS.md README.md docs/agent/generated-project-index.md .codex/README.md; do
      if grep -Eq 'not complete until `git push` succeeds|then `git push`' "$root/$rel"; then
        printf 'generated closeout guidance must distinguish local-only and remote-backed repos: %s\n' "$rel" >&2
        status=1
      fi
    done
  fi
}

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/AGENTS.md \
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
  src/AGENTS.md \
  automation/context/templates/generated-project-project-map.md \
  automation/context/templates/generated-project-metadata-index.json \
  automation/context/template-managed-paths.txt; do
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
require_markdown_link "docs/AGENTS.md" "agent/index.md"
require_markdown_link "docs/AGENTS.md" "agent/generated-project-index.md"
require_markdown_link ".codex/README.md" "../docs/agent/index.md"
require_markdown_link ".codex/README.md" "../docs/agent/generated-project-index.md"
require_markdown_link ".codex/README.md" "../docs/agent/review.md"
require_markdown_link ".codex/README.md" "../env/README.md"
require_markdown_link ".codex/README.md" "../.agents/skills/README.md"
require_markdown_link ".codex/README.md" "../docs/exec-plans/README.md"
require_markdown_link ".agents/skills/README.md" "../../.claude/skills/README.md"
require_markdown_link ".claude/skills/README.md" "../../.agents/skills/README.md"
require_markdown_link "src/AGENTS.md" "../docs/agent/generated-project-index.md"
require_contains "docs/agent/index.md" "docs/agent/architecture.md"
require_contains "docs/agent/index.md" "docs/agent/generated-project-index.md"
require_contains "docs/agent/index.md" "docs/agent/source-vs-generated.md"
require_contains "docs/agent/index.md" "docs/agent/verify.md"
require_contains "docs/agent/index.md" "docs/agent/review.md"
require_contains "docs/agent/index.md" "docs/exec-plans/README.md"
require_contains "docs/README.md" "docs/agent/generated-project-index.md"
require_contains "docs/AGENTS.md" "generated repo"
require_contains "automation/AGENTS.md" "automation/context/project-map.md"
require_contains "automation/AGENTS.md" "automation/context/metadata-index.generated.json"
require_contains "automation/AGENTS.md" "docs/agent/generated-project-index.md"
require_contains "src/AGENTS.md" "automation/context/project-map.md"
require_contains "src/AGENTS.md" "automation/context/metadata-index.generated.json"
require_contains "docs/agent/generated-project-index.md" "seed-once / project-owned"
require_contains "docs/agent/generated-project-index.md" "generated-derived"
require_contains "docs/agent/generated-project-index.md" "make template-update"
require_contains "docs/agent/generated-project-index.md" ".template-overlay-version"
require_contains "docs/agent/generated-project-index.md" "automation/context/metadata-index.generated.json"
require_contains "docs/agent/generated-project-index.md" "docs/agent/review.md"
require_contains "docs/agent/generated-project-index.md" "env/README.md"
require_contains "docs/agent/generated-project-index.md" ".agents/skills/README.md"
require_contains "docs/agent/generated-project-index.md" ".codex/README.md"
require_contains "docs/agent/generated-project-index.md" "docs/exec-plans/README.md"
require_contains "docs/agent/source-vs-generated.md" "template-managed"
require_contains "docs/agent/source-vs-generated.md" ".template-overlay-version"
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
require_contains "docs/template-maintenance.md" ".template-overlay-version"
require_contains "docs/template-maintenance.md" "automation/context/template-managed-paths.txt"
require_contains "docs/template-maintenance.md" "./scripts/llm/export-context.sh --write"
require_contains "docs/template-maintenance.md" "tests/smoke/copier-update-ready.sh"
require_contains ".codex/README.md" "env/README.md"
require_contains ".codex/README.md" "docs/agent/review.md"
require_contains ".codex/README.md" "docs/exec-plans/README.md"
require_contains ".agents/skills/README.md" ".claude/skills/"
require_contains ".claude/skills/README.md" ".agents/skills/"

for rel in \
  AGENTS.md \
  README.md \
  docs/README.md \
  docs/AGENTS.md \
  docs/agent/index.md \
  docs/agent/architecture.md \
  docs/agent/generated-project-index.md \
  docs/agent/generated-project-verification.md \
  docs/agent/source-vs-generated.md \
  docs/agent/verify.md \
  docs/agent/review.md \
  docs/template-maintenance.md \
  docs/exec-plans/README.md \
  automation/AGENTS.md \
  .codex/README.md \
  src/AGENTS.md \
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
    automation/context/template-managed-paths.txt \
    automation/context/source-tree.generated.txt \
    automation/context/metadata-index.generated.json \
    openspec/project.md \
    .template-overlay-version; do
    require_path "$rel"
  done

  require_markdown_link "AGENTS.md" "docs/agent/generated-project-index.md"
  require_markdown_link "AGENTS.md" "automation/context/project-map.md"
  require_markdown_link "AGENTS.md" "automation/context/metadata-index.generated.json"
  require_markdown_link "AGENTS.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "AGENTS.md" "docs/template-maintenance.md"
  require_markdown_link "README.md" "docs/agent/generated-project-index.md"
  require_markdown_link "README.md" "automation/context/project-map.md"
  require_markdown_link "README.md" "automation/context/metadata-index.generated.json"
  require_markdown_link "README.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "README.md" "docs/agent/review.md"
  require_markdown_link "README.md" "env/README.md"
  require_markdown_link "README.md" ".agents/skills/README.md"
  require_markdown_link "README.md" ".codex/README.md"
  require_markdown_link "README.md" "docs/exec-plans/README.md"
  require_markdown_link "README.md" "docs/template-maintenance.md"

  require_contains "AGENTS.md" "generated 1С-project"
  require_contains "AGENTS.md" "generated-project-first onboarding path"
  require_contains "README.md" "generated 1С-проект"
  require_contains "README.md" "Ownership Classes"
  require_contains "README.md" ".template-overlay-version"
  require_contains "automation/context/project-map.md" "Ownership Model"
  require_contains "automation/context/project-map.md" "generated-derived"
  require_contains "openspec/project.md" "generated 1С-проект"

  require_no_placeholder_pattern "README.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "automation/context/project-map.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "openspec/project.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "README.md" 'template source repo'
  require_no_placeholder_pattern "automation/context/project-map.md" 'template source repo'
  require_absent_regex "README.md" 'docs/agent/index\.md' \
    "generated README must not route to source-repo-centric onboarding"

  check_generated_private_leaks
  check_generated_metadata_contract
  check_generated_closeout_contract

  if ! "$root/scripts/llm/export-context.sh" --check; then
    status=1
  fi
fi

if [ "$status" -eq 0 ]; then
  log "Agent-facing docs and context look consistent"
fi

exit "$status"
