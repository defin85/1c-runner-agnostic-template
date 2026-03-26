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
Generated-project support-matrix templates: automation/context/templates/generated-project-runtime-support-matrix.md, automation/context/templates/generated-project-runtime-support-matrix.json

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
  local support_matrix_json="automation/context/runtime-support-matrix.json"
  local support_matrix_md="automation/context/runtime-support-matrix.md"
  local config_name=""
  local contour_line=""

  require_generated_path "$project_map_path"
  require_generated_path "$support_matrix_json"
  require_generated_path "$support_matrix_md"

  if [ -f "$root/$metadata_path" ]; then
    config_name="$(jq -r '.configuration.name // ""' "$root/$metadata_path")"
  fi

  cat <<EOF
# Codex Onboard

Repository role: generated-project
Canonical onboarding router: docs/agent/generated-project-index.md
Project map: $project_map_path
Runtime support matrix (md): $support_matrix_md
Runtime support matrix (json): $support_matrix_json
Summary-first map: $summary_path
Raw inventory: $metadata_path
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

Planning matrix:
- OpenSpec -> use for new capability, breaking change, architecture shift, or ambiguous intent
- bd -> use for executable code-change tracking after approval
- docs/exec-plans/README.md -> use for long-running, multi-session, or cross-cutting work

Follow-up routers:
- docs/agent/review.md
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
