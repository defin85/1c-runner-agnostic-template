#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"
# shellcheck source=./runtime-profile.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-profile.sh"

CAPABILITY_PROFILE_INPUT=""
CAPABILITY_RUN_ROOT_INPUT=""
CAPABILITY_DRY_RUN="${DRY_RUN:-0}"
CAPABILITY_SHOW_HELP=0
CAPABILITY_SELECTED_FILES_INPUT=""
CAPABILITY_DRIVER=""
CAPABILITY_COMMAND_SOURCE=""
CAPABILITY_COMMAND_EXECUTOR="direct"
CAPABILITY_CONTEXT_JSON="{}"
CAPABILITY_COMMAND=()

reset_capability_cli_state() {
  CAPABILITY_PROFILE_INPUT=""
  CAPABILITY_RUN_ROOT_INPUT=""
  CAPABILITY_DRY_RUN="${DRY_RUN:-0}"
  CAPABILITY_SHOW_HELP=0
  CAPABILITY_SELECTED_FILES_INPUT=""
}

reset_prepared_capability_command() {
  CAPABILITY_DRIVER=""
  CAPABILITY_COMMAND_SOURCE=""
  CAPABILITY_COMMAND_EXECUTOR="direct"
  CAPABILITY_CONTEXT_JSON="{}"
  CAPABILITY_COMMAND=()
}

prepare_adapter_wrapper_env() {
  local _adapter="$1"
  local array_name="$2"
  local -n out_ref="$array_name"

  out_ref=()
}

parse_capability_cli_args() {
  reset_capability_cli_state

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || die "--profile requires a value"
        CAPABILITY_PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || die "--run-root requires a value"
        CAPABILITY_RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --dry-run)
        CAPABILITY_DRY_RUN=1
        shift
        ;;
      --files)
        [ "$#" -ge 2 ] || die "--files requires a value"
        CAPABILITY_SELECTED_FILES_INPUT="$2"
        shift 2
        ;;
      -h|--help)
        CAPABILITY_SHOW_HELP=1
        shift
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
}

capability_help_requested() {
  local arg=""

  for arg in "$@"; do
    case "$arg" in
      -h|--help)
        return 0
        ;;
    esac
  done

  return 1
}

prepare_capability_run_root() {
  local capability_id="$1"
  local requested_root="${2:-}"
  local run_root=""

  if [ -n "$requested_root" ]; then
    run_root="$(canonical_path "$requested_root")"
    mkdir -p "$run_root"
  else
    run_root="$(mktemp -d "${TMPDIR:-/tmp}/1c-${capability_id}.XXXXXX")"
  fi

  printf '%s\n' "$run_root"
}

capability_summary_path() {
  printf '%s/summary.json\n' "$1"
}

set_prepared_capability_command() {
  local driver="$1"
  local source="$2"
  local executor="$3"
  shift 3

  CAPABILITY_DRIVER="$driver"
  CAPABILITY_COMMAND_SOURCE="$source"
  CAPABILITY_COMMAND_EXECUTOR="$executor"
  CAPABILITY_COMMAND=("$@")
}

set_capability_context_json() {
  local json="${1-}"

  if [ -z "$json" ]; then
    json='{}'
  fi

  require_command jq
  CAPABILITY_CONTEXT_JSON="$(jq -c '.' <<<"$json")"
}

trim_capability_csv_item() {
  local value="$1"

  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s\n' "$value"
}

normalize_capability_selected_file() {
  local value="$1"
  local segment=""
  local normalized=""
  local -a segments=()
  local -a stack=()

  if [[ "$value" = /* ]]; then
    die "--files entries must be relative to the configured source tree: $value"
  fi

  IFS='/' read -r -a segments <<<"$value"
  for segment in "${segments[@]}"; do
    case "$segment" in
      ""|".")
        continue
        ;;
      "..")
        set -- "${stack[@]}"
        if [ "$#" -eq 0 ]; then
          die "--files entries must stay within the configured source tree: $value"
        fi
        unset "stack[$(( $# - 1 ))]"
        stack=("${stack[@]}")
        ;;
      *)
        stack+=("$segment")
        ;;
    esac
  done

  set -- "${stack[@]}"
  if [ "$#" -eq 0 ]; then
    die "--files entries must point to files within the configured source tree: $value"
  fi

  normalized="${stack[0]}"
  for segment in "${stack[@]:1}"; do
    normalized+="/$segment"
  done

  printf '%s\n' "$normalized"
}

capability_selected_files_requested() {
  [ -n "$CAPABILITY_SELECTED_FILES_INPUT" ]
}

load_capability_selected_files() {
  local array_name="$1"
  local item=""
  local trimmed=""
  local -a raw_items=()
  local -n out_ref="$array_name"

  out_ref=()
  if ! capability_selected_files_requested; then
    return 0
  fi

  IFS=',' read -r -a raw_items <<<"$CAPABILITY_SELECTED_FILES_INPUT"
  for item in "${raw_items[@]}"; do
    trimmed="$(trim_capability_csv_item "$item")"
    if [ -z "$trimmed" ]; then
      die "--files must not contain empty entries"
    fi
    out_ref+=("$(normalize_capability_selected_file "$trimmed")")
  done
}

reject_capability_selected_files() {
  local capability_id="$1"

  if capability_selected_files_requested; then
    die "capability $capability_id does not support --files"
  fi
}

write_capability_summary() {
  local summary_path="$1"
  local status="$2"
  local capability_id="$3"
  local capability_label="$4"
  local adapter="$5"
  local driver="$6"
  local profile_path="$7"
  local run_root="$8"
  local exit_code="$9"
  local started_at="${10}"
  local finished_at="${11}"
  local stdout_log="${12}"
  local stderr_log="${13}"
  local dry_run="${14}"
  local command_source="${15}"
  local executor="${16}"
  local context_json="${17}"

  require_command jq

  jq -n \
    --arg status "$status" \
    --arg capability_id "$capability_id" \
    --arg capability_label "$capability_label" \
    --arg adapter "$adapter" \
    --arg driver "$driver" \
    --arg profile_path "$profile_path" \
    --arg run_root "$run_root" \
    --arg summary_json "$summary_path" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --arg command_source "$command_source" \
    --arg executor "$executor" \
    --argjson exit_code "$exit_code" \
    --argjson dry_run "$dry_run" \
    --argjson context "$context_json" \
    '{
      status: $status,
      capability: {
        id: $capability_id,
        label: $capability_label
      },
      adapter: $adapter,
      driver: (if $driver == "" then null else $driver end),
      profile_path: (if $profile_path == "" then null else $profile_path end),
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      execution: {
        source: $command_source,
        executor: $executor
      },
      artifacts: {
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    } + $context' >"$summary_path"
}

resolve_adapter_wrapper() {
  local adapter="$1"
  local root="$2"
  local array_name="$3"
  local -n out_ref="$array_name"

  out_ref=()

  case "$adapter" in
    direct-platform)
      out_ref=("$root/scripts/adapters/direct-platform.sh")
      ;;
    remote-windows)
      out_ref=("$root/scripts/adapters/remote-windows.sh")
      ;;
    vrunner)
      die "adapter vrunner requires capability-specific command arrays under schemaVersion 2"
      ;;
    *)
      die "unsupported RUNNER_ADAPTER: $adapter"
      ;;
  esac
}

execute_prepared_capability_command() {
  local root="$1"
  local adapter="$2"
  local stdout_log="$3"
  local stderr_log="$4"
  local -a adapter_env=()
  local -a wrapped_command=()
  local exit_code=0

  if [ "${CAPABILITY_COMMAND[*]-}" = "" ] && [ "$CAPABILITY_COMMAND_EXECUTOR" != "builtin-unsupported" ]; then
    die "capability command was not prepared"
  fi

  set +e
  case "$CAPABILITY_COMMAND_EXECUTOR" in
    direct)
      "${CAPABILITY_COMMAND[@]}" >"$stdout_log" 2>"$stderr_log"
      exit_code=$?
      ;;
    adapter-wrapper)
      resolve_adapter_wrapper "$adapter" "$root" wrapped_command
      wrapped_command+=("${CAPABILITY_COMMAND[@]}")
      prepare_adapter_wrapper_env "$adapter" adapter_env
      set -- "${adapter_env[@]}"
      if [ "$#" -gt 0 ]; then
        env "${adapter_env[@]}" "${wrapped_command[@]}" >"$stdout_log" 2>"$stderr_log"
      else
        "${wrapped_command[@]}" >"$stdout_log" 2>"$stderr_log"
      fi
      exit_code=$?
      ;;
    builtin-unsupported)
      printf 'unsupported contour: %s\n' \
        "${CAPABILITY_COMMAND[0]:-runtime profile marks this capability as unsupported}" \
        >"$stderr_log"
      exit_code=64
      ;;
    *)
      set -e
      die "unsupported capability command executor: $CAPABILITY_COMMAND_EXECUTOR"
      ;;
  esac
  set -e

  return "$exit_code"
}

run_profile_capability() {
  local capability_id="$1"
  local capability_label="$2"
  local builder_fn="$3"
  shift 3

  local root=""
  local profile_path=""
  local adapter=""
  local run_root=""
  local summary_path=""
  local stdout_log=""
  local stderr_log=""
  local started_at=""
  local finished_at=""
  local exit_code=0
  local status="success"

  parse_capability_cli_args "$@"
  reset_prepared_capability_command

  if [ "$CAPABILITY_SHOW_HELP" = "1" ]; then
    return 2
  fi

  root="$(project_root)"
  profile_path="$(resolve_runtime_profile_path "$CAPABILITY_PROFILE_INPUT" "$root")"
  load_runtime_profile "$profile_path"
  require_runtime_profile_loaded

  adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
  "$builder_fn" "$capability_id" "$adapter"

  run_root="$(prepare_capability_run_root "$capability_id" "$CAPABILITY_RUN_ROOT_INPUT")"
  summary_path="$(capability_summary_path "$run_root")"
  stdout_log="$run_root/stdout.log"
  stderr_log="$run_root/stderr.log"
  : >"$stdout_log"
  : >"$stderr_log"

  log "$capability_label"
  log "adapter=$adapter"
  if [ -n "$CAPABILITY_DRIVER" ]; then
    log "driver=$CAPABILITY_DRIVER"
  fi
  log "command_source=$CAPABILITY_COMMAND_SOURCE"
  log "executor=$CAPABILITY_COMMAND_EXECUTOR"
  if [ -n "$profile_path" ]; then
    log "profile=$profile_path"
  fi
  log "run_root=$run_root"

  started_at="$(timestamp_utc)"

  if [ "$CAPABILITY_DRY_RUN" = "1" ]; then
    status="dry-run"
  else
    if execute_prepared_capability_command "$root" "$adapter" "$stdout_log" "$stderr_log"; then
      exit_code=0
    else
      exit_code=$?
      status="failed"
    fi
  fi

  finished_at="$(timestamp_utc)"
  write_capability_summary \
    "$summary_path" \
    "$status" \
    "$capability_id" \
    "$capability_label" \
    "$adapter" \
    "$CAPABILITY_DRIVER" \
    "$profile_path" \
    "$run_root" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$stdout_log" \
    "$stderr_log" \
    "$CAPABILITY_DRY_RUN" \
    "$CAPABILITY_COMMAND_SOURCE" \
    "$CAPABILITY_COMMAND_EXECUTOR" \
    "$CAPABILITY_CONTEXT_JSON"

  log "summary_json=$summary_path"

  if [ "$status" = "failed" ]; then
    exit "$exit_code"
  fi
}
