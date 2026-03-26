#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command jq

root="$(project_root)"

is_source_repo() {
  [ -f "$root/openspec/specs/agent-runtime-toolkit/spec.md" ] && \
    [ -f "$root/openspec/specs/project-scoped-skills/spec.md" ] && \
    [ -f "$root/openspec/specs/template-ci-contours/spec.md" ]
}

print_source_repo_onboard() {
  cat <<'EOF'
# Codex Onboard

Repository role: template-source
Canonical onboarding router: docs/agent/index.md
Architecture guide: docs/agent/architecture.md
Verification entrypoint: make agent-verify
Generated-project router reference: docs/agent/generated-project-index.md
Generated-project workflow guide: docs/agent/codex-workflows.md
Generated-project support-matrix templates: automation/context/templates/generated-project-runtime-support-matrix.md, automation/context/templates/generated-project-runtime-support-matrix.json
Generated-project productivity scaffolds: automation/context/templates/generated-project-architecture-map.md, automation/context/templates/generated-project-operator-local-runbook.md, automation/context/templates/generated-project-runtime-quickstart.md, automation/context/templates/generated-project-project-delta-hints.json, automation/context/templates/generated-project-project-delta-hotspots.md
Execution plan starters: docs/exec-plans/TEMPLATE.md, docs/exec-plans/EXAMPLE.md

Codex controls:
- /plan -> execution matrix for long-running work
- /compact -> reduce session size before handoff
- /review -> focused review pass
- /ps -> inspect background shell work
- /mcp -> inspect available MCP tools

Next commands:
- make agent-verify
- openspec list
- bd ready
EOF
}

require_generated_path() {
  local rel="$1"
  [ -e "$root/$rel" ] || die "generated-project onboarding path is missing: $rel"
}

print_generated_repo_onboard() {
  local metadata_path="automation/context/metadata-index.generated.json"
  local summary_path="automation/context/hotspots-summary.generated.md"
  local project_map_path="automation/context/project-map.md"
  local architecture_map_path="docs/agent/architecture-map.md"
  local workflow_path="docs/agent/codex-workflows.md"
  local operator_local_runbook_path="docs/agent/operator-local-runbook.md"
  local runtime_quickstart_path="docs/agent/runtime-quickstart.md"
  local support_matrix_json="automation/context/runtime-support-matrix.json"
  local support_matrix_md="automation/context/runtime-support-matrix.md"
  local project_delta_hints_path="automation/context/project-delta-hints.json"
  local project_delta_hotspots_path="automation/context/project-delta-hotspots.generated.md"
  local exec_plan_template_path="docs/exec-plans/TEMPLATE.md"
  local config_name=""
  local contour_line=""
  local extension_line=""

  require_generated_path "$project_map_path"
  require_generated_path "$architecture_map_path"
  require_generated_path "$workflow_path"
  require_generated_path "$operator_local_runbook_path"
  require_generated_path "$runtime_quickstart_path"
  require_generated_path "$support_matrix_json"
  require_generated_path "$support_matrix_md"
  require_generated_path "$project_delta_hints_path"
  require_generated_path "$project_delta_hotspots_path"
  require_generated_path "$exec_plan_template_path"

  if [ -f "$root/$metadata_path" ]; then
    config_name="$(jq -r '.configuration.name // ""' "$root/$metadata_path")"
  fi

  if jq -e '.projectSpecificBaselineExtension != null' "$root/$support_matrix_json" >/dev/null 2>&1; then
    extension_line="$(jq -r '.projectSpecificBaselineExtension | "\(.id) -> \(.entrypoint) (\(.runbookPath))"' "$root/$support_matrix_json")"
  else
    extension_line="not declared"
  fi

  cat <<EOF
# Codex Onboard

Repository role: generated-project
Canonical onboarding router: docs/agent/generated-project-index.md
Project map: $project_map_path
Workflow guide: $workflow_path
Architecture map: $architecture_map_path
Operator-local runbook: $operator_local_runbook_path
Runtime quick reference: $runtime_quickstart_path
Runtime support matrix (md): $support_matrix_md
Runtime support matrix (json): $support_matrix_json
Project-delta hints: $project_delta_hints_path
Project-delta hotspots: $project_delta_hotspots_path
Summary-first map: $summary_path
Raw inventory: $metadata_path
Exec-plan template: $exec_plan_template_path
Project-specific baseline extension: $extension_line
EOF

  if [ -n "$config_name" ]; then
    printf 'Configuration name: %s\n' "$config_name"
  fi

  printf '\nSafe-local first pass:\n'
  printf -- '- make codex-onboard\n'
  printf -- '- make agent-verify\n'
  printf -- '- make export-context-check\n'

  printf '\nRuntime contour statuses:\n'
  while IFS= read -r contour_line; do
    [ -n "$contour_line" ] || continue
    printf -- '- %s\n' "$contour_line"
  done < <(
    jq -r '.contours[] | "\(.id): \(.status) (\(.profileProvenance))"' "$root/$support_matrix_json"
  )

  cat <<'EOF'

Codex controls:
- /plan -> зафиксировать execution matrix до большого multi-session change
- /compact -> свернуть длинную сессию перед handoff
- /review -> попросить focused review pass по текущему worktree
- /ps -> посмотреть фоновые shell/runtime contours
- /mcp -> подтвердить доступные MCP tools


Planning matrix:
- OpenSpec -> use for new capability, breaking change, architecture shift, or ambiguous intent
- bd -> use for executable code-change tracking after approval
- docs/exec-plans/TEMPLATE.md -> copy-ready starter for long-running, multi-session, or cross-cutting work

Follow-up routers:
- docs/agent/review.md
- docs/agent/codex-workflows.md
- docs/agent/operator-local-runbook.md
- env/README.md
- .agents/skills/README.md
- .codex/README.md
- docs/exec-plans/README.md
- docs/template-maintenance.md

Next commands:
- make agent-verify
- make export-context-check
- bd ready
EOF
}

case "${1:---default}" in
  --help|-h)
    cat <<'EOF'
Usage:
  ./scripts/qa/codex-onboard.sh

Read-only onboarding snapshot for the current repository.
Prints the canonical router, safe-local verification commands, and runtime support truth without mutating checked-in files.
EOF
    ;;
  --default)
    if is_source_repo; then
      print_source_repo_onboard
    else
      print_generated_repo_onboard
    fi
    ;;
  *)
    die "unknown argument: $1"
    ;;
esac
