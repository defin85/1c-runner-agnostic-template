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
CAPABILITY_COMMAND_SOURCE=""
CAPABILITY_COMMAND_EXECUTOR="direct"
CAPABILITY_CONTEXT_JSON="{}"
CAPABILITY_COMMAND=()

reset_capability_cli_state() {
  CAPABILITY_PROFILE_INPUT=""
  CAPABILITY_RUN_ROOT_INPUT=""
  CAPABILITY_DRY_RUN="${DRY_RUN:-0}"
  CAPABILITY_SHOW_HELP=0
}

reset_prepared_capability_command() {
  CAPABILITY_COMMAND_SOURCE=""
  CAPABILITY_COMMAND_EXECUTOR="direct"
  CAPABILITY_CONTEXT_JSON="{}"
  CAPABILITY_COMMAND=()
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
  local source="$1"
  local executor="$2"
  shift 2

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

write_capability_summary() {
  local summary_path="$1"
  local status="$2"
  local capability_id="$3"
  local capability_label="$4"
  local adapter="$5"
  local profile_path="$6"
  local run_root="$7"
  local exit_code="$8"
  local started_at="$9"
  local finished_at="${10}"
  local stdout_log="${11}"
  local stderr_log="${12}"
  local dry_run="${13}"
  local command_source="${14}"
  local executor="${15}"
  local context_json="${16}"

  require_command jq

  jq -n \
    --arg status "$status" \
    --arg capability_id "$capability_id" \
    --arg capability_label "$capability_label" \
    --arg adapter "$adapter" \
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
  local -a wrapped_command=()
  local exit_code=0

  if [ "${CAPABILITY_COMMAND[*]-}" = "" ]; then
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
      "${wrapped_command[@]}" >"$stdout_log" 2>"$stderr_log"
      exit_code=$?
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
