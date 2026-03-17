#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/doctor-profile.json"
run_root="$tmpdir/doctor-run"

cat >"$profile_path" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "doctor-fixture",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "echo create",
    "DUMP_SRC_CMD": "echo dump",
    "LOAD_SRC_CMD": "echo load",
    "UPDATE_DB_CMD": "echo update",
    "DIFF_SRC_CMD": "echo diff",
    "XUNIT_RUN_CMD": "echo xunit",
    "BDD_RUN_CMD": "echo bdd",
    "SMOKE_RUN_CMD": "echo smoke"
  }
}
EOF

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
  ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$run_root" >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success"' "doctor-status"
assert_jq "$run_root/summary.json" '.capability.id == "doctor"' "doctor-capability"
assert_jq "$run_root/summary.json" '.adapter == "direct-platform"' "doctor-adapter"
assert_jq "$run_root/summary.json" '[.checks.required_env[] | select(.status != "set")] | length == 0' "doctor-required-env"
assert_jq "$run_root/summary.json" '[.checks.required_tools[] | select(.status != "present")] | length == 0' "doctor-required-tools"
