#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

ACTION=""
INPUT_PATH=""
OUTPUT_PATH=""
RUN_ROOT_INPUT=""
TOOL_INPUT="${V8UNPACK:-v8unpack}"
DRY_RUN=0
EXTRA_ARGS=()

RUN_ROOT=""
STDOUT_LOG=""
STDERR_LOG=""
COMMAND_TXT=""

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/v8unpack.sh <extract|build|index> [options]

Options:
  --input <path>        Input file for extract, source dir for build/index
  --output <path>       Output source dir for extract, output file for build
  --run-root <dir>      Directory for summary and command artifacts
  --tool <path>         v8unpack executable (defaults to V8UNPACK or v8unpack)
  --extra-arg <arg>     Extra argument passed to v8unpack; repeatable
  --dry-run             Resolve command and write summary only
  -h, --help            Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

parse_args() {
  [ "$#" -gt 0 ] || fail "action is required: extract, build, or index"
  ACTION="$1"
  shift

  case "$ACTION" in
    extract|build|index) ;;
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
      --input)
        [ "$#" -ge 2 ] || fail "--input requires a value"
        INPUT_PATH="$2"
        shift 2
        ;;
      --output)
        [ "$#" -ge 2 ] || fail "--output requires a value"
        OUTPUT_PATH="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || fail "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --tool)
        [ "$#" -ge 2 ] || fail "--tool requires a value"
        TOOL_INPUT="$2"
        shift 2
        ;;
      --extra-arg)
        [ "$#" -ge 2 ] || fail "--extra-arg requires a value"
        EXTRA_ARGS+=("$2")
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

  [ -n "$INPUT_PATH" ] || fail "--input is required"
  if [ "$ACTION" != "index" ]; then
    [ -n "$OUTPUT_PATH" ] || fail "--output is required for $ACTION"
  fi
}

resolve_run_root() {
  local resolved=""

  if [ -n "$RUN_ROOT_INPUT" ]; then
    resolved="$(canonical_path "$RUN_ROOT_INPUT")"
    mkdir -p "$resolved"
    printf '%s\n' "$resolved"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/1c-v8unpack.XXXXXX"
}

write_command_file() {
  local command_path="$1"
  local arg=""

  : >"$command_path"
  shift
  for arg in "$@"; do
    printf '%q ' "$arg" >>"$command_path"
  done
  printf '\n' >>"$command_path"
}

build_command() {
  local array_name="$1"
  local -n out_ref="$array_name"

  out_ref=("$TOOL_INPUT")
  case "$ACTION" in
    extract)
      out_ref+=("-E" "$INPUT_PATH" "$OUTPUT_PATH")
      ;;
    build)
      out_ref+=("-B" "$INPUT_PATH" "$OUTPUT_PATH")
      ;;
    index)
      out_ref+=("-I" "$INPUT_PATH")
      ;;
  esac
  out_ref+=("${EXTRA_ARGS[@]}")
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local started_at="$3"
  local finished_at="$4"

  jq -n \
    --arg status "$status" \
    --arg action "$ACTION" \
    --arg input_path "$INPUT_PATH" \
    --arg output_path "$OUTPUT_PATH" \
    --arg run_root "$RUN_ROOT" \
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
        id: "v8unpack",
        label: "Run v8unpack"
      },
      action: $action,
      input_path: $input_path,
      output_path: (if $output_path == "" then null else $output_path end),
      run_root: $run_root,
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
if ! command -v "$TOOL_INPUT" >/dev/null 2>&1 && [ ! -x "$TOOL_INPUT" ]; then
  fail "v8unpack executable not found: $TOOL_INPUT"
fi

RUN_ROOT="$(resolve_run_root)"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"
COMMAND_TXT="$RUN_ROOT/command.txt"

mkdir -p "$RUN_ROOT"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

command=()
build_command command
write_command_file "$COMMAND_TXT" "${command[@]}"

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
