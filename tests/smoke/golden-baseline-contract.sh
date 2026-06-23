#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

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

run_root="$tmpdir/not-configured"
if "$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" 2>"$tmpdir/not-configured.err"; then
  printf 'golden-baseline must fail closed when no project runner is configured\n' >&2
  exit 1
fi
assert_jq "$run_root/summary.json" '.contour == "golden-baseline" and .status == "failed" and .exitCode == 2 and .classification == "not configured"' "not-configured"

run_root="$tmpdir/passed"
"$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" --command "printf ok" >/dev/null
assert_jq "$run_root/summary.json" '.status == "passed" and .exitCode == 0 and .command == "printf ok"' "passed"

run_root="$tmpdir/failed"
if "$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" --command "exit 7"; then
  printf 'golden-baseline must propagate project runner failure\n' >&2
  exit 1
fi
assert_jq "$run_root/summary.json" '.status == "failed" and .exitCode == 7 and .classification == "failed"' "failed"
