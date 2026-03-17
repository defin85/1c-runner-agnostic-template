#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command java
require_env BSL_LANGUAGE_SERVER_JAR

root="$(project_root)"
src_dir="${BSL_FORMAT_SRC:-$root/src/cf}"

cmd=(
  java
  "-Xmx${BSL_LS_XMX:-2g}"
  -jar
  "$BSL_LANGUAGE_SERVER_JAR"
  --format
  --src "$src_dir"
)

log "Format BSL sources"
printf '%q ' "${cmd[@]}"
printf '\n'

if [ "${DRY_RUN:-0}" = "1" ]; then
  exit 0
fi

"${cmd[@]}"
