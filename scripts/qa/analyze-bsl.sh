#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

require_command java
require_env BSL_LANGUAGE_SERVER_JAR

root="$(project_root)"
src_dir="${BSL_SRC_DIR:-$root/src/cf}"
output_dir="${BSL_REPORT_DIR:-$root/reports/bsl-analysis}"
config_path="${BSL_LANGUAGE_SERVER_CONFIG:-}"
xmx="${BSL_LS_XMX:-2g}"

ensure_dir "$output_dir"

cmd=(
  java
  "-Xmx$xmx"
  -jar
  "$BSL_LANGUAGE_SERVER_JAR"
)

if [ -n "$config_path" ]; then
  cmd+=(--configuration "$config_path")
fi

cmd+=(
  --analyze
  --srcDir "$src_dir"
  --outputDir "$output_dir"
  --reporter json
  --reporter junit
)

log "Run BSL analysis"
printf '%q ' "${cmd[@]}"
printf '\n'

if [ "${DRY_RUN:-0}" = "1" ]; then
  exit 0
fi

"${cmd[@]}"
