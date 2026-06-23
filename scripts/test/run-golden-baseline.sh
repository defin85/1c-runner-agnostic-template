#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

RUN_ROOT_INPUT="${ONEC_CAPABILITY_RUN_ROOT:-}"
COMMAND_INPUT="${GOLDEN_BASELINE_COMMAND:-}"

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-golden-baseline.sh [options]

Options:
  --run-root <dir>   Directory for summary.json and logs.
  --command <cmd>    Explicit golden check command. Defaults to tests/golden/run.sh.
  -h, --help         Show this help.
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --run-root)
        [ "$#" -ge 2 ] || fail "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --command)
        [ "$#" -ge 2 ] || fail "--command requires a value"
        COMMAND_INPUT="$2"
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

json_string() {
  jq -Rn --arg value "$1" '$value'
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local classification="$3"
  local command="$4"

  cat >"$RUN_ROOT/summary.json" <<EOF
{
  "contour": "golden-baseline",
  "status": $(json_string "$status"),
  "exitCode": $exit_code,
  "classification": $(json_string "$classification"),
  "command": $(json_string "$command"),
  "stdout": $(json_string "$RUN_ROOT/stdout.log"),
  "stderr": $(json_string "$RUN_ROOT/stderr.log")
}
EOF
}

parse_args "$@"
RUN_ROOT="${RUN_ROOT_INPUT:-$(mktemp -d "${TMPDIR:-/tmp}/1c-golden-baseline.XXXXXX")}"
mkdir -p "$RUN_ROOT"
: >"$RUN_ROOT/stdout.log"
: >"$RUN_ROOT/stderr.log"

if [ -z "$COMMAND_INPUT" ]; then
  if [ -x "$PROJECT_ROOT/tests/golden/run.sh" ]; then
    COMMAND_INPUT="./tests/golden/run.sh"
  else
    write_summary "failed" 2 "not configured" ""
    printf 'golden-baseline is mandatory: add executable tests/golden/run.sh or pass --command\n' >&2
    exit 2
  fi
fi

set +e
(
  cd "$PROJECT_ROOT"
  bash -lc "$COMMAND_INPUT"
) >"$RUN_ROOT/stdout.log" 2>"$RUN_ROOT/stderr.log"
exit_code=$?
set -e

if [ "$exit_code" -eq 0 ]; then
  write_summary "passed" 0 "passed" "$COMMAND_INPUT"
else
  write_summary "failed" "$exit_code" "failed" "$COMMAND_INPUT"
fi

exit "$exit_code"
