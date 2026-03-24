#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
cd "$root"

require_command openspec

log "Validate OpenSpec"
openspec validate --all --strict --no-interactive

log "Verify traceability"
"$root/scripts/llm/verify-traceability.sh"

log "Check skill bindings"
"$root/scripts/qa/check-skill-bindings.sh"

log "Check agent-facing docs and context"
"$root/scripts/qa/check-agent-docs.sh"

log "Baseline agent verification passed"
