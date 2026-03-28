#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

project_root="$tmpdir/project"
bindir="$tmpdir/bin"
bd_log="$tmpdir/bd.log"

mkdir -p "$project_root/scripts/bootstrap" "$project_root/scripts/lib" "$project_root/scripts/llm" "$project_root/scripts/template" "$bindir"
git init -q "$project_root" >/dev/null 2>&1

cp "$SOURCE_ROOT/scripts/bootstrap/agents-overlay.sh" "$project_root/scripts/bootstrap/agents-overlay.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/copier-post-copy.sh" "$project_root/scripts/bootstrap/copier-post-copy.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/generated-project-surface.sh" "$project_root/scripts/bootstrap/generated-project-surface.sh"
cp "$SOURCE_ROOT/scripts/lib/common.sh" "$project_root/scripts/lib/common.sh"
cp "$SOURCE_ROOT/scripts/llm/export-context.sh" "$project_root/scripts/llm/export-context.sh"
cp "$SOURCE_ROOT/scripts/template/lib-overlay.sh" "$project_root/scripts/template/lib-overlay.sh"

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ] || [ "$1" != "init" ] || [ "$2" != "--tools" ]; then
  printf 'unexpected openspec args: %s\n' "$*" >&2
  exit 1
fi

if [ ! -f AGENTS.md ]; then
  cat >AGENTS.md <<'EOT'
<!-- OPENSPEC:START -->
# OpenSpec Instructions
<!-- OPENSPEC:END -->
EOT
fi
EOF

cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$BD_LOG"
EOF

chmod +x "$bindir/openspec" "$bindir/bd"

run_bootstrap() {
  (
    cd "$project_root"
    PATH="$bindir:$PATH" BD_LOG="$bd_log" bash ./scripts/bootstrap/copier-post-copy.sh \
      "$SOURCE_ROOT" \
      "Sample Project" \
      "sample-project" \
      "Тестовый generated проект" \
      "direct-platform" \
      "none" \
      "no" \
      "yes" \
      "sample-project" \
      >/dev/null
  )
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_exists() {
  local path="$1"

  if [ -e "$path" ]; then
    printf 'path should not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"

  if ! jq -e "$expr" "$file" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_count() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local actual_count

  actual_count="$(grep -Fc -- "$pattern" "$file" || true)"
  if [ "$actual_count" != "$expected_count" ]; then
    printf 'unexpected count for %s: expected %s, got %s\n' "$pattern" "$expected_count" "$actual_count" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_next_line() {
  local file="$1"
  local expected_current="$2"
  local expected_next="$3"

  if ! awk -v expected_current="$expected_current" -v expected_next="$expected_next" '
    $0 == expected_current {
      found = 1
      if (getline next_line <= 0) {
        exit 2
      }
      if (next_line != expected_next) {
        exit 1
      }
      exit 0
    }
    END {
      if (!found) {
        exit 3
      }
    }
  ' "$file"; then
    printf 'expected "%s" to be followed immediately by "%s"\n' "$expected_current" "$expected_next" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_bootstrap
run_bootstrap

agents_file="$project_root/AGENTS.md"
readme_file="$project_root/README.md"
project_map_file="$project_root/automation/context/project-map.md"
runtime_policy_file="$project_root/automation/context/runtime-profile-policy.json"
runtime_matrix_file="$project_root/automation/context/runtime-support-matrix.md"
runtime_matrix_json_file="$project_root/automation/context/runtime-support-matrix.json"
architecture_map_file="$project_root/docs/agent/architecture-map.md"
runtime_quickstart_file="$project_root/docs/agent/runtime-quickstart.md"
codex_workflows_file="$project_root/docs/agent/codex-workflows.md"
operator_local_runbook_file="$project_root/docs/agent/operator-local-runbook.md"
exec_plan_template_file="$project_root/docs/exec-plans/TEMPLATE.md"
exec_plan_example_file="$project_root/docs/exec-plans/EXAMPLE.md"
work_items_readme_file="$project_root/docs/work-items/README.md"
work_items_template_file="$project_root/docs/work-items/TEMPLATE.md"
metadata_index_file="$project_root/automation/context/metadata-index.generated.json"
hotspots_summary_file="$project_root/automation/context/hotspots-summary.generated.md"
project_delta_hints_file="$project_root/automation/context/project-delta-hints.json"
project_delta_hotspots_file="$project_root/automation/context/project-delta-hotspots.generated.md"
source_tree_file="$project_root/automation/context/source-tree.generated.txt"
openspec_project_file="$project_root/openspec/project.md"
overlay_version_file="$project_root/.template-overlay-version"
manifest_file="$project_root/automation/context/template-managed-paths.txt"
docs_agents_file="$project_root/docs/AGENTS.md"
env_agents_file="$project_root/env/AGENTS.md"
tests_agents_file="$project_root/tests/AGENTS.md"
scripts_agents_file="$project_root/scripts/AGENTS.md"
src_agents_file="$project_root/src/AGENTS.md"
cf_agents_file="$project_root/src/cf/AGENTS.md"
cf_readme_file="$project_root/src/cf/README.md"

assert_contains "$agents_file" "We operate in a cycle: **OpenSpec (What) -> Beads (How) -> Code (Implementation)**."
assert_contains "$agents_file" 'This repository is a generated 1С-project created from `1c-runner-agnostic-template`.'
assert_contains "$agents_file" 'Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) for the generated-project-first onboarding path.'
assert_contains "$agents_file" 'Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.'
assert_contains "$agents_file" 'Use [automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md) as the compact generated-derived map for the first hour.'
assert_contains "$agents_file" 'Use [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json) for sanctioned checked-in runtime profile policy.'
assert_contains "$agents_file" 'Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.'
assert_contains "$agents_file" 'Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.'
assert_contains "$agents_file" 'Use [docs/agent/codex-workflows.md](docs/agent/codex-workflows.md) as the canonical Codex workflow guide after the first router step.'
assert_contains "$agents_file" 'Use [docs/agent/review.md](docs/agent/review.md), [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md), [env/README.md](env/README.md), [.agents/skills/README.md](.agents/skills/README.md), [docs/exec-plans/README.md](docs/exec-plans/README.md), and [docs/work-items/README.md](docs/work-items/README.md) as the main follow-up routers.'
assert_contains "$agents_file" 'Do not move to production code for new or major changes without explicit approval. Canonical signal: `Go!`.'
assert_contains "$agents_file" 'Use `bd` as the source of truth for code-change tracking.'
assert_contains "$agents_file" 'Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.'
assert_contains "$agents_file" '1. `mcp__claude-context__search_code`, if available in the current environment'
assert_contains "$agents_file" 'For remote-backed repos with a writable Git remote, a code-change session is not complete until the verified branch state is pushed.'
assert_contains "$agents_file" 'For local-only repos or repos without a writable remote, do not invent a push-only closeout path.'
assert_count "$agents_file" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->" "1"
assert_next_line "$agents_file" "<!-- OPENSPEC:END -->" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"

assert_contains "$readme_file" "<!-- RUNNER_AGNOSTIC_PROJECT:START -->"
assert_contains "$readme_file" "generated 1С-проект"
assert_contains "$readme_file" "[automation/context/project-map.md](automation/context/project-map.md)"
assert_contains "$readme_file" "[automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md)"
assert_contains "$readme_file" "[automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json)"
assert_contains "$readme_file" "[automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json)"
assert_contains "$readme_file" "[docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md)"
assert_contains "$readme_file" "[docs/agent/review.md](docs/agent/review.md)"
assert_contains "$readme_file" "[env/README.md](env/README.md)"
assert_contains "$readme_file" "[.agents/skills/README.md](.agents/skills/README.md)"
assert_contains "$readme_file" "[.codex/README.md](.codex/README.md)"
assert_contains "$readme_file" "[docs/agent/codex-workflows.md](docs/agent/codex-workflows.md)"
assert_contains "$readme_file" "[docs/exec-plans/README.md](docs/exec-plans/README.md)"
assert_contains "$readme_file" "[docs/work-items/README.md](docs/work-items/README.md)"
assert_contains "$readme_file" "[docs/template-maintenance.md](docs/template-maintenance.md)"
assert_contains "$readme_file" "local-only"
assert_contains "$readme_file" "remote-backed"
assert_contains "$readme_file" "[docs/agent/architecture-map.md](docs/agent/architecture-map.md)"
assert_contains "$readme_file" "[docs/agent/runtime-quickstart.md](docs/agent/runtime-quickstart.md)"
assert_contains "$readme_file" "[docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md)"
assert_contains "$readme_file" "[automation/context/project-delta-hotspots.generated.md](automation/context/project-delta-hotspots.generated.md)"
assert_contains "$project_map_file" "Ownership Model"
assert_contains "$project_map_file" "generated-derived"
assert_contains "$project_map_file" "automation/context/runtime-profile-policy.json"
assert_contains "$project_map_file" "docs/agent/architecture-map.md"
assert_contains "$project_map_file" "docs/agent/runtime-quickstart.md"
assert_contains "$project_map_file" "docs/work-items/README.md"
assert_contains "$project_map_file" "automation/context/project-delta-hints.json"
assert_contains "$project_map_file" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$openspec_project_file" "generated 1С-проект"
assert_contains "$architecture_map_file" "# Architecture Map"
assert_contains "$architecture_map_file" "## Representative Change Scenarios"
assert_contains "$architecture_map_file" "docs/agent/runtime-quickstart.md"
assert_contains "$architecture_map_file" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$architecture_map_file" "automation/context/project-delta-hints.json"
assert_contains "$runtime_quickstart_file" "# Runtime Quickstart"
assert_contains "$runtime_quickstart_file" "## Contour Quick Reference"
assert_contains "$runtime_quickstart_file" "automation/context/runtime-support-matrix.md"
assert_contains "$runtime_quickstart_file" "## Optional Project-Specific Baseline Extension"
assert_contains "$runtime_quickstart_file" "docs/agent/operator-local-runbook.md"
assert_contains "$runtime_quickstart_file" "docs/work-items/README.md"
assert_contains "$codex_workflows_file" "# Codex Workflows"
assert_contains "$codex_workflows_file" "docs/exec-plans/TEMPLATE.md"
assert_contains "$codex_workflows_file" "docs/work-items/README.md"
assert_contains "$codex_workflows_file" "docs/work-items/TEMPLATE.md"
assert_contains "$operator_local_runbook_file" "# Operator-Local Runbook"
assert_contains "$operator_local_runbook_file" "automation/context/runtime-support-matrix.md"
assert_contains "$operator_local_runbook_file" "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run"
assert_contains "$operator_local_runbook_file" "./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run"
assert_contains "$operator_local_runbook_file" "docs/work-items/README.md"
assert_contains "$exec_plan_template_file" "# Execution Plan Template"
assert_contains "$exec_plan_example_file" "# Example Execution Plan"
assert_contains "$work_items_readme_file" "# Work Items"
assert_contains "$work_items_readme_file" "docs/exec-plans/README.md"
assert_contains "$work_items_template_file" "# Work Item Template"
assert_contains "$metadata_index_file" "\"inventoryRole\": \"generated-derived\""
assert_contains "$hotspots_summary_file" "# Generated Hotspots Summary"
assert_contains "$hotspots_summary_file" "## Freshness"
assert_contains "$hotspots_summary_file" "automation/context/runtime-profile-policy.json"
assert_contains "$hotspots_summary_file" "docs/agent/architecture-map.md"
assert_contains "$hotspots_summary_file" "docs/agent/runtime-quickstart.md"
assert_contains "$hotspots_summary_file" "docs/work-items/README.md"
assert_contains "$hotspots_summary_file" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$project_delta_hotspots_file" "# Generated Project-Delta Hotspots"
assert_contains "$project_delta_hotspots_file" "automation/context/project-delta-hints.json"
assert_contains "$source_tree_file" "# Generated Project Tree"
assert_contains "$overlay_version_file" "$(git -C "$SOURCE_ROOT" describe --tags --always)"
assert_contains "$manifest_file" "scripts/template/update-template.sh"
assert_contains "$manifest_file" "automation/context/templates/generated-project-hotspots-summary.md"
assert_contains "$manifest_file" "automation/context/templates/generated-project-operator-local-runbook.md"
assert_contains "$manifest_file" "automation/context/templates/generated-project-project-delta-hints.json"
assert_contains "$manifest_file" "automation/context/templates/generated-project-project-delta-hotspots.md"
assert_contains "$manifest_file" "automation/context/templates/generated-project-runtime-profile-policy.json"
assert_contains "$manifest_file" "automation/context/templates/generated-project-work-items-readme.md"
assert_contains "$manifest_file" "automation/context/templates/generated-project-work-items-template.md"
assert_contains "$manifest_file" "docs/AGENTS.md"
assert_contains "$manifest_file" "env/AGENTS.md"
assert_contains "$manifest_file" "tests/AGENTS.md"
assert_contains "$manifest_file" "scripts/AGENTS.md"
assert_contains "$manifest_file" "src/AGENTS.md"
assert_contains "$docs_agents_file" "[docs/agent/generated-project-index.md](agent/generated-project-index.md)"
assert_contains "$docs_agents_file" "[docs/agent/index.md](agent/index.md)"
assert_contains "$env_agents_file" "[env/README.md](README.md)"
assert_contains "$env_agents_file" "automation/context/runtime-profile-policy.json"
assert_contains "$tests_agents_file" "[docs/agent/generated-project-verification.md](../docs/agent/generated-project-verification.md)"
assert_contains "$tests_agents_file" "scripts/qa/check-agent-docs.sh"
assert_contains "$scripts_agents_file" "[docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md)"
assert_contains "$scripts_agents_file" "automation/context/hotspots-summary.generated.md"
assert_contains "$src_agents_file" "[docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md)"
assert_contains "$src_agents_file" "docs/agent/architecture-map.md"
assert_contains "$src_agents_file" "docs/agent/runtime-quickstart.md"
assert_contains "$src_agents_file" "automation/context/project-map.md"
assert_contains "$src_agents_file" "automation/context/hotspots-summary.generated.md"
assert_contains "$src_agents_file" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$src_agents_file" "automation/context/metadata-index.generated.json"
assert_contains "$src_agents_file" "src/cf/CommonModules"
assert_contains "$src_agents_file" "src/cf/ScheduledJobs"
assert_not_exists "$cf_agents_file"
assert_not_exists "$cf_readme_file"
assert_jq "$project_delta_hints_file" '.hintsRole == "project-owned-project-delta-hints" and (.selectors.pathPrefixes | type == "array") and (.selectors.pathKeywords | type == "array") and (.representativePaths | type == "array")' "project-delta-hints-default"
assert_jq "$runtime_policy_file" '.rootEnvProfiles.sanctionedAdditionalProfiles == []' "runtime-policy-default"
assert_jq "$runtime_matrix_json_file" '.projectSpecificBaselineExtension == null and (.contours[] | select(.id == "doctor") | .runbookPath) == "docs/agent/operator-local-runbook.md"' "runtime-matrix-default-extension"

mkdir -p \
  "$project_root/src/cf/HTTPServices/Orders" \
  "$project_root/src/cf/WebServices/LegacySync" \
  "$project_root/src/cf/ScheduledJobs/SyncCatalog" \
  "$project_root/src/cf/CommonModules/Shared" \
  "$project_root/src/cf/Subsystems/Backoffice" \
  "$project_root/src/cfe/MainExtension" \
  "$project_root/src/epf/ImportWizard" \
  "$project_root/src/erf/RevenueReport" \
  "$project_root/env/.local" \
  "$project_root/.codex"

cat >"$project_root/src/cf/Configuration.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration uuid="11111111-1111-1111-1111-111111111111">
    <Properties>
      <Name>SmokeConfiguration</Name>
    </Properties>
  </Configuration>
</MetaDataObject>
EOF

printf '{ "profileName": "local" }\n' >"$project_root/env/local.json"
printf '{ "profileName": "private" }\n' >"$project_root/env/.local/dev.json"
printf 'mcp = true\n' >"$project_root/.codex/local.override.toml"

(
  cd "$project_root"
  bash ./scripts/llm/export-context.sh --write >/dev/null
)

assert_contains "$metadata_index_file" '"name": "SmokeConfiguration"'
assert_contains "$metadata_index_file" '"uuid": "11111111-1111-1111-1111-111111111111"'
assert_contains "$metadata_index_file" '"entrypointInventory"'
assert_contains "$metadata_index_file" '"configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"]'
assert_contains "$metadata_index_file" '"httpServices": ["src/cf/HTTPServices/Orders"]'
assert_contains "$metadata_index_file" '"webServices": ["src/cf/WebServices/LegacySync"]'
assert_contains "$metadata_index_file" '"scheduledJobs": ["src/cf/ScheduledJobs/SyncCatalog"]'
assert_contains "$metadata_index_file" '"commonModules": ["src/cf/CommonModules/Shared"]'
assert_contains "$metadata_index_file" '"subsystems": ["src/cf/Subsystems/Backoffice"]'
assert_contains "$metadata_index_file" '"extensions": ["src/cfe/MainExtension"]'
assert_contains "$metadata_index_file" '"externalProcessors": ["src/epf/ImportWizard"]'
assert_contains "$metadata_index_file" '"reports": ["src/erf/RevenueReport"]'
assert_jq "$metadata_index_file" '.authoritativeDocs.runtimeProfilePolicy == "automation/context/runtime-profile-policy.json" and .authoritativeDocs.hotspotsSummary == "automation/context/hotspots-summary.generated.md" and .authoritativeDocs.architectureMap == "docs/agent/architecture-map.md" and .authoritativeDocs.runtimeQuickstart == "docs/agent/runtime-quickstart.md" and .authoritativeDocs.codexWorkflows == "docs/agent/codex-workflows.md" and .authoritativeDocs.operatorLocalRunbook == "docs/agent/operator-local-runbook.md" and .authoritativeDocs.workItemsGuide == "docs/work-items/README.md" and .authoritativeDocs.workItemsTemplate == "docs/work-items/TEMPLATE.md" and .authoritativeDocs.projectDeltaHints == "automation/context/project-delta-hints.json" and .authoritativeDocs.projectDeltaHotspots == "automation/context/project-delta-hotspots.generated.md"' "generated-metadata-authoritative-docs"
assert_contains "$hotspots_summary_file" 'Configuration name: `SmokeConfiguration`'
assert_contains "$hotspots_summary_file" '`metadata-index.generated.json` checksum:'
assert_contains "$project_delta_hotspots_file" "No project-delta selectors are declared yet."

if grep -Fq -- './env/local.json' "$source_tree_file"; then
  printf 'generated source tree leaked env/local.json\n' >&2
  exit 1
fi

if grep -Fq -- './env/.local/dev.json' "$source_tree_file"; then
  printf 'generated source tree leaked env/.local/dev.json\n' >&2
  exit 1
fi

if grep -Fq -- './.codex/local.override.toml' "$source_tree_file"; then
  printf 'generated source tree leaked .codex/local.override.toml\n' >&2
  exit 1
fi
