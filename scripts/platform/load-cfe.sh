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

PROFILE_INPUT=""
RUN_ROOT_INPUT=""
DRY_RUN=0
CAPABILITY_DRY_RUN=0
TARGET_INPUT=""
EXPLICIT_EXTENSIONS=()

ADAPTER=""
SOURCE_ROOT=""
PROFILE_PATH=""
RUN_ROOT=""
STDOUT_LOG=""
STDERR_LOG=""

SELECTED_EXTENSIONS=()
FAILED_EXTENSIONS=()
FAILED_EXTENSION=""
FAILED_STEP=""

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/load-cfe.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>   Directory for wrapper summary and per-extension artifacts
  --target <id>      Target id from automation/context/target-matrix.json
  --extension <name> Load only the specified extension (repeatable)
  --dry-run          Resolve ibcmd commands and write dry-run summaries only
  -h, --help         Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

json_array_from_lines() {
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  printf '%s\n' "$@" | jq -R . | jq -s .
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
        EXPLICIT_EXTENSIONS+=("$2")
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        CAPABILITY_DRY_RUN=1
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

  mktemp -d "${TMPDIR:-/tmp}/1c-load-cfe.XXXXXX"
}

collect_extension_names() {
  local source_root="$1"
  local extension_name=""
  local path=""

  SELECTED_EXTENSIONS=()
  if target_matrix_enabled "$PROJECT_ROOT"; then
    if [ "${#EXPLICIT_EXTENSIONS[@]}" -gt 0 ]; then
      target_require_requested "$PROJECT_ROOT" "$TARGET_INPUT"
      for extension_name in "${EXPLICIT_EXTENSIONS[@]}"; do
        [ -d "$source_root/$extension_name" ] || fail "extension source not found under $source_root: $extension_name"
        target_extensions_json "$PROJECT_ROOT" "$TARGET_INPUT" |
          jq -e --arg extension "$extension_name" 'index($extension) != null' >/dev/null ||
          fail "requested extension is not present in target matrix for target=$TARGET_INPUT: $extension_name"
        SELECTED_EXTENSIONS+=("$extension_name")
      done
      return 0
    fi
    target_fill_extensions_array "$PROJECT_ROOT" "$TARGET_INPUT" SELECTED_EXTENSIONS
    return 0
  fi

  if [ "${#EXPLICIT_EXTENSIONS[@]}" -gt 0 ]; then
    for extension_name in "${EXPLICIT_EXTENSIONS[@]}"; do
      [ -d "$source_root/$extension_name" ] || fail "extension source not found under $source_root: $extension_name"
      SELECTED_EXTENSIONS+=("$extension_name")
    done
    return 0
  fi

  while IFS= read -r path; do
    [ -n "$path" ] || continue
    SELECTED_EXTENSIONS+=("$(basename -- "$path")")
  done < <(find "$source_root" -mindepth 1 -maxdepth 1 -type d | sort)
}

summary_string_field_or_empty() {
  local summary_path="$1"
  local expr="$2"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r "$expr // empty" "$summary_path"
}

summary_number_field_or_empty() {
  local summary_path="$1"
  local expr="$2"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r "($expr // empty)" "$summary_path"
}

redact_command_arg() {
  local value="$1"

  case "$value" in
    --password=*|--db-pwd=*)
      printf '%s\n' "${value%%=*}=__REDACTED_SECRET__"
      ;;
    *)
      printf '%s\n' "$value"
      ;;
  esac
}

write_redacted_command_file() {
  local command_path="$1"
  local redacted=""

  : >"$command_path"
  shift
  for redacted in "$@"; do
    printf '%q ' "$(redact_command_arg "$redacted")" >>"$command_path"
  done
  printf '\n' >>"$command_path"
}

append_log_line() {
  local target="$1"
  shift

  printf '%s\n' "$*" >>"$target"
}

build_step_command() {
  local step="$1"
  local extension_name="$2"
  local extension_source_dir="$3"
  local array_name="$4"
  local binary_path=""
  local -n out_ref="$array_name"

  binary_path="$(ibcmd_binary_path)"
  out_ref=("$binary_path" "config")
  case "$step" in
    import)
      out_ref+=("import")
      append_ibcmd_server_access_args out_ref
      append_ibcmd_target_args out_ref
      append_ibcmd_infobase_auth_args out_ref
      out_ref+=("--extension=$extension_name" "$extension_source_dir")
      ;;
    check)
      out_ref+=("check")
      append_ibcmd_server_access_args out_ref
      append_ibcmd_target_args out_ref
      append_ibcmd_infobase_auth_args out_ref
      out_ref+=("--extension=$extension_name" "--force")
      ;;
    apply)
      out_ref+=("apply")
      append_ibcmd_server_access_args out_ref
      append_ibcmd_target_args out_ref
      append_ibcmd_infobase_auth_args out_ref
      out_ref+=("--extension=$extension_name" "--force")
      ;;
    *)
      fail "unsupported extension step: $step"
      ;;
  esac
}

write_step_summary() {
  local summary_path="$1"
  local step_id="$2"
  local status="$3"
  local exit_code="$4"
  local started_at="$5"
  local finished_at="$6"
  local stdout_log="$7"
  local stderr_log="$8"
  local command_txt="$9"

  jq -n \
    --arg step_id "$step_id" \
    --arg status "$status" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --arg command_txt "$command_txt" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    '{
      id: $step_id,
      status: $status,
      exit_code: $exit_code,
      dry_run: $dry_run,
      started_at: $started_at,
      finished_at: $finished_at,
      artifacts: {
        command_txt: $command_txt,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$summary_path"
}

run_extension_step() {
  local extension_name="$1"
  local extension_source_dir="$2"
  local extension_run_root="$3"
  local step_id="$4"
  local step_summary_path="$extension_run_root/$step_id.summary.json"
  local step_command_path="$extension_run_root/$step_id.command.txt"
  local step_stdout_log="$extension_run_root/$step_id.stdout.log"
  local step_stderr_log="$extension_run_root/$step_id.stderr.log"
  local extension_stdout_log="$extension_run_root/stdout.log"
  local extension_stderr_log="$extension_run_root/stderr.log"
  local started_at=""
  local finished_at=""
  local status="success"
  local exit_code=0
  local -a command=()

  : >"$step_stdout_log"
  : >"$step_stderr_log"

  build_step_command "$step_id" "$extension_name" "$extension_source_dir" command
  write_redacted_command_file "$step_command_path" "${command[@]}"

  started_at="$(timestamp_utc)"
  append_log_line "$STDOUT_LOG" "[load-cfe] extension=$extension_name step=$step_id started"
  append_log_line "$extension_stdout_log" "[load-cfe] extension=$extension_name step=$step_id started"

  if [ "$DRY_RUN" = "1" ]; then
    status="dry-run"
  else
    set +e
    "${command[@]}" >"$step_stdout_log" 2>"$step_stderr_log"
    exit_code=$?
    set -e
    if [ "$exit_code" -ne 0 ]; then
      status="failed"
    fi
  fi

  finished_at="$(timestamp_utc)"
  append_log_line "$extension_stdout_log" "[load-cfe] extension=$extension_name step=$step_id status=$status exit_code=$exit_code"
  append_log_line "$STDOUT_LOG" "[load-cfe] extension=$extension_name step=$step_id status=$status exit_code=$exit_code"
  if [ "$status" = "failed" ]; then
    append_log_line "$extension_stderr_log" "[load-cfe] extension=$extension_name step=$step_id failed"
    append_log_line "$STDERR_LOG" "[load-cfe] extension=$extension_name step=$step_id failed"
  fi

  write_step_summary \
    "$step_summary_path" \
    "$step_id" \
    "$status" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$step_stdout_log" \
    "$step_stderr_log" \
    "$step_command_path"

  if [ "$status" = "failed" ]; then
    return "$exit_code"
  fi
}

write_extension_summary() {
  local extension_name="$1"
  local extension_source_dir="$2"
  local extension_run_root="$3"
  local status="$4"
  local exit_code="$5"
  local started_at="$6"
  local finished_at="$7"
  local failed_step="$8"
  local summary_path="$extension_run_root/summary.json"
  local stdout_log="$extension_run_root/stdout.log"
  local stderr_log="$extension_run_root/stderr.log"
  local steps_json='[]'
  local step_id=""
  local step_summary_path=""
  local step_status=""
  local step_exit_code=""
  local step_started_at=""
  local step_finished_at=""
  local step_command_txt=""
  local step_stdout_log=""
  local step_stderr_log=""

  for step_id in import check apply; do
    step_summary_path="$extension_run_root/$step_id.summary.json"
    step_status="$(summary_string_field_or_empty "$step_summary_path" '.status')"
    step_exit_code="$(summary_number_field_or_empty "$step_summary_path" '.exit_code')"
    step_started_at="$(summary_string_field_or_empty "$step_summary_path" '.started_at')"
    step_finished_at="$(summary_string_field_or_empty "$step_summary_path" '.finished_at')"
    step_command_txt="$(summary_string_field_or_empty "$step_summary_path" '.artifacts.command_txt')"
    step_stdout_log="$(summary_string_field_or_empty "$step_summary_path" '.artifacts.stdout_log')"
    step_stderr_log="$(summary_string_field_or_empty "$step_summary_path" '.artifacts.stderr_log')"

    steps_json="$(jq -cn \
      --argjson acc "$steps_json" \
      --arg step_id "$step_id" \
      --arg step_status "$step_status" \
      --arg step_started_at "$step_started_at" \
      --arg step_finished_at "$step_finished_at" \
      --arg step_command_txt "$step_command_txt" \
      --arg step_stdout_log "$step_stdout_log" \
      --arg step_stderr_log "$step_stderr_log" \
      --argjson step_exit_code "$(if [ -n "$step_exit_code" ]; then printf '%s' "$step_exit_code"; else printf 'null'; fi)" \
      '$acc + [{
        id: $step_id,
        status: (if $step_status == "" then null else $step_status end),
        exit_code: $step_exit_code,
        started_at: (if $step_started_at == "" then null else $step_started_at end),
        finished_at: (if $step_finished_at == "" then null else $step_finished_at end),
        artifacts: {
          command_txt: (if $step_command_txt == "" then null else $step_command_txt end),
          stdout_log: (if $step_stdout_log == "" then null else $step_stdout_log end),
          stderr_log: (if $step_stderr_log == "" then null else $step_stderr_log end)
        }
      }]')"
  done

  jq -n \
    --arg status "$status" \
    --arg extension_name "$extension_name" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$extension_run_root" \
    --arg source_path "$extension_source_dir" \
    --arg summary_json "$summary_path" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg adapter "$ADAPTER" \
    --arg failed_step "$failed_step" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson steps "$steps_json" \
    '{
      status: $status,
      extension_name: $extension_name,
      profile_path: $profile_path,
      run_root: $run_root,
      source_path: $source_path,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      driver: "ibcmd",
      adapter: $adapter,
      failed_step: (if $failed_step == "" then null else $failed_step end),
      execution: {
        source: "load-cfe-wrapper",
        executor: "direct",
        mode: "ibcmd-sequential-extension-import-check-apply"
      },
      steps: $steps,
      failure: (if $failed_step == "" then null else {
        classification: "extension-sync failed",
        extension_name: $extension_name,
        step: $failed_step
      } end),
      artifacts: {
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$summary_path"
}

run_extension_sync() {
  local extension_name="$1"
  local extension_source_dir="$SOURCE_ROOT/$extension_name"
  local extension_run_root="$RUN_ROOT/extensions/$extension_name"
  local stdout_log="$extension_run_root/stdout.log"
  local stderr_log="$extension_run_root/stderr.log"
  local started_at=""
  local finished_at=""
  local status="success"
  local exit_code=0
  local failed_step=""
  local step_id=""

  mkdir -p "$extension_run_root"
  : >"$stdout_log"
  : >"$stderr_log"

  started_at="$(timestamp_utc)"
  for step_id in import check apply; do
    if run_extension_step "$extension_name" "$extension_source_dir" "$extension_run_root" "$step_id"; then
      :
    else
      exit_code=$?
      status="failed"
      failed_step="$step_id"
      break
    fi
  done

  if [ "$status" = "success" ] && [ "$DRY_RUN" = "1" ]; then
    status="dry-run"
  fi

  finished_at="$(timestamp_utc)"
  write_extension_summary \
    "$extension_name" \
    "$extension_source_dir" \
    "$extension_run_root" \
    "$status" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$failed_step"

  if [ "$status" = "failed" ]; then
    FAILED_EXTENSION="$extension_name"
    FAILED_STEP="$failed_step"
    FAILED_EXTENSIONS=("$extension_name")
    return "$exit_code"
  fi
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local started_at="$3"
  local finished_at="$4"
  local selected_extensions_json=""
  local failed_extensions_json=""
  local results_json='[]'
  local extension_name=""
  local extension_run_root=""
  local extension_summary_path=""
  local extension_stdout_log=""
  local extension_stderr_log=""
  local extension_status=""
  local extension_failed_step=""
  local extension_exit_code=""

  selected_extensions_json="$(json_array_from_lines "${SELECTED_EXTENSIONS[@]}")"
  failed_extensions_json="$(json_array_from_lines "${FAILED_EXTENSIONS[@]}")"

  for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
    extension_run_root="$RUN_ROOT/extensions/$extension_name"
    extension_summary_path="$extension_run_root/summary.json"
    extension_stdout_log="$extension_run_root/stdout.log"
    extension_stderr_log="$extension_run_root/stderr.log"
    extension_status="$(summary_string_field_or_empty "$extension_summary_path" '.status')"
    extension_failed_step="$(summary_string_field_or_empty "$extension_summary_path" '.failed_step')"
    extension_exit_code="$(summary_number_field_or_empty "$extension_summary_path" '.exit_code')"

    results_json="$(jq -cn \
      --argjson acc "$results_json" \
      --arg extension_name "$extension_name" \
      --arg run_root "$extension_run_root" \
      --arg summary_json "$extension_summary_path" \
      --arg stdout_log "$extension_stdout_log" \
      --arg stderr_log "$extension_stderr_log" \
      --arg status_value "$extension_status" \
      --arg failed_step "$extension_failed_step" \
      --argjson extension_exit_code "$(if [ -n "$extension_exit_code" ]; then printf '%s' "$extension_exit_code"; else printf 'null'; fi)" \
      '$acc + [{
        extension_name: $extension_name,
        run_root: $run_root,
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log,
        status: (if $status_value == "" then null else $status_value end),
        exit_code: $extension_exit_code,
        failed_step: (if $failed_step == "" then null else $failed_step end)
      }]')"
  done

  jq -n \
    --arg status "$status" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg summary_json "$RUN_ROOT/summary.json" \
    --arg stdout_log "$STDOUT_LOG" \
    --arg stderr_log "$STDERR_LOG" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg source_root "$SOURCE_ROOT" \
    --arg target_id "$TARGET_INPUT" \
    --arg adapter "$ADAPTER" \
    --arg failed_extension "$FAILED_EXTENSION" \
    --arg failed_step "$FAILED_STEP" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson selected_extensions "$selected_extensions_json" \
    --argjson failed_extensions "$failed_extensions_json" \
    --argjson results "$results_json" \
    '{
      status: $status,
      capability: {
        id: "load-cfe",
        label: "Load 1C extensions"
      },
      profile_path: $profile_path,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      driver: "ibcmd",
      adapter: $adapter,
      execution: {
        source: "load-cfe-wrapper",
        strategy: "ibcmd-sequential-extension-import-check-apply",
        mode: "ibcmd-sequential-extension-import-check-apply"
      },
      extension_source: {
        root: $source_root,
        target_id: (if $target_id == "" then null else $target_id end),
        selected_names: $selected_extensions,
        failed_names: $failed_extensions
      },
      failed_extension: (if $failed_extension == "" then null else $failed_extension end),
      failed_step: (if $failed_step == "" then null else $failed_step end),
      failure: (if $failed_extension == "" then null else {
        classification: "extension-sync failed",
        extension_name: $failed_extension,
        step: $failed_step,
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

ADAPTER="${RUNTIME_PROFILE_RUNNER_ADAPTER:-}"
validate_ibcmd_capability_support "load-src" "$ADAPTER"

collect_extension_names "$SOURCE_ROOT"
if [ "${#SELECTED_EXTENSIONS[@]}" -eq 0 ]; then
  fail "no extensions found under $SOURCE_ROOT"
fi

started_at="$(timestamp_utc)"
status="success"
exit_code=0

append_log_line "$STDOUT_LOG" "[load-cfe] profile=$PROFILE_PATH"
append_log_line "$STDOUT_LOG" "[load-cfe] source_root=$SOURCE_ROOT"
append_log_line "$STDOUT_LOG" "[load-cfe] adapter=$ADAPTER"
append_log_line "$STDOUT_LOG" "[load-cfe] extensions=${SELECTED_EXTENSIONS[*]}"

for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
  if run_extension_sync "$extension_name"; then
    :
  else
    exit_code=$?
    status="failed"
    break
  fi
done

if [ "$status" = "success" ] && [ "$DRY_RUN" = "1" ]; then
  status="dry-run"
fi

finished_at="$(timestamp_utc)"
write_summary "$status" "$exit_code" "$started_at" "$finished_at"

if [ "$status" = "failed" ]; then
  exit "$exit_code"
fi
