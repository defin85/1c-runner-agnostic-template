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

reset_capability_cli_state() {
  CAPABILITY_PROFILE_INPUT=""
  CAPABILITY_RUN_ROOT_INPUT=""
  CAPABILITY_DRY_RUN="${DRY_RUN:-0}"
  CAPABILITY_SHOW_HELP=0
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

write_capability_summary() {
  local summary_path="$1"
  local status="$2"
  local capability_id="$3"
  local capability_label="$4"
  local adapter="$5"
  local profile_path="$6"
  local command_var="$7"
  local run_root="$8"
  local exit_code="$9"
  local started_at="${10}"
  local finished_at="${11}"
  local stdout_log="${12}"
  local stderr_log="${13}"
  local dry_run="${14}"

  require_command jq

  jq -n \
    --arg status "$status" \
    --arg capability_id "$capability_id" \
    --arg capability_label "$capability_label" \
    --arg adapter "$adapter" \
    --arg profile_path "$profile_path" \
    --arg command_var "$command_var" \
    --arg run_root "$run_root" \
    --arg summary_json "$summary_path" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --argjson exit_code "$exit_code" \
    --argjson dry_run "$dry_run" \
    '{
      status: $status,
      capability: {
        id: $capability_id,
        label: $capability_label
      },
      adapter: $adapter,
      profile_path: (if $profile_path == "" then null else $profile_path end),
      command_var: $command_var,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      artifacts: {
        summary_json: $summary_json,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$summary_path"
}

resolve_adapter_command_var() {
  local adapter="$1"
  local direct_var="$2"
  local windows_var="$3"
  local vrunner_var="$4"

  case "$adapter" in
    direct-platform)
      printf '%s\n' "$direct_var"
      ;;
    remote-windows)
      printf '%s\n' "$windows_var"
      ;;
    vrunner)
      printf '%s\n' "$vrunner_var"
      ;;
    *)
      die "unsupported RUNNER_ADAPTER: $adapter"
      ;;
  esac
}

run_adapter_capability() {
  local capability_id="$1"
  local capability_label="$2"
  local direct_var="$3"
  local windows_var="$4"
  local vrunner_var="$5"
  shift 5

  local root=""
  local profile_path=""
  local adapter=""
  local command_var=""
  local command_string=""
  local run_root=""
  local summary_path=""
  local stdout_log=""
  local stderr_log=""
  local started_at=""
  local finished_at=""
  local exit_code=0
  local status="success"

  parse_capability_cli_args "$@"

  if [ "$CAPABILITY_SHOW_HELP" = "1" ]; then
    return 2
  fi

  root="$(project_root)"
  profile_path="$(resolve_runtime_profile_path "$CAPABILITY_PROFILE_INPUT" "$root")"
  load_runtime_profile "$profile_path"

  adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
  command_var="$(resolve_adapter_command_var "$adapter" "$direct_var" "$windows_var" "$vrunner_var")"
  require_env "$command_var"
  command_string="${!command_var}"

  run_root="$(prepare_capability_run_root "$capability_id" "$CAPABILITY_RUN_ROOT_INPUT")"
  summary_path="$(capability_summary_path "$run_root")"
  stdout_log="$run_root/stdout.log"
  stderr_log="$run_root/stderr.log"
  : >"$stdout_log"
  : >"$stderr_log"

  log "$capability_label"
  log "adapter=$adapter"
  log "command_var=$command_var"
  if [ -n "$profile_path" ]; then
    log "profile=$profile_path"
  fi
  log "run_root=$run_root"

  started_at="$(timestamp_utc)"

  if [ "$CAPABILITY_DRY_RUN" = "1" ]; then
    status="dry-run"
  else
    set +e
    bash -lc "$command_string" >"$stdout_log" 2>"$stderr_log"
    exit_code=$?
    set -e

    if [ "$exit_code" -ne 0 ]; then
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
    "$command_var" \
    "$run_root" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$stdout_log" \
    "$stderr_log" \
    "$CAPABILITY_DRY_RUN"

  log "summary_json=$summary_path"

  if [ "$status" = "failed" ]; then
    exit "$exit_code"
  fi
}
