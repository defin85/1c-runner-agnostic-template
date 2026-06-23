#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

PROFILE_INPUT=""
RUN_ROOT_INPUT=""
DRY_RUN=0
EXPLICIT_EXTENSIONS=()

PROFILE_PATH=""
RUN_ROOT=""
STDOUT_LOG=""
STDERR_LOG=""
SELECTED_EXTENSIONS=()
FAILED_EXTENSION=""

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/configure-cfe-runtime-flags.sh [options]

Options:
  --profile <file>       Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>       Directory for wrapper summary and per-extension artifacts
  --extension <name>     Extension name to configure; repeatable. Defaults to all extension directories present in src/cfe.
  --dry-run              Resolve ibcmd commands and write dry-run summaries only
  -h, --help             Show this help
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

  mktemp -d "${TMPDIR:-/tmp}/1c-configure-cfe-runtime-flags.XXXXXX"
}

collect_extension_names() {
  local path=""

  SELECTED_EXTENSIONS=()
  if [ "${#EXPLICIT_EXTENSIONS[@]}" -gt 0 ]; then
    SELECTED_EXTENSIONS=("${EXPLICIT_EXTENSIONS[@]}")
    return 0
  fi

  while IFS= read -r path; do
    [ -n "$path" ] || continue
    SELECTED_EXTENSIONS+=("$(basename -- "$path")")
  done < <(find "$PROJECT_ROOT/src/cfe" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
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

build_update_command() {
  local extension_name="$1"
  local array_name="$2"
  local binary_path=""
  local -n out_ref="$array_name"

  binary_path="$(ibcmd_binary_path)"
  out_ref=("$binary_path" "infobase" "config" "extension" "update")
  append_ibcmd_server_access_args out_ref
  append_ibcmd_target_args out_ref
  append_ibcmd_infobase_auth_args out_ref
  out_ref+=(
    "--name=$extension_name"
    "--safe-mode=no"
    "--unsafe-action-protection=no"
  )
}

write_extension_summary() {
  local summary_path="$1"
  local extension_name="$2"
  local status="$3"
  local exit_code="$4"
  local started_at="$5"
  local finished_at="$6"
  local stdout_log="$7"
  local stderr_log="$8"
  local command_txt="$9"

  jq -n \
    --arg extension_name "$extension_name" \
    --arg status "$status" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --arg command_txt "$command_txt" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    '{
      extension_name: $extension_name,
      status: $status,
      exit_code: $exit_code,
      dry_run: $dry_run,
      requested_flags: {
        safe_mode: "no",
        unsafe_action_protection: "no"
      },
      started_at: $started_at,
      finished_at: $finished_at,
      artifacts: {
        command_txt: $command_txt,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      }
    }' >"$summary_path"
}

run_extension_update() {
  local extension_name="$1"
  local extension_run_root="$RUN_ROOT/extensions/$extension_name"
  local summary_path="$extension_run_root/summary.json"
  local command_path="$extension_run_root/update.command.txt"
  local stdout_log="$extension_run_root/update.stdout.log"
  local stderr_log="$extension_run_root/update.stderr.log"
  local started_at=""
  local finished_at=""
  local status="success"
  local exit_code=0
  local -a command=()

  mkdir -p "$extension_run_root"
  : >"$stdout_log"
  : >"$stderr_log"

  build_update_command "$extension_name" command
  write_redacted_command_file "$command_path" "${command[@]}"

  started_at="$(timestamp_utc)"
  append_log_line "$STDOUT_LOG" "[configure-cfe-runtime-flags] extension=$extension_name started"
  if [ "$DRY_RUN" = "1" ]; then
    status="dry-run"
  else
    set +e
    "${command[@]}" >"$stdout_log" 2>"$stderr_log"
    exit_code=$?
    set -e
    if [ "$exit_code" -ne 0 ]; then
      status="failed"
      FAILED_EXTENSION="$extension_name"
    fi
  fi
  finished_at="$(timestamp_utc)"

  write_extension_summary \
    "$summary_path" \
    "$extension_name" \
    "$status" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$stdout_log" \
    "$stderr_log" \
    "$command_path"

  append_log_line "$STDOUT_LOG" "[configure-cfe-runtime-flags] extension=$extension_name status=$status exit_code=$exit_code"
  if [ "$status" = "failed" ]; then
    append_log_line "$STDERR_LOG" "[configure-cfe-runtime-flags] extension=$extension_name failed"
  fi

  return "$exit_code"
}

extension_status() {
  local extension_name="$1"
  local summary_path="$RUN_ROOT/extensions/$extension_name/summary.json"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r '.status // empty' "$summary_path"
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local started_at="$3"
  local finished_at="$4"
  local extension_names_json=""
  local results_json="[]"
  local extension_name=""
  local extension_summary=""

  extension_names_json="$(json_array_from_lines "${SELECTED_EXTENSIONS[@]}")"
  for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
    extension_summary="$RUN_ROOT/extensions/$extension_name/summary.json"
    results_json="$(jq -cn \
      --argjson existing "$results_json" \
      --arg extension_name "$extension_name" \
      --arg summary_json "$extension_summary" \
      --arg status "$(extension_status "$extension_name")" \
      '$existing + [{
        extension_name: $extension_name,
        summary_json: $summary_json,
        status: (if $status == "" then null else $status end)
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
    --arg failed_extension "$FAILED_EXTENSION" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson extension_names "$extension_names_json" \
    --argjson results "$results_json" \
    '{
      status: $status,
      capability: {
        id: "configure-cfe-runtime-flags",
        label: "Configure CFE runtime flags"
      },
      profile_path: $profile_path,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      requested_flags: {
        safe_mode: "no",
        unsafe_action_protection: "no"
      },
      extension_source: {
        selected_names: $extension_names
      },
      failed_extension: (if $failed_extension == "" then null else $failed_extension end),
      failure: (if $failed_extension == "" then null else {
        classification: "extension-runtime-flags failed",
        extension_name: $failed_extension
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
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded

RUN_ROOT="$(resolve_run_root)"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"

mkdir -p "$RUN_ROOT"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

collect_extension_names
[ "${#SELECTED_EXTENSIONS[@]}" -gt 0 ] || fail "no runtime extensions selected"

started_at="$(timestamp_utc)"
status="success"
exit_code=0

append_log_line "$STDOUT_LOG" "[configure-cfe-runtime-flags] profile=$PROFILE_PATH"
append_log_line "$STDOUT_LOG" "[configure-cfe-runtime-flags] extensions=${SELECTED_EXTENSIONS[*]}"

for extension_name in "${SELECTED_EXTENSIONS[@]}"; do
  if run_extension_update "$extension_name"; then
    continue
  else
    exit_code=$?
  fi

  status="failed"
  break
done

if [ "$DRY_RUN" = "1" ] && [ "$status" = "success" ]; then
  status="dry-run"
fi

finished_at="$(timestamp_utc)"
write_summary "$status" "$exit_code" "$started_at" "$finished_at"

if [ "$status" = "failed" ]; then
  exit "$exit_code"
fi
