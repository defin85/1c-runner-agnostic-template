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

ACTION=""
PROFILE_INPUT=""
RUN_ROOT_INPUT=""
TARGET_INPUT=""
EXTENSION_NAME=""
DRY_RUN=0
CAPABILITY_DRY_RUN=0

PROFILE_PATH=""
RUN_ROOT=""
STDOUT_LOG=""
STDERR_LOG=""
COMMAND_TXT=""

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/manage-cfe.sh <list|delete> [options]

Options:
  --profile <file>     Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>     Directory for wrapper summary and command artifacts
  --target <id>        Target id from automation/context/target-matrix.json
  --extension <name>   Extension name for delete
  --dry-run            Resolve ibcmd command and write summary only
  -h, --help           Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

parse_args() {
  [ "$#" -gt 0 ] || fail "action is required: list or delete"
  ACTION="$1"
  shift

  case "$ACTION" in
    list|delete) ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unsupported action: $ACTION"
      ;;
  esac

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
        EXTENSION_NAME="$2"
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

  if [ "$ACTION" = "delete" ] && [ -z "$EXTENSION_NAME" ]; then
    fail "delete requires --extension <name>"
  fi
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

  mktemp -d "${TMPDIR:-/tmp}/1c-manage-cfe.XXXXXX"
}

redact_command_arg() {
  case "$1" in
    --password=*|--db-pwd=*)
      printf '%s\n' "${1%%=*}=__REDACTED_SECRET__"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

write_redacted_command_file() {
  local command_path="$1"
  local arg=""

  : >"$command_path"
  shift
  for arg in "$@"; do
    printf '%q ' "$(redact_command_arg "$arg")" >>"$command_path"
  done
  printf '\n' >>"$command_path"
}

build_command() {
  local array_name="$1"
  local binary_path=""
  local -n out_ref="$array_name"

  binary_path="$(ibcmd_binary_path)"
  out_ref=("$binary_path" "config")
  append_ibcmd_server_access_args out_ref
  append_ibcmd_target_args out_ref
  append_ibcmd_infobase_auth_args out_ref
  out_ref+=("extension" "$ACTION")
  if [ "$ACTION" = "delete" ]; then
    out_ref+=("--name=$EXTENSION_NAME")
  fi
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local started_at="$3"
  local finished_at="$4"

  jq -n \
    --arg status "$status" \
    --arg action "$ACTION" \
    --arg extension_name "$EXTENSION_NAME" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg target_id "$TARGET_INPUT" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg command_txt "$COMMAND_TXT" \
    --arg stdout_log "$STDOUT_LOG" \
    --arg stderr_log "$STDERR_LOG" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    '{
      status: $status,
      capability: {
        id: "manage-cfe",
        label: "Manage 1C extensions"
      },
      action: $action,
      extension_name: (if $extension_name == "" then null else $extension_name end),
      profile_path: $profile_path,
      run_root: $run_root,
      target_id: (if $target_id == "" then null else $target_id end),
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      artifacts: {
        command_txt: $command_txt,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$RUN_ROOT/summary.json"
}

parse_args "$@"

require_command jq
PROFILE_PATH="$(resolve_profile_path)"
RUN_ROOT="$(resolve_run_root)"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"
COMMAND_TXT="$RUN_ROOT/command.txt"

mkdir -p "$RUN_ROOT"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded
target_require_requested "$PROJECT_ROOT" "$TARGET_INPUT"
validate_ibcmd_capability_support "load-src" "${RUNTIME_PROFILE_RUNNER_ADAPTER:-}"

command=()
build_command command
write_redacted_command_file "$COMMAND_TXT" "${command[@]}"

started_at="$(timestamp_utc)"
status="success"
exit_code=0

if [ "$DRY_RUN" = "1" ]; then
  status="dry-run"
else
  set +e
  "${command[@]}" >"$STDOUT_LOG" 2>"$STDERR_LOG"
  exit_code=$?
  set -e
  if [ "$exit_code" -ne 0 ]; then
    status="failed"
  fi
fi

finished_at="$(timestamp_utc)"
write_summary "$status" "$exit_code" "$started_at" "$finished_at"

if [ "$status" = "failed" ]; then
  exit "$exit_code"
fi
