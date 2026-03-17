#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/profile.json"
run_root_success="$tmpdir/run-success"
run_root_failure="$tmpdir/run-failure"

cat >"$profile_path" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "fixture",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "printf 'create-ok\\n'; printf 'create-stderr\\n' >&2",
    "DUMP_SRC_CMD": "printf 'dump failed\\n' >&2; exit 17",
    "LOAD_SRC_CMD": "printf 'load-ok\\n'",
    "UPDATE_DB_CMD": "printf 'update-ok\\n'",
    "DIFF_SRC_CMD": "printf 'diff-ok\\n'",
    "XUNIT_RUN_CMD": "printf 'xunit-ok\\n'",
    "BDD_RUN_CMD": "printf 'bdd-ok\\n'",
    "SMOKE_RUN_CMD": "printf 'smoke-ok\\n'"
  }
}
EOF

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"

  if ! jq -e "$expr" "$file" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$run_root_success" >/dev/null
)

assert_jq "$run_root_success/summary.json" '.status == "success"' "success-status"
assert_jq "$run_root_success/summary.json" '.capability.id == "create-ib"' "success-capability"
assert_jq "$run_root_success/summary.json" '.adapter == "direct-platform"' "success-adapter"
if ! jq -e --arg profile "$profile_path" '.profile_path == $profile' "$run_root_success/summary.json" >/dev/null; then
  printf 'jq assertion failed (success-profile)\n' >&2
  cat "$run_root_success/summary.json" >&2
  exit 1
fi
assert_jq "$run_root_success/summary.json" '.command_var == "CREATE_IB_CMD"' "success-command-var"
assert_contains "$run_root_success/stdout.log" "create-ok"
assert_contains "$run_root_success/stderr.log" "create-stderr"

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/platform/dump-src.sh --profile "$profile_path" --run-root "$run_root_failure" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 17 ]; then
  printf 'unexpected exit code for dump-src: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$run_root_failure/summary.json" '.status == "failed"' "failure-status"
assert_jq "$run_root_failure/summary.json" '.exit_code == 17' "failure-exit-code"
assert_jq "$run_root_failure/summary.json" '.command_var == "DUMP_SRC_CMD"' "failure-command-var"
assert_contains "$run_root_failure/stderr.log" "dump failed"
