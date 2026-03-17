#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command copier

root="$(project_root)"
cd "$root"

cmd=(copier check-update)
cmd+=("$@")

log "Check template updates"
printf '%q ' "${cmd[@]}"
printf '\n'

"${cmd[@]}"
