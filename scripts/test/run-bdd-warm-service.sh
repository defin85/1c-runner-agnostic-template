#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/vanessa-bdd.sh
source "$SCRIPT_DIR/../lib/vanessa-bdd.sh"

CONTOUR_ID="bdd-warm-service"
COMMAND="${1:-}"
PROFILE_INPUT=""
RUN_ROOT=""
VANESSA_SINGLE_PATH=""
WARMUP_FEATURE_PATH=""
LIBRARY_PATHS=()
STEP_DEFINITION_PATHS=()
EXTENSION_SCOPE=()
MISSING_INPUTS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-bdd-warm-service.sh <up|status|run|down> [options]

Options:
  --profile <file>              Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>              Directory for summary.json and logs
  --vanessa-single <file>       Vanessa Automation Single EPF path
  --warmup-feature <file>       Warmup feature path
  --library-path <path>         Vanessa library path (repeatable)
  --step-definitions <path>     Step definitions path (repeatable)
  --extension <name>            Extension scope entry (repeatable)
  -h, --help                    Show this help
EOF
}

json_array_from_args() {
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi
  printf '%s\n' "$@" | jq -R . | jq -s .
}

resolve_profile_path_or_die() {
  local resolved=""

  resolved="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$resolved" ] || die "runtime profile is required; pass --profile <file> or create env/local.json"
  canonical_path "$resolved"
}

resolve_run_root() {
  if [ -n "$RUN_ROOT" ]; then
    mkdir -p "$RUN_ROOT"
    canonical_path "$RUN_ROOT"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/bdd-warm-service.XXXXXX"
}

parse_args() {
  [ -n "$COMMAND" ] || {
    usage
    exit 2
  }
  shift || true

  case "$COMMAND" in
    up|status|run|down)
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unsupported bdd-warm-service command: $COMMAND"
      ;;
  esac

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || die "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || die "--run-root requires a value"
        RUN_ROOT="$2"
        shift 2
        ;;
      --vanessa-single)
        [ "$#" -ge 2 ] || die "--vanessa-single requires a value"
        VANESSA_SINGLE_PATH="$2"
        shift 2
        ;;
      --warmup-feature)
        [ "$#" -ge 2 ] || die "--warmup-feature requires a value"
        WARMUP_FEATURE_PATH="$2"
        shift 2
        ;;
      --library-path)
        [ "$#" -ge 2 ] || die "--library-path requires a value"
        LIBRARY_PATHS+=("$2")
        shift 2
        ;;
      --step-definitions)
        [ "$#" -ge 2 ] || die "--step-definitions requires a value"
        STEP_DEFINITION_PATHS+=("$2")
        shift 2
        ;;
      --extension)
        [ "$#" -ge 2 ] || die "--extension requires a value"
        EXTENSION_SCOPE+=("$2")
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
}

load_profile_defaults() {
  local value=""

  [ -n "$VANESSA_SINGLE_PATH" ] || VANESSA_SINGLE_PATH="$(profile_string '.capabilities.bddWarmService.vanessaSinglePath // empty')"
  [ -n "$WARMUP_FEATURE_PATH" ] || WARMUP_FEATURE_PATH="$(profile_string '.capabilities.bddWarmService.warmupFeaturePath // empty')"

  if [ "${#LIBRARY_PATHS[@]}" -eq 0 ]; then
    while IFS= read -r value; do
      [ -n "$value" ] || continue
      LIBRARY_PATHS+=("$value")
    done < <(profile_jq_raw '.capabilities.bddWarmService.libraryPaths // [] | if type == "array" then .[] else empty end')
  fi
  if [ "${#STEP_DEFINITION_PATHS[@]}" -eq 0 ]; then
    while IFS= read -r value; do
      [ -n "$value" ] || continue
      STEP_DEFINITION_PATHS+=("$value")
    done < <(profile_jq_raw '.capabilities.bddWarmService.stepDefinitionPaths // [] | if type == "array" then .[] else empty end')
  fi
  if [ "${#EXTENSION_SCOPE[@]}" -eq 0 ]; then
    while IFS= read -r value; do
      [ -n "$value" ] || continue
      EXTENSION_SCOPE+=("$value")
    done < <(profile_jq_raw '.capabilities.bddWarmService.extensionScope // [] | if type == "array" then .[] else empty end')
  fi
}

append_missing_path() {
  local label="$1"
  local value="$2"

  if [ -z "$value" ] || [ ! -e "$value" ]; then
    MISSING_INPUTS+=("$label")
  fi
}

validate_inputs() {
  local item=""

  vanessa_bdd_validate_target_binding "$PROJECT_ROOT" MISSING_INPUTS
  append_missing_path "Vanessa Automation Single path" "$VANESSA_SINGLE_PATH"
  append_missing_path "warmup feature path" "$WARMUP_FEATURE_PATH"

  if [ "${#LIBRARY_PATHS[@]}" -eq 0 ]; then
    MISSING_INPUTS+=("library paths")
  else
    for item in "${LIBRARY_PATHS[@]}"; do
      append_missing_path "library path: $item" "$item"
    done
  fi

  if [ "${#STEP_DEFINITION_PATHS[@]}" -eq 0 ]; then
    MISSING_INPUTS+=("step definitions")
  else
    for item in "${STEP_DEFINITION_PATHS[@]}"; do
      append_missing_path "step definitions path: $item" "$item"
    done
  fi

  [ "${#EXTENSION_SCOPE[@]}" -gt 0 ] || MISSING_INPUTS+=("extension scope")
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local classification="$3"
  local message="$4"
  local summary_path="$RUN_ROOT/summary.json"
  local missing_json="[]"
  local libraries_json="[]"
  local steps_json="[]"
  local extensions_json="[]"
  local profile_target=""

  missing_json="$(json_array_from_args "${MISSING_INPUTS[@]}")"
  libraries_json="$(json_array_from_args "${LIBRARY_PATHS[@]}")"
  steps_json="$(json_array_from_args "${STEP_DEFINITION_PATHS[@]}")"
  extensions_json="$(json_array_from_args "${EXTENSION_SCOPE[@]}")"
  profile_target="$(profile_string '.target.id // empty')"

  jq -n \
    --arg status "$status" \
    --arg classification "$classification" \
    --arg message "$message" \
    --arg command "$COMMAND" \
    --arg contour "$CONTOUR_ID" \
    --arg profile_path "$RUNTIME_PROFILE_PATH" \
    --arg profile_target "$profile_target" \
    --arg run_root "$RUN_ROOT" \
    --arg vanessa_single_path "$VANESSA_SINGLE_PATH" \
    --arg warmup_feature_path "$WARMUP_FEATURE_PATH" \
    --argjson exit_code "$exit_code" \
    --argjson missing_inputs "$missing_json" \
    --argjson library_paths "$libraries_json" \
    --argjson step_definition_paths "$steps_json" \
    --argjson extension_scope "$extensions_json" \
    '{
      contour: $contour,
      command: $command,
      status: $status,
      classification: $classification,
      message: $message,
      exitCode: $exit_code,
      missing_inputs: $missing_inputs,
      profile_path: $profile_path,
      runtime_profile: {
        target: (if $profile_target == "" then null else $profile_target end)
      },
      run_root: $run_root,
      inputs: {
        vanessa_single_path: (if $vanessa_single_path == "" then null else $vanessa_single_path end),
        warmup_feature_path: (if $warmup_feature_path == "" then null else $warmup_feature_path end),
        library_paths: $library_paths,
        step_definition_paths: $step_definition_paths,
        extension_scope: $extension_scope
      }
    }' >"$summary_path"
}

parse_args "$@"
require_command jq
RUNTIME_PROFILE_PATH="$(resolve_profile_path_or_die)"
load_runtime_profile "$RUNTIME_PROFILE_PATH"
require_runtime_profile_loaded
RUN_ROOT="$(resolve_run_root)"
mkdir -p "$RUN_ROOT"

load_profile_defaults
validate_inputs

if [ "${#MISSING_INPUTS[@]}" -gt 0 ]; then
  write_summary "failed" 2 "not configured" "Vanessa BDD warm-service is not configured"
  printf 'bdd-warm-service-message=%s\n' "Vanessa BDD warm-service is not configured" >&2
  printf 'bdd-warm-service-run-root=%s\n' "$RUN_ROOT" >&2
  exit 2
fi

MISSING_INPUTS+=("runtime implementation")
write_summary "failed" 2 "not implemented" "Vanessa BDD warm-service runtime launcher is a fail-closed skeleton"
printf 'bdd-warm-service-message=%s\n' "Vanessa BDD warm-service runtime launcher is a fail-closed skeleton" >&2
printf 'bdd-warm-service-run-root=%s\n' "$RUN_ROOT" >&2
exit 2
