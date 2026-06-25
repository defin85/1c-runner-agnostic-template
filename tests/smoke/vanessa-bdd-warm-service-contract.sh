#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"
bindir="$tmpdir/bin"
ready_file="$tmpdir/xpra-ready-display"

mkdir -p "$fixture_root/scripts" "$fixture_root/env" "$fixture_root/automation/context" "$fixture_root/features" "$bindir"
cp -R "$SOURCE_ROOT/scripts/lib" "$fixture_root/scripts/lib"
cp -R "$SOURCE_ROOT/scripts/test" "$fixture_root/scripts/test"
cp -R "$SOURCE_ROOT/scripts/adapters" "$fixture_root/scripts/adapters"
cp -R "$SOURCE_ROOT/scripts/tools" "$fixture_root/scripts/tools"

cat >"$bindir/1cv8" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'fake-%s\n' "$(basename "$0")"
printf 'display=%s\n' "${DISPLAY:-}"
printf 'xauthority=%s\n' "${XAUTHORITY:-}"
sleep 300
EOF
cp "$bindir/1cv8" "$bindir/1cv8c"

cat >"$bindir/xpra" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'fake-xpra\n' >&2
for arg in "$@"; do
  printf 'xpra-arg=%s\n' "$arg" >&2
done
case "${1:-}" in
  start-desktop)
    printf '%s\n' "${2:-}" >"${ONEC_FAKE_XPRA_READY_FILE:?}"
    ;;
  stop)
    : >"${ONEC_FAKE_XPRA_READY_FILE:?}"
    ;;
esac
EOF

cat >"$bindir/xdpyinfo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
display="${DISPLAY:-}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    -display)
      display="${2:-}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
[ -f "${ONEC_FAKE_XPRA_READY_FILE:?}" ] || exit 1
[ "$(cat "$ONEC_FAKE_XPRA_READY_FILE")" = "$display" ]
EOF

cat >"$bindir/Xvfb" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat >"$bindir/openbox" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$bindir/"*

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "vanessa-bdd-warm-fixture",
  "runnerAdapter": "direct-platform",
  "target": {
    "id": "local-bdd"
  },
  "platform": {
    "binaryPath": "$bindir/1cv8",
    "xpra": {
      "enabled": true,
      "startChild": "openbox",
      "xvfbArgs": ["Xvfb", "-screen", "0", "1440x900x24", "-nolisten", "tcp", "-noreset", "-auth", "\$XAUTHORITY"]
    }
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
      "vanessaSinglePath": "$fixture_root/vanessa-automation-single.epf",
      "warmupFeaturePath": "$fixture_root/features/warmup.feature",
      "launchParameterName": "ProjectBddWarmServiceConfig"
    }
  }
}
EOF

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
printf 'fake epf\n' >"$fixture_root/vanessa-automation-single.epf"
printf '# language: ru\nФункционал: warmup\n' >"$fixture_root/features/warmup.feature"

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
  PATH="$bindir:$PATH" ONEC_FAKE_XPRA_READY_FILE="$ready_file" \
    ./scripts/test/run-bdd-warm-service.sh up --profile env/local.json --run-root "$run_root/up"
)
assert_jq "$run_root/up/summary.json" '.status == "success" and .service.state == "ready"' "up-ready"
state_path="$(jq -r '.service.state_json' "$run_root/up/summary.json")"
assert_jq "$state_path" '.roles.manager.pid != null and .roles.test_client.pid != null and .roles.test_client.port != null' "role-pids"
assert_contains "$(jq -r '.roles.manager.artifacts.stderr_log' "$state_path")" "xpra-arg=--session-name=BDD manager local-bdd"
assert_contains "$(jq -r '.roles.test_client.artifacts.stderr_log' "$state_path")" "xpra-arg=--session-name=BDD test-client local-bdd"
assert_contains "$(jq -r '.roles.manager.artifacts.command_txt' "$state_path")" "/TESTMANAGER"
assert_contains "$(jq -r '.roles.manager.artifacts.command_txt' "$state_path")" "ProjectBddWarmServiceConfig="
assert_contains "$(jq -r '.roles.manager.artifacts.command_txt' "$state_path")" "/out"
assert_contains "$(jq -r '.roles.test_client.artifacts.command_txt' "$state_path")" "/TestClient"
assert_contains "$(jq -r '.roles.test_client.artifacts.command_txt' "$state_path")" "-TPort"
assert_contains "$(jq -r '.roles.test_client.artifacts.command_txt' "$state_path")" "/out"

(
  cd "$fixture_root"
  PATH="$bindir:$PATH" ONEC_FAKE_XPRA_READY_FILE="$ready_file" \
    ./scripts/test/run-bdd-warm-service.sh status --profile env/local.json --run-root "$run_root/status"
)
assert_jq "$run_root/status/summary.json" '.service.state == "ready"' "status-ready"

(
  cd "$fixture_root"
  PATH="$bindir:$PATH" ONEC_FAKE_XPRA_READY_FILE="$ready_file" \
    ./scripts/test/run-bdd-warm-service.sh down --profile env/local.json --run-root "$run_root/down"
)
assert_jq "$run_root/down/summary.json" '.status == "success" and .service.state == "stopped"' "down-stopped"

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
