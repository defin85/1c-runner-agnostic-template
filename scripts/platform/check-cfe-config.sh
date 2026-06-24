#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/target-matrix.sh
source "$SCRIPT_DIR/../lib/target-matrix.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"
# shellcheck source=../lib/designer-diagnostics.sh
source "$SCRIPT_DIR/../lib/designer-diagnostics.sh"

PROFILE_INPUT=""
RUN_ROOT_INPUT=""
DRY_RUN=0
TARGET_INPUT=""
REQUESTED_EXTENSIONS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/check-cfe-config.sh [options]

Options:
  --profile <file>       Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>       Directory for wrapper summary and extension-level artifacts
  --target <id>          Target id from automation/context/target-matrix.json
  --extension <name>     Check only the specified extension (repeatable)
  --dry-run              Resolve config verification commands and write dry-run summaries only
  -h, --help             Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || fail "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || fail "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --target)
        [ "$#" -ge 2 ] || fail "--target requires a value"
        TARGET_INPUT="$2"
        shift 2
        ;;
      --extension)
        [ "$#" -ge 2 ] || fail "--extension requires a value"
        REQUESTED_EXTENSIONS+=("$2")
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
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

resolve_profile_path() {
  local resolved=""

  resolved="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$resolved" ] || fail "runtime profile is required; pass --profile <file> or create env/local.json"
  printf '%s\n' "$(canonical_path "$resolved")"
}

resolve_run_root() {
  local resolved=""

  if [ -n "$RUN_ROOT_INPUT" ]; then
    resolved="$(canonical_path "$RUN_ROOT_INPUT")"
    mkdir -p "$resolved"
    printf '%s\n' "$resolved"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/1c-check-cfe-config.XXXXXX"
}

resolve_adapter_wrapper_path() {
  local adapter="$1"

  case "$adapter" in
    direct-platform)
      printf '%s\n' "$PROJECT_ROOT/scripts/adapters/direct-platform.sh"
      ;;
    remote-windows)
      printf '%s\n' "$PROJECT_ROOT/scripts/adapters/remote-windows.sh"
      ;;
    *)
      fail "unsupported RUNNER_ADAPTER for check-cfe-config: $adapter"
      ;;
  esac
}

json_array_from_lines() {
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  printf '%s\n' "$@" | jq -R . | jq -s .
}

collect_available_extensions() {
  local source_root="$1"
  local path=""

  AVAILABLE_EXTENSIONS=()
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    AVAILABLE_EXTENSIONS+=("$(basename -- "$path")")
  done < <(find "$source_root" -mindepth 1 -maxdepth 1 -type d | sort)
}

resolve_selected_extensions() {
  local requested=""
  local available=""
  local exists=0

  SELECTED_EXTENSIONS=()
  if target_matrix_enabled "$PROJECT_ROOT"; then
    if [ "${#REQUESTED_EXTENSIONS[@]}" -gt 0 ]; then
      fail "--extension cannot be combined with --target in a multi-target workspace"
    fi
    target_fill_extensions_array "$PROJECT_ROOT" "$TARGET_INPUT" SELECTED_EXTENSIONS
    return 0
  fi

  if [ "${#REQUESTED_EXTENSIONS[@]}" -eq 0 ]; then
    SELECTED_EXTENSIONS=("${AVAILABLE_EXTENSIONS[@]}")
    return 0
  fi

  for requested in "${REQUESTED_EXTENSIONS[@]}"; do
    exists=0
    for available in "${AVAILABLE_EXTENSIONS[@]}"; do
      if [ "$available" = "$requested" ]; then
        exists=1
        break
      fi
    done

    if [ "$exists" -ne 1 ]; then
      fail "requested extension is not present under $SOURCE_ROOT: $requested"
    fi

    SELECTED_EXTENSIONS+=("$requested")
  done
}

write_extension_summary() {
  local extension_name="$1"
  local status="$2"
  local exit_code="$3"
  local started_at="$4"
  local finished_at="$5"
  local extension_run_root="$6"
  local stdout_log="$7"
  local stderr_log="$8"
  local designer_out_log="$9"
  local diagnostics_json_path="${10}"
  local blocking_diagnostics_json_path="${11}"
  local inherited_diagnostics_json_path="${12}"
  local diagnostics_count="${13}"
  local blocking_diagnostics_count="${14}"
  local inherited_diagnostics_count="${15}"
  local designer_exit_code="${16}"
  local summary_path="${17}"

  jq -n \
    --arg status "$status" \
    --arg extension_name "$extension_name" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$extension_run_root" \
    --arg summary_json "$summary_path" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --arg designer_out_log "$designer_out_log" \
    --arg diagnostics_json_path "$diagnostics_json_path" \
    --arg blocking_diagnostics_json_path "$blocking_diagnostics_json_path" \
    --arg inherited_diagnostics_json_path "$inherited_diagnostics_json_path" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg adapter "$ADAPTER" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson designer_exit_code "$designer_exit_code" \
    --argjson diagnostics_count "$diagnostics_count" \
    --argjson blocking_diagnostics_count "$blocking_diagnostics_count" \
    --argjson inherited_diagnostics_count "$inherited_diagnostics_count" \
    --slurpfile diagnostics "$diagnostics_json_path" \
    --slurpfile blocking_diagnostics "$blocking_diagnostics_json_path" \
    --slurpfile inherited_diagnostics "$inherited_diagnostics_json_path" \
    '{
      status: $status,
      extension_name: $extension_name,
      profile_path: $profile_path,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      designer_exit_code: $designer_exit_code,
      dry_run: $dry_run,
      adapter: $adapter,
      diagnostics_count: $diagnostics_count,
      blocking_diagnostics_count: $blocking_diagnostics_count,
      inherited_diagnostics_count: $inherited_diagnostics_count,
      diagnostics: (if ($diagnostics | length) == 0 then [] else $diagnostics[0] end),
      blocking_diagnostics: (if ($blocking_diagnostics | length) == 0 then [] else $blocking_diagnostics[0] end),
      inherited_diagnostics: (if ($inherited_diagnostics | length) == 0 then [] else $inherited_diagnostics[0] end),
      execution: {
        source: "check-cfe-config-wrapper",
        executor: "adapter-wrapper",
        mode: "designer-check-config"
      },
      artifacts: {
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log,
        designer_out_log: $designer_out_log,
        diagnostics_json: $diagnostics_json_path,
        blocking_diagnostics_json: $blocking_diagnostics_json_path,
        inherited_diagnostics_json: $inherited_diagnostics_json_path
      }
    }' >"$summary_path"
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local started_at="$3"
  local finished_at="$4"
  local failed_extensions_json="$5"
  local selected_extensions_json=""
  local results_json='[]'
  local extension_name=""
  local extension_run_root=""
  local extension_summary_path=""
  local extension_stdout_log=""
  local extension_stderr_log=""
  local extension_status=""
  local extension_designer_out_log=""
  local extension_diagnostics_count=""
  local extension_blocking_diagnostics_count=""
  local extension_inherited_diagnostics_count=""

  selected_extensions_json="$(json_array_from_lines "${SELECTED_EXTENSIONS[@]}")"

  for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
    extension_run_root="$RUN_ROOT/extensions/$extension_name"
    extension_summary_path="$extension_run_root/summary.json"
    extension_stdout_log="$extension_run_root/stdout.log"
    extension_stderr_log="$extension_run_root/stderr.log"
    extension_status="$(summary_string_field_or_empty "$extension_summary_path" '.status')"
    extension_designer_out_log="$(summary_string_field_or_empty "$extension_summary_path" '.artifacts.designer_out_log')"
    extension_diagnostics_count="$(summary_number_field_or_empty "$extension_summary_path" '.diagnostics_count')"
    extension_blocking_diagnostics_count="$(summary_number_field_or_empty "$extension_summary_path" '.blocking_diagnostics_count')"
    extension_inherited_diagnostics_count="$(summary_number_field_or_empty "$extension_summary_path" '.inherited_diagnostics_count')"

    results_json="$(jq -cn \
      --argjson acc "$results_json" \
      --arg extension_name "$extension_name" \
      --arg run_root "$extension_run_root" \
      --arg summary_json "$extension_summary_path" \
      --arg stdout_log "$extension_stdout_log" \
      --arg stderr_log "$extension_stderr_log" \
      --arg designer_out_log "$extension_designer_out_log" \
      --arg status_value "$extension_status" \
      --arg diagnostics_count "$extension_diagnostics_count" \
      --arg blocking_diagnostics_count "$extension_blocking_diagnostics_count" \
      --arg inherited_diagnostics_count "$extension_inherited_diagnostics_count" \
      '$acc + [{
        extension_name: $extension_name,
        run_root: $run_root,
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log,
        designer_out_log: (if $designer_out_log == "" then null else $designer_out_log end),
        diagnostics_count: (if $diagnostics_count == "" then null else ($diagnostics_count | tonumber) end),
        blocking_diagnostics_count: (if $blocking_diagnostics_count == "" then null else ($blocking_diagnostics_count | tonumber) end),
        inherited_diagnostics_count: (if $inherited_diagnostics_count == "" then null else ($inherited_diagnostics_count | tonumber) end),
        status: (if $status_value == "" then null else $status_value end)
      }]')"
  done

  jq -n \
    --arg status "$status" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg summary_json "$RUN_ROOT/summary.json" \
    --arg stdout_log "$RUN_ROOT/stdout.log" \
    --arg stderr_log "$RUN_ROOT/stderr.log" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg source_root "$SOURCE_ROOT" \
    --arg target_id "$TARGET_INPUT" \
    --arg adapter "$ADAPTER" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson selected_extensions "$selected_extensions_json" \
    --argjson failed_extensions "$failed_extensions_json" \
    --argjson results "$results_json" \
    '{
      status: $status,
      capability: {
        id: "check-cfe-config",
        label: "Check extension config"
      },
      profile_path: $profile_path,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      adapter: $adapter,
      execution: {
        source: "check-cfe-config-wrapper",
        strategy: "designer-check-config"
      },
      extension_source: {
        root: $source_root,
        target_id: (if $target_id == "" then null else $target_id end),
        selected_names: $selected_extensions,
        failed_names: $failed_extensions
      },
      failure: (if ($failed_extensions | length) == 0 then null else {
        classification: "extension-config-verification failed",
        extensions: $failed_extensions
      } end),
      results: $results,
      artifacts: {
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$RUN_ROOT/summary.json"
}

run_extension_check() {
  local extension_name="$1"
  local extension_run_root="$RUN_ROOT/extensions/$extension_name"
  local summary_path="$extension_run_root/summary.json"
  local stdout_log="$extension_run_root/stdout.log"
  local stderr_log="$extension_run_root/stderr.log"
  local designer_out_log="$extension_run_root/designer.out.log"
  local diagnostics_json_path="$extension_run_root/diagnostics.json"
  local blocking_diagnostics_json_path="$extension_run_root/blocking-diagnostics.json"
  local inherited_diagnostics_json_path="$extension_run_root/inherited-diagnostics.json"
  local started_at=""
  local finished_at=""
  local status="success"
  local exit_code=0
  local designer_exit_code=0
  local diagnostics_count=0
  local blocking_diagnostics_count=0
  local inherited_diagnostics_count=0
  local -a command=()
  local -a adapter_env=()
  local -a command_env=()

  mkdir -p "$extension_run_root"
  : >"$stdout_log"
  : >"$stderr_log"
  : >"$designer_out_log"
  printf '[]\n' >"$diagnostics_json_path"
  printf '[]\n' >"$blocking_diagnostics_json_path"
  printf '[]\n' >"$inherited_diagnostics_json_path"

  build_designer_command command \
    "/DisableStartupDialogs" \
    "/DisableStartupMessages" \
    "/Out" "$designer_out_log" \
    "/CheckConfig" \
    "-HandlersExistence" \
    "-ThinClient" \
    "-WebClient" \
    "-Server" \
    "-ThickClientManagedApplication" \
    "-ThickClientServerManagedApplication" \
    "-Extension" "$extension_name"
  prepare_adapter_wrapper_env "$ADAPTER" adapter_env
  command_env=(
    "ONEC_PROJECT_ROOT=$PROJECT_ROOT"
    "ONEC_PROFILE_PATH=$PROFILE_PATH"
    "ONEC_RUNNER_ADAPTER=$ADAPTER"
    "ONEC_CAPABILITY_ID=check-cfe-config"
    "ONEC_CAPABILITY_LABEL=Check extension config"
    "ONEC_CAPABILITY_RUN_ROOT=$extension_run_root"
  )

  started_at="$(timestamp_utc)"
  printf '[check-cfe-config] extension=%s\n' "$extension_name" >>"$stdout_log"

  if [ "$DRY_RUN" = "1" ]; then
    status="dry-run"
  else
    set +e
    env "${command_env[@]}" "${adapter_env[@]}" "$ADAPTER_WRAPPER" "${command[@]}" >>"$stdout_log" 2>>"$stderr_log"
    designer_exit_code=$?
    set -e
    exit_code="$designer_exit_code"
    if [ "$designer_exit_code" -ne 0 ]; then
      status="failed"
    fi

    designer_out_diagnostics_to_json_file "$designer_out_log" "$exit_code" "$diagnostics_json_path"
    classify_extension_config_diagnostics \
      "$PROJECT_ROOT" \
      "$diagnostics_json_path" \
      "$diagnostics_json_path" \
      "$blocking_diagnostics_json_path" \
      "$inherited_diagnostics_json_path"
    diagnostics_count="$(json_array_length_from_file "$diagnostics_json_path")"
    blocking_diagnostics_count="$(json_array_length_from_file "$blocking_diagnostics_json_path")"
    inherited_diagnostics_count="$(json_array_length_from_file "$inherited_diagnostics_json_path")"
    if [ "$blocking_diagnostics_count" -gt 0 ]; then
      status="failed"
      if [ "$exit_code" -eq 0 ]; then
        exit_code=1
      fi
    elif [ "$inherited_diagnostics_count" -gt 0 ]; then
      status="success"
      exit_code=0
    elif [ "$designer_exit_code" -ne 0 ]; then
      status="failed"
    fi
  fi

  finished_at="$(timestamp_utc)"
  write_extension_summary \
    "$extension_name" \
    "$status" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$extension_run_root" \
    "$stdout_log" \
    "$stderr_log" \
    "$designer_out_log" \
    "$diagnostics_json_path" \
    "$blocking_diagnostics_json_path" \
    "$inherited_diagnostics_json_path" \
    "$diagnostics_count" \
    "$blocking_diagnostics_count" \
    "$inherited_diagnostics_count" \
    "$designer_exit_code" \
    "$summary_path"

  if [ "$status" = "failed" ]; then
    return "$exit_code"
  fi
  return 0
}

parse_args "$@"

require_command jq

PROFILE_PATH="$(resolve_profile_path)"
RUN_ROOT="$(resolve_run_root)"
SOURCE_ROOT="$(resolve_project_tree_path "./src/cfe")"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"

mkdir -p "$RUN_ROOT"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded
target_require_requested "$PROJECT_ROOT" "$TARGET_INPUT"
ADAPTER="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
ADAPTER_WRAPPER="$(resolve_adapter_wrapper_path "$ADAPTER")"

collect_available_extensions "$SOURCE_ROOT"
if [ "${#AVAILABLE_EXTENSIONS[@]}" -eq 0 ]; then
  fail "no extensions found under $SOURCE_ROOT"
fi
resolve_selected_extensions

printf '[check-cfe-config] profile=%s\n' "$PROFILE_PATH" >>"$STDOUT_LOG"
printf '[check-cfe-config] adapter=%s\n' "$ADAPTER" >>"$STDOUT_LOG"
printf '[check-cfe-config] source_root=%s\n' "$SOURCE_ROOT" >>"$STDOUT_LOG"
printf '[check-cfe-config] selected_extensions=%s\n' "${SELECTED_EXTENSIONS[*]}" >>"$STDOUT_LOG"

started_at="$(timestamp_utc)"
status="success"
exit_code=0
FAILED_EXTENSIONS=()

for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
  if run_extension_check "$extension_name"; then
    :
  else
    extension_exit_code=$?
    if [ "$exit_code" -eq 0 ]; then
      exit_code="$extension_exit_code"
    fi
    FAILED_EXTENSIONS+=("$extension_name")
    status="failed"
  fi
done

if [ "$status" = "success" ] && [ "$DRY_RUN" = "1" ]; then
  status="dry-run"
fi

finished_at="$(timestamp_utc)"
failed_extensions_json="$(json_array_from_lines "${FAILED_EXTENSIONS[@]}")"
write_summary \
  "$status" \
  "$exit_code" \
  "$started_at" \
  "$finished_at" \
  "$failed_extensions_json"

if [ "$status" = "failed" ]; then
  if [ "$exit_code" -eq 0 ]; then
    exit 1
  fi
  exit "$exit_code"
fi
