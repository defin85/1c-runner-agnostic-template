#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
cd "$root"

require_command openspec
require_command jq

log "Validate OpenSpec"
openspec validate --all --strict --no-interactive

log "Verify traceability"
"$root/scripts/llm/verify-traceability.sh"

log "Check skill bindings"
"$root/scripts/qa/check-skill-bindings.sh"

log "Check overlay manifest"
"$root/scripts/qa/check-overlay-manifest.sh"

log "Check agent-facing docs and context"
"$root/scripts/qa/check-agent-docs.sh"

log "Check imported skill readiness contract"
readiness_json="$("$root/scripts/skills/run-imported-skill.sh" --readiness --json)"
printf '%s' "$readiness_json" | jq -e '
  .canonicalTarget == "make imported-skills-readiness" and
  .canonicalCommand == "./scripts/skills/run-imported-skill.sh --readiness" and
  .representative.python.representative_skill == "cf-edit" and
  .representative.node.representative_skill == "web-test" and
  .representative.reference.representative_skill == "form-patterns" and
  .representative.nativeAlias.representative_skill == "db-create" and
  (.representative.python.ready or ((.representative.python.bootstrap_commands | length) > 0)) and
  (.representative.node.ready or ((.representative.node.bootstrap_commands | length) > 0))
' >/dev/null

log "Baseline agent verification passed"
