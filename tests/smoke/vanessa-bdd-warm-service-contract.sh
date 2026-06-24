#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"

mkdir -p \
  "$fixture_root/scripts" \
  "$fixture_root/env" \
  "$fixture_root/automation/context" \
  "$fixture_root/features/libraries" \
  "$fixture_root/features/steps" \
  "$fixture_root/src/cfe/ProjectBddExtension"
cp -R "$SOURCE_ROOT/scripts/lib" "$fixture_root/scripts/lib"
cp -R "$SOURCE_ROOT/scripts/test" "$fixture_root/scripts/test"
cp -R "$SOURCE_ROOT/scripts/tools" "$fixture_root/scripts/tools"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "vanessa-bdd-warm-fixture",
  "runnerAdapter": "direct-platform",
  "target": {
    "id": "local-bdd"
  },
  "platform": {
    "binaryPath": "/tmp/fake-1cv8"
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/ib",
    "auth": {
      "mode": "os"
    }
  },
  "capabilities": {
    "bddWarmService": {
      "vanessaSinglePath": "$fixture_root/tools/vanessa-automation-single.epf",
      "warmupFeaturePath": "$fixture_root/features/warmup.feature",
      "libraryPaths": ["$fixture_root/features/libraries"],
      "stepDefinitionPaths": ["$fixture_root/features/steps"],
      "extensionScope": ["ProjectBddExtension"]
    }
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

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

(
  cd "$fixture_root"
  unset ONEC_TEST_PORT_LEASE_HELPER
  export ONEC_TEST_PORT_LEASE_ROOT="$tmpdir/leases"
  export ONEC_TEST_PORT_LEASE_REPO="fixture-repo"
  source scripts/lib/common.sh
  source scripts/lib/onec-port-lease.sh
  helper_path="$(onec_port_lease_helper_path)"
  [ "$helper_path" = "$fixture_root/scripts/tools/onec-test-port-lease" ] || {
    printf 'unexpected helper path: %s\n' "$helper_path" >&2
    exit 1
  }
  lease_json="$(onec_port_lease_acquire bdd-warm testclient 48120-48122 1)"
  printf '%s\n' "$lease_json" | jq -e '.repo == "fixture-repo" and .role == "testclient"' >/dev/null
  onec_port_lease_release_by_id "$(printf '%s\n' "$lease_json" | onec_port_lease_id_from_json)"
)

set +e
(
  cd "$fixture_root"
  ./scripts/test/run-bdd-warm-service.sh up --profile env/local.json --run-root "$run_root/missing-target" 2>"$tmpdir/missing-target.err"
)
status=$?
set -e
[ "$status" -eq 2 ] || {
  printf 'bdd-warm-service missing target contract exit=%s\n' "$status" >&2
  exit 1
}
assert_jq "$run_root/missing-target/summary.json" '.status == "failed" and .classification == "not configured"' "missing-status"
assert_jq "$run_root/missing-target/summary.json" '.missing_inputs | index("automation/context/operator-local-targets.json") != null' "missing-target-contract"
assert_contains "$tmpdir/missing-target.err" "Vanessa BDD warm-service is not configured"

cat >"$fixture_root/automation/context/operator-local-targets.json" <<EOF
{
  "schemaVersion": 1,
  "operatorLocalTargets": {
    "vanessaBdd": {
      "targetId": "local-bdd",
      "infobase": {
        "mode": "file",
        "filePath": "$tmpdir/ib"
      }
    }
  }
}
EOF
mkdir -p "$fixture_root/tools"
printf 'fake epf\n' >"$fixture_root/tools/vanessa-automation-single.epf"
printf '# language: ru\nФункционал: warmup\n' >"$fixture_root/features/warmup.feature"

set +e
(
  cd "$fixture_root"
  ./scripts/test/run-bdd-warm-service.sh status --profile env/local.json --run-root "$run_root/configured" 2>"$tmpdir/configured.err"
)
status=$?
set -e
[ "$status" -eq 2 ] || {
  printf 'bdd-warm-service configured skeleton exit=%s\n' "$status" >&2
  exit 1
}
assert_jq "$run_root/configured/summary.json" '.classification == "not implemented" and (.missing_inputs | index("runtime implementation") != null)' "configured-skeleton"
assert_jq "$run_root/configured/summary.json" '.runtime_profile.target == "local-bdd"' "configured-target"

rendered_root="$tmpdir/rendered"
mkdir -p "$rendered_root"
(
  source "$SOURCE_ROOT/scripts/bootstrap/generated-project-surface.sh"
  seed_generated_project_surface_on_copy "$rendered_root" "Fixture" "fixture" "Fixture"
)
assert_jq "$rendered_root/automation/context/runtime-support-matrix.json" '([.contours[].id] | index("bdd-warm-service") != null) and (.contours[] | select(.id == "bdd-warm-service") | .status) == "operator-local"' "matrix-entry"
assert_jq "$rendered_root/automation/context/operator-local-targets.json" '.operatorLocalTargets.vanessaBdd.targetId == ""' "target-template"
assert_contains "$rendered_root/automation/context/runtime-support-matrix.md" "bdd-warm-service"

for forbidden in "De""lans" "DC""BddWarmServiceConfig" "De""lansCommon" "UT ""11" "УТ ""11"; do
  if grep -R -F -- "$forbidden" \
    "$SOURCE_ROOT/scripts/test/run-bdd-warm-service.sh" \
    "$SOURCE_ROOT/scripts/lib/vanessa-bdd.sh" \
    "$SOURCE_ROOT/automation/context/templates" \
    "$rendered_root" >/dev/null; then
    printf 'forbidden applied-project string leaked: %s\n' "$forbidden" >&2
    exit 1
  fi
done
