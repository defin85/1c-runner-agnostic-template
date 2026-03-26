#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"

root="$(project_root)"
status=0
generated_summary_rel="automation/context/hotspots-summary.generated.md"
generated_policy_rel="automation/context/runtime-profile-policy.json"
generated_matrix_json_rel="automation/context/runtime-support-matrix.json"
generated_matrix_md_rel="automation/context/runtime-support-matrix.md"
codex_onboard_rel="scripts/qa/codex-onboard.sh"

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

require_no_local_private_runtime_truth() {
  local rel="$1"

  if grep -Eq -- 'runtime doctor:.*env/(local|wsl|ci|windows-executor)\.json|runtime truth:.*env/(local|wsl|ci|windows-executor)\.json|shared truth:.*env/(local|wsl|ci|windows-executor)\.json|source of truth:.*env/(local|wsl|ci|windows-executor)\.json|--profile[[:space:]]+env/(local|wsl|ci|windows-executor)\.json|--profile[[:space:]]+env/\.local/' "$root/$rel"; then
    printf 'local-private runtime profile must not be advertised as shared truth outside runtime support matrix: %s\n' \
      "$rel" >&2
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

require_jq_expr() {
  local rel="$1"
  local expr="$2"
  local message="$3"

  require_command jq
  if ! jq -e "$expr" "$root/$rel" >/dev/null; then
    printf '%s: %s\n' "$message" "$rel" >&2
    status=1
  fi
}

profile_capability_command_expr() {
  local capability="$1"

  printf '.capabilities.%s.command\n' "$capability"
}

checked_in_command_token_references_repo_path() {
  local token="$1"
  local candidate=""

  candidate="${token%%[[:space:];|&()]*}"
  [ -n "$candidate" ] || return 1

  case "$candidate" in
    ./*)
      [ -e "$root/${candidate#./}" ]
      ;;
    scripts/*|tests/*|features/*|src/*|automation/*|docs/*|env/*|.agents/*|.codex/*|.claude/*|Makefile)
      [ -e "$root/$candidate" ]
      ;;
    *)
      return 1
      ;;
  esac
}

checked_in_verification_command_is_repo_owned() {
  local -a command=("$@")

  [ "$#" -gt 0 ] || return 1

  if [ "${command[0]}" = "make" ] && [ "$#" -ge 2 ] && [[ "${command[1]}" != -* ]]; then
    return 0
  fi

  checked_in_command_token_references_repo_path "${command[0]}"
}

check_checked_in_verification_command_shape() {
  local rel="$1"
  local capability="$2"
  local command_expr=""
  local -a profile_command=()

  command_expr="$(profile_capability_command_expr "$capability")"
  if ! jq -e "$command_expr != null" "$root/$rel" >/dev/null 2>&1; then
    return 0
  fi

  mapfile -t profile_command < <(jq -r "$command_expr | if type == \"array\" then .[] else empty end" "$root/$rel")
  if ! checked_in_verification_command_is_repo_owned "${profile_command[@]}"; then
    printf 'checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: %s (%s)\n' \
      "$rel" "$capability" >&2
    status=1
  fi
}

check_checked_in_verification_contract() {
  local rel="$1"
  local capability=""

  for capability in smoke xunit bdd; do
    check_checked_in_verification_command_shape "$rel" "$capability"
  done
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
  require_contains "automation/context/metadata-index.generated.json" "\"runtimeProfilePolicy\""
  require_contains "automation/context/metadata-index.generated.json" "\"runtimeSupportMatrixJson\""
  require_contains "automation/context/metadata-index.generated.json" "\"runtimeSupportMatrixMarkdown\""
  require_contains "automation/context/metadata-index.generated.json" "\"hotspotsSummary\""

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

check_generated_summary_contract() {
  require_contains "$generated_summary_rel" "# Generated Hotspots Summary"
  require_contains "$generated_summary_rel" "## Identity"
  require_contains "$generated_summary_rel" "## Freshness"
  require_contains "$generated_summary_rel" "## High-Signal Counts"
  require_contains "$generated_summary_rel" "## Task-to-Path Routing"
  require_contains "$generated_summary_rel" "## Follow-Up Routers"
  require_contains "$generated_summary_rel" "automation/context/project-map.md"
  require_contains "$generated_summary_rel" "automation/context/metadata-index.generated.json"
  require_contains "$generated_summary_rel" "automation/context/runtime-profile-policy.json"
  require_contains "$generated_summary_rel" "automation/context/runtime-support-matrix.md"
  require_contains "$generated_summary_rel" "automation/context/runtime-support-matrix.json"
}

check_generated_runtime_profile_policy_contract() {
  local policy_rel="$generated_policy_rel"
  local sanctioned_rel=""
  local capability=""
  local filename=""
  local -a unexpected_profiles=()
  local -a sanctioned_profiles=()

  require_jq_expr "$policy_rel" '.rootEnvProfiles.canonicalExamples | type == "array"' \
    "runtime profile policy must define canonicalExamples array"
  require_jq_expr "$policy_rel" '.rootEnvProfiles.canonicalLocalPrivate | type == "array"' \
    "runtime profile policy must define canonicalLocalPrivate array"
  require_jq_expr "$policy_rel" '.rootEnvProfiles.sanctionedAdditionalProfiles | type == "array"' \
    "runtime profile policy must define sanctionedAdditionalProfiles array"
  require_jq_expr "$policy_rel" '.rootEnvProfiles.localSandbox | type == "string"' \
    "runtime profile policy must define localSandbox string"

  collect_runtime_profile_layout_drift_paths "$root" unexpected_profiles
  if [ "${unexpected_profiles[*]-}" != "" ]; then
    printf 'generated runtime profile policy leaves unsanctioned checked-in root profiles: %s\n' \
      "${unexpected_profiles[*]}" >&2
    status=1
  fi

  load_sanctioned_additional_root_runtime_profiles "$root" sanctioned_profiles
  for sanctioned_rel in "${sanctioned_profiles[@]}"; do
    if [ ! -f "$root/$sanctioned_rel" ]; then
      printf 'sanctioned runtime profile is missing: %s\n' "$sanctioned_rel" >&2
      status=1
      continue
    fi

    filename="$(basename "$sanctioned_rel")"
    if canonical_root_runtime_profile_filename "$filename"; then
      printf 'sanctionedAdditionalProfiles must list only additional root presets, not canonical names: %s\n' \
        "$sanctioned_rel" >&2
      status=1
    fi

    if grep -nF -- 'TODO:' "$root/$sanctioned_rel" >/dev/null; then
      printf 'sanctioned runtime profile contains placeholder TODO: %s\n' "$sanctioned_rel" >&2
      status=1
    fi

    check_checked_in_verification_contract "$sanctioned_rel"
  done
}

check_generated_runtime_support_matrix_contract() {
  require_contains "$generated_matrix_md_rel" "# Runtime Support Matrix"
  require_contains "$generated_matrix_md_rel" '`supported`'
  require_contains "$generated_matrix_md_rel" '`unsupported`'
  require_contains "$generated_matrix_md_rel" '`operator-local`'
  require_contains "$generated_matrix_md_rel" '`provisioned`'
  require_contains "$generated_matrix_md_rel" "automation/context/project-map.md"
  require_contains "$generated_matrix_md_rel" "docs/agent/generated-project-index.md"
  require_contains "$generated_matrix_md_rel" "docs/agent/generated-project-verification.md"

  require_jq_expr "$generated_matrix_json_rel" '.matrixRole == "project-owned-runtime-support-matrix"' \
    "runtime support matrix must declare project-owned role"
  require_jq_expr "$generated_matrix_json_rel" \
    '(.statuses | sort) == ["operator-local","provisioned","supported","unsupported"]' \
    "runtime support matrix must define the canonical status set"
  require_jq_expr "$generated_matrix_json_rel" \
    '(.contours | map(.id)) as $ids | ["codex-onboard","agent-verify","export-context-check","doctor","xunit","bdd","smoke","publish-http"] | all(. as $id | $ids | index($id))' \
    "runtime support matrix must cover the required contour ids"
  require_jq_expr "$generated_matrix_json_rel" \
    '.contours | type == "array" and length > 0 and all(.[]; (.id | type == "string" and length > 0) and (.status | type == "string" and length > 0) and (.profileProvenance | type == "string" and length > 0) and (((.entrypoint // "") | type == "string" and length > 0) or ((.runbookPath // "") | type == "string" and length > 0)))' \
    "runtime support matrix contours must declare id/status/provenance and entrypoint or runbook"
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
  docs/template-release.md \
  docs/exec-plans/README.md \
  docs/exec-plans/active/.gitkeep \
  docs/exec-plans/completed/.gitkeep \
  .codex/README.md \
  .agents/skills/README.md \
  .claude/skills/README.md \
  env/AGENTS.md \
  tests/AGENTS.md \
  scripts/AGENTS.md \
  src/AGENTS.md \
  automation/AGENTS.md \
  automation/context/templates/generated-project-hotspots-summary.md \
  automation/context/templates/generated-project-project-map.md \
  automation/context/templates/generated-project-metadata-index.json \
  automation/context/templates/generated-project-runtime-support-matrix.json \
  automation/context/templates/generated-project-runtime-support-matrix.md \
  automation/context/templates/generated-project-runtime-profile-policy.json \
  automation/context/template-managed-paths.txt \
  scripts/qa/codex-onboard.sh; do
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
require_markdown_link "docs/agent/index.md" "../template-release.md"
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
require_markdown_link "env/AGENTS.md" "README.md"
require_markdown_link "tests/AGENTS.md" "../docs/agent/generated-project-verification.md"
require_markdown_link "tests/AGENTS.md" "../env/README.md"
require_markdown_link "scripts/AGENTS.md" "../docs/agent/generated-project-index.md"
require_markdown_link "scripts/AGENTS.md" "../env/README.md"
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
require_contains "automation/AGENTS.md" "automation/context/hotspots-summary.generated.md"
require_contains "automation/AGENTS.md" "automation/context/metadata-index.generated.json"
require_contains "automation/AGENTS.md" "automation/context/runtime-profile-policy.json"
require_contains "automation/AGENTS.md" "automation/context/runtime-support-matrix.md"
require_contains "automation/AGENTS.md" "docs/agent/generated-project-index.md"
require_contains "env/AGENTS.md" "env/README.md"
require_contains "env/AGENTS.md" "automation/context/runtime-profile-policy.json"
require_contains "env/AGENTS.md" "automation/context/runtime-support-matrix.md"
require_contains "env/AGENTS.md" "unsupportedReason"
require_contains "tests/AGENTS.md" "docs/agent/generated-project-verification.md"
require_contains "tests/AGENTS.md" "automation/context/runtime-profile-policy.json"
require_contains "tests/AGENTS.md" "automation/context/runtime-support-matrix.md"
require_contains "tests/AGENTS.md" "scripts/qa/check-agent-docs.sh"
require_contains "tests/AGENTS.md" "scripts/llm/export-context.sh"
require_contains "scripts/AGENTS.md" "docs/agent/generated-project-index.md"
require_contains "scripts/AGENTS.md" "automation/context/hotspots-summary.generated.md"
require_contains "scripts/AGENTS.md" "automation/context/runtime-profile-policy.json"
require_contains "scripts/AGENTS.md" "automation/context/runtime-support-matrix.md"
require_contains "scripts/AGENTS.md" "make codex-onboard"
require_contains "scripts/AGENTS.md" "scripts/llm/export-context.sh"
require_contains "scripts/AGENTS.md" "scripts/qa/check-agent-docs.sh"
require_contains "src/AGENTS.md" "automation/context/project-map.md"
require_contains "src/AGENTS.md" "automation/context/hotspots-summary.generated.md"
require_contains "src/AGENTS.md" "automation/context/metadata-index.generated.json"
require_contains "docs/agent/generated-project-index.md" "seed-once / project-owned"
require_contains "docs/agent/generated-project-index.md" "generated-derived"
require_contains "docs/agent/generated-project-index.md" "make codex-onboard"
require_contains "docs/agent/generated-project-index.md" "make template-update"
require_contains "docs/agent/generated-project-index.md" ".template-overlay-version"
require_contains "docs/agent/generated-project-index.md" "automation/context/hotspots-summary.generated.md"
require_contains "docs/agent/generated-project-index.md" "automation/context/metadata-index.generated.json"
require_contains "docs/agent/generated-project-index.md" "automation/context/runtime-profile-policy.json"
require_contains "docs/agent/generated-project-index.md" "automation/context/runtime-support-matrix.md"
require_contains "docs/agent/generated-project-index.md" "OpenSpec"
require_contains "docs/agent/generated-project-index.md" "docs/exec-plans/README.md"
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
require_contains "docs/agent/generated-project-verification.md" "make codex-onboard"
require_contains "docs/agent/generated-project-verification.md" "Profile-Required"
require_contains "docs/agent/generated-project-verification.md" "Provisioned / Self-Hosted 1C"
require_contains "docs/agent/generated-project-verification.md" "./scripts/llm/export-context.sh --write"
require_contains "docs/agent/generated-project-verification.md" "unsupportedReason"
require_contains "docs/agent/generated-project-verification.md" "runtime-profile-policy.json"
require_contains "docs/agent/generated-project-verification.md" "runtime-support-matrix.md"
require_contains "docs/template-maintenance.md" "template maintenance"
require_contains "docs/template-maintenance.md" "make template-check-update"
require_contains "docs/template-maintenance.md" "make template-update"
require_contains "docs/template-maintenance.md" "./scripts/template/check-update.sh"
require_contains "docs/template-maintenance.md" "./scripts/template/update-template.sh"
require_contains "docs/template-maintenance.md" ".template-overlay-version"
require_contains "docs/template-maintenance.md" "automation/context/template-managed-paths.txt"
require_contains "docs/template-maintenance.md" "./scripts/llm/export-context.sh --write"
require_contains "docs/template-maintenance.md" "tests/smoke/copier-update-ready.sh"
require_contains "docs/template-release.md" "source repo шаблона"
require_contains "docs/template-release.md" "./scripts/release/install-source-hooks.sh"
require_contains "docs/template-release.md" "./scripts/release/publish-overlay-release.sh --tag v0.3.6"
require_contains "docs/template-release.md" "origin/main"
require_contains "docs/template-release.md" "refs/tags/v*"
require_contains "docs/template-release.md" "make agent-verify"
require_contains ".codex/README.md" "env/README.md"
require_contains ".codex/README.md" "docs/agent/review.md"
require_contains ".codex/README.md" "docs/exec-plans/README.md"
require_contains ".codex/README.md" "make codex-onboard"
require_contains ".codex/README.md" "runtime-support-matrix.md"
require_contains ".codex/README.md" "First 15 Minutes"
require_contains ".codex/README.md" "Long-Running Change"
require_contains ".codex/README.md" "Runtime Investigation"
require_contains ".codex/README.md" "Review-Only Session"
require_contains ".codex/README.md" "Parallel Research"
require_contains "docs/agent/source-vs-generated.md" "runtime-support-matrix.md"
require_contains "docs/agent/source-vs-generated.md" "runtime-support-matrix.json"
require_contains "scripts/qa/codex-onboard.sh" "Repository role: generated-project"
require_contains "scripts/qa/codex-onboard.sh" "Canonical onboarding router: docs/agent/generated-project-index.md"
require_contains "scripts/qa/codex-onboard.sh" "Runtime support matrix (md):"
require_contains "scripts/qa/codex-onboard.sh" "Planning matrix:"
require_contains "automation/context/templates/generated-project-metadata-index.json" "runtimeSupportMatrixJsonPath"
require_contains "automation/context/templates/generated-project-metadata-index.json" "runtimeSupportMatrixMarkdownPath"
require_contains "automation/context/templates/generated-project-hotspots-summary.md" "runtime-support-matrix.md"
require_contains "automation/context/templates/generated-project-project-map.md" "runtime support truth"
require_contains "automation/context/templates/generated-project-runtime-support-matrix.json" "requiredContourIds"
require_contains "automation/context/templates/generated-project-runtime-support-matrix.md" "# Runtime Support Matrix Reference"
require_contains "automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-support-matrix.json"
require_contains "automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-support-matrix.md"
require_contains "automation/context/template-managed-paths.txt" "scripts/qa/codex-onboard.sh"
require_contains ".agents/skills/README.md" ".claude/skills/"
require_contains ".claude/skills/README.md" ".agents/skills/"
require_contains "docs/exec-plans/README.md" "Progress"
require_contains "docs/exec-plans/README.md" "Surprises & Discoveries"
require_contains "docs/exec-plans/README.md" "Decision Log"
require_contains "docs/exec-plans/README.md" "Outcomes & Retrospective"

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
  docs/template-release.md \
  docs/exec-plans/README.md \
  automation/AGENTS.md \
  .codex/README.md \
  env/AGENTS.md \
  tests/AGENTS.md \
  scripts/AGENTS.md \
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
  require_markdown_link "docs/agent/architecture.md" "../template-release.md"
  require_contains "README.md" "1c-runner-agnostic-template"
  require_contains "README.md" "automation/context/templates/"
  require_contains "docs/README.md" "automation/context/hotspots-summary.generated.md"
  require_path "scripts/release/install-source-hooks.sh"
  require_path "scripts/release/publish-overlay-release.sh"
  require_path "scripts/release/lib-source-release.sh"
  require_path ".githooks/pre-push"
  require_contains "docs/agent/index.md" "docs/template-release.md"
  require_contains "docs/agent/architecture.md" "docs/template-release.md"
  require_contains "docs/agent/architecture.md" "./scripts/release/publish-overlay-release.sh --tag vX.Y.Z"
  require_contains "docs/template-maintenance.md" "docs/template-release.md"

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

  for rel in env/local.example.json env/ci.example.json env/wsl.example.json env/windows-executor.example.json; do
    require_absent_regex "$rel" 'TODO:' "placeholder verification command remains in example profile"
    check_checked_in_verification_contract "$rel"
  done

  if ! "$root/scripts/llm/export-context.sh" --check; then
    status=1
  fi
else
  for rel in \
    automation/context/project-map.md \
    automation/context/template-managed-paths.txt \
    automation/context/source-tree.generated.txt \
    automation/context/metadata-index.generated.json \
    automation/context/hotspots-summary.generated.md \
    automation/context/runtime-profile-policy.json \
    automation/context/runtime-support-matrix.json \
    automation/context/runtime-support-matrix.md \
    openspec/project.md \
    env/AGENTS.md \
    tests/AGENTS.md \
    scripts/AGENTS.md \
    scripts/qa/codex-onboard.sh \
    .template-overlay-version; do
    require_path "$rel"
  done

  require_markdown_link "AGENTS.md" "docs/agent/generated-project-index.md"
  require_markdown_link "AGENTS.md" "automation/context/project-map.md"
  require_markdown_link "AGENTS.md" "$generated_summary_rel"
  require_markdown_link "AGENTS.md" "automation/context/metadata-index.generated.json"
  require_markdown_link "AGENTS.md" "$generated_policy_rel"
  require_markdown_link "AGENTS.md" "$generated_matrix_md_rel"
  require_markdown_link "AGENTS.md" "$generated_matrix_json_rel"
  require_markdown_link "AGENTS.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "AGENTS.md" "docs/template-maintenance.md"
  require_markdown_link "README.md" "docs/agent/generated-project-index.md"
  require_markdown_link "README.md" "automation/context/project-map.md"
  require_markdown_link "README.md" "$generated_summary_rel"
  require_markdown_link "README.md" "automation/context/metadata-index.generated.json"
  require_markdown_link "README.md" "$generated_policy_rel"
  require_markdown_link "README.md" "$generated_matrix_md_rel"
  require_markdown_link "README.md" "$generated_matrix_json_rel"
  require_markdown_link "README.md" "docs/agent/generated-project-verification.md"
  require_markdown_link "README.md" "docs/agent/review.md"
  require_markdown_link "README.md" "env/README.md"
  require_markdown_link "README.md" ".agents/skills/README.md"
  require_markdown_link "README.md" ".codex/README.md"
  require_markdown_link "README.md" "docs/exec-plans/README.md"
  require_markdown_link "README.md" "docs/template-maintenance.md"

  require_contains "AGENTS.md" "generated 1С-project"
  require_contains "AGENTS.md" "generated-project-first onboarding path"
  require_contains "AGENTS.md" "make codex-onboard"
  require_contains "AGENTS.md" "automation/context/hotspots-summary.generated.md"
  require_contains "AGENTS.md" "automation/context/runtime-profile-policy.json"
  require_contains "AGENTS.md" "automation/context/runtime-support-matrix.md"
  require_contains "README.md" "generated 1С-проект"
  require_contains "README.md" "Ownership Classes"
  require_contains "README.md" "make codex-onboard"
  require_contains "README.md" ".template-overlay-version"
  require_contains "README.md" "automation/context/hotspots-summary.generated.md"
  require_contains "README.md" "automation/context/runtime-profile-policy.json"
  require_contains "README.md" "automation/context/runtime-support-matrix.md"
  require_contains "automation/context/project-map.md" "Ownership Model"
  require_contains "automation/context/project-map.md" "generated-derived"
  require_contains "automation/context/project-map.md" "automation/context/runtime-profile-policy.json"
  require_contains "automation/context/project-map.md" "automation/context/runtime-support-matrix.md"
  require_contains "openspec/project.md" "generated 1С-проект"
  require_contains "env/AGENTS.md" "automation/context/runtime-profile-policy.json"
  require_contains "tests/AGENTS.md" "scripts/qa/check-agent-docs.sh"
  require_contains "scripts/AGENTS.md" "automation/context/hotspots-summary.generated.md"

  require_no_local_private_runtime_truth "AGENTS.md"
  require_no_local_private_runtime_truth "README.md"
  require_no_local_private_runtime_truth "docs/agent/generated-project-index.md"
  require_no_local_private_runtime_truth "automation/context/project-map.md"

  require_no_placeholder_pattern "README.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "automation/context/project-map.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "openspec/project.md" '<[[:alnum:]_][^>]*>'
  require_no_placeholder_pattern "README.md" 'template source repo'
  require_no_placeholder_pattern "automation/context/project-map.md" 'template source repo'
  require_absent_regex "README.md" 'docs/agent/index\.md' \
    "generated README must not route to source-repo-centric onboarding"

  check_generated_private_leaks
  check_generated_metadata_contract
  check_generated_summary_contract
  check_generated_runtime_profile_policy_contract
  check_generated_runtime_support_matrix_contract
  check_generated_closeout_contract

  if ! "$root/scripts/llm/export-context.sh" --check; then
    status=1
  fi
fi

if [ "$status" -eq 0 ]; then
  log "Agent-facing docs and context look consistent"
fi

exit "$status"
