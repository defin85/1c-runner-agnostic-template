#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

PROFILE_INPUT="${ONEC_PROFILE_PATH:-}"
SOURCE_ROOT_INPUT=""
OUTPUT_EPF_INPUT=""
LOG_OUT_INPUT=""

usage() {
  cat <<'EOF'
Usage: ./scripts/test/build-xunit-epf.sh [options]

Options:
  --profile <file>        Runtime profile JSON.
  --source-root <dir>     Source tree root for external data processor.
  --output-epf <file>     Result EPF file path.
  --log-out <file>        Designer /Out log path.
  -h, --help              Show this help.
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

array_length() {
  local array_name="$1"
  local item=""
  local count=0
  declare -n array_ref="$array_name"

  for item in "${array_ref[@]}"; do
    count=$((count + 1))
  done

  printf '%s\n' "$count"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || fail "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --source-root)
        [ "$#" -ge 2 ] || fail "--source-root requires a value"
        SOURCE_ROOT_INPUT="$2"
        shift 2
        ;;
      --output-epf)
        [ "$#" -ge 2 ] || fail "--output-epf requires a value"
        OUTPUT_EPF_INPUT="$2"
        shift 2
        ;;
      --log-out)
        [ "$#" -ge 2 ] || fail "--log-out requires a value"
        LOG_OUT_INPUT="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

resolve_required_path() {
  local value="$1"
  local label="$2"

  [ -n "$value" ] || fail "$label is required"
  printf '%s\n' "$(canonical_path "$value")"
}

resolve_dump_root_file() {
  local source_path="$1"
  local candidate=""

  if [ -f "$source_path" ]; then
    printf '%s\n' "$source_path"
    return 0
  fi

  if [ ! -d "$source_path" ]; then
    fail "source root not found: $source_path"
  fi

  candidate="$source_path/$(basename -- "$source_path").xml"
  if [ -f "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  mapfile -t xml_candidates < <(find "$source_path" -maxdepth 1 -type f -name '*.xml' | sort)
  if [ "$(array_length xml_candidates)" -eq 1 ]; then
    printf '%s\n' "${xml_candidates[0]}"
    return 0
  fi

  fail "failed to resolve dump root xml under $source_path"
}

parse_args "$@"

require_command jq

PROFILE_PATH="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
[ -n "$PROFILE_PATH" ] || fail "runtime profile is required"
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded

[ "${RUNTIME_PROFILE_RUNNER_ADAPTER:-}" = "direct-platform" ] || fail "runnerAdapter=direct-platform is required"

SOURCE_ROOT="$(resolve_required_path "$SOURCE_ROOT_INPUT" "--source-root")"
DUMP_ROOT_FILE="$(resolve_dump_root_file "$SOURCE_ROOT")"
OUTPUT_EPF="$(resolve_required_path "$OUTPUT_EPF_INPUT" "--output-epf")"

if [ -n "$LOG_OUT_INPUT" ]; then
  LOG_OUT="$(canonical_path "$LOG_OUT_INPUT")"
else
  LOG_OUT="$OUTPUT_EPF.out.log"
fi

mkdir -p "$(dirname -- "$OUTPUT_EPF")" "$(dirname -- "$LOG_OUT")"
rm -f "$OUTPUT_EPF"

declare -a DESIGNER_CMD=()
declare -a ADAPTER_ENV=()

DESIGNER_CMD=("$(platform_binary_path)" "DESIGNER")
append_connection_args DESIGNER_CMD
append_auth_args DESIGNER_CMD
DESIGNER_CMD+=(
  "/DisableStartupDialogs"
  "/DisableStartupMessages"
  "/Out" "$LOG_OUT"
  "/LoadExternalDataProcessorOrReportFromFiles" "$DUMP_ROOT_FILE" "$OUTPUT_EPF"
  "-Format" "Hierarchical"
)

prepare_adapter_wrapper_env "direct-platform" ADAPTER_ENV
if [ "$(array_length ADAPTER_ENV)" -gt 0 ]; then
  env "${ADAPTER_ENV[@]}" "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${DESIGNER_CMD[@]}"
else
  "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${DESIGNER_CMD[@]}"
fi

printf '%s\n' "$OUTPUT_EPF"
