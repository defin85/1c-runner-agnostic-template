#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/profile.json"
run_root_success="$tmpdir/run-success"
run_root_failure="$tmpdir/run-failure"
run_root_load="$tmpdir/run-load"
run_root_update="$tmpdir/run-update"
run_root_xunit="$tmpdir/run-xunit"
run_root_unsupported="$tmpdir/run-unsupported"
fake_binary="$tmpdir/fake-1cv8"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done

printf 'fake-1cv8-stderr\n' >&2

for arg in "$@"; do
  if [ "$arg" = "/DumpConfigToFiles" ]; then
    printf 'dump failed\n' >&2
    exit 17
  fi
done
EOF

chmod +x "$fake_binary"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "client-server",
    "server": "127.0.0.1:1541",
    "ref": "fixture-ref",
    "auth": {
      "mode": "user-password",
      "user": "fixture-user",
      "passwordEnv": "ONEC_IB_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "outputDir": "./src/cf"
    },
    "loadSrc": {
      "sourceDir": "./src/cf"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

export ONEC_IB_PASSWORD="super-secret"

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
assert_jq "$run_root_success/summary.json" '.driver == "designer"' "success-driver"
assert_jq "$run_root_success/summary.json" '.execution.source == "standard-builder"' "success-execution-source"
assert_jq "$run_root_success/summary.json" '.infobase.mode == "client-server"' "success-ib-mode"
assert_jq "$run_root_success/summary.json" '.infobase.auth_mode == "user-password"' "success-auth-mode"
if ! jq -e --arg profile "$profile_path" '.profile_path == $profile' "$run_root_success/summary.json" >/dev/null; then
  printf 'jq assertion failed (success-profile)\n' >&2
  cat "$run_root_success/summary.json" >&2
  exit 1
fi
assert_contains "$run_root_success/stdout.log" "CREATEINFOBASE"
assert_contains "$run_root_success/stdout.log" "fixture-ref"
assert_contains "$run_root_success/stderr.log" "fake-1cv8-stderr"
if grep -Fq -- "super-secret" "$run_root_success/summary.json"; then
  printf 'summary.json must not contain resolved secrets\n' >&2
  cat "$run_root_success/summary.json" >&2
  exit 1
fi

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
assert_jq "$run_root_failure/summary.json" '.driver == "designer"' "failure-driver"
assert_jq "$run_root_failure/summary.json" '.execution.source == "standard-builder"' "failure-execution-source"
assert_contains "$run_root_failure/stderr.log" "dump failed"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/load-src.sh --profile "$profile_path" --run-root "$run_root_load" >/dev/null
)

assert_jq "$run_root_load/summary.json" '.status == "success"' "load-status"
assert_jq "$run_root_load/summary.json" '.driver == "designer"' "load-driver"
assert_jq "$run_root_load/summary.json" '.execution.source == "standard-builder"' "load-execution-source"
assert_contains "$run_root_load/stdout.log" "/LoadConfigFromFiles"
assert_contains "$run_root_load/stdout.log" "./src/cf"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/update-db.sh --profile "$profile_path" --run-root "$run_root_update" >/dev/null
)

assert_jq "$run_root_update/summary.json" '.status == "success"' "update-status"
assert_jq "$run_root_update/summary.json" '.driver == "designer"' "update-driver"
assert_jq "$run_root_update/summary.json" '.execution.source == "standard-builder"' "update-execution-source"
assert_contains "$run_root_update/stdout.log" "/UpdateDBCfg"

(
  cd "$SOURCE_ROOT"
  ./scripts/test/run-xunit.sh --profile "$profile_path" --run-root "$run_root_xunit" >/dev/null
)

assert_jq "$run_root_xunit/summary.json" '.status == "success"' "xunit-status"
assert_jq "$run_root_xunit/summary.json" '.execution.source == "profile-command"' "xunit-execution-source"
assert_contains "$run_root_xunit/stdout.log" "xunit-ok"

unsupported_profile_path="$tmpdir/unsupported-profile.json"
cat >"$unsupported_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "unsupported-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/unsupported-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "xunit": {
      "unsupportedReason": "xUnit contour is not wired yet."
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/test/run-xunit.sh --profile "$unsupported_profile_path" --run-root "$run_root_unsupported" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 64 ]; then
  printf 'unexpected exit code for unsupported xunit contour: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$run_root_unsupported/summary.json" '.status == "failed"' "unsupported-status"
assert_jq "$run_root_unsupported/summary.json" '.exit_code == 64' "unsupported-exit-code"
assert_jq "$run_root_unsupported/summary.json" '.execution.source == "unsupported-profile"' "unsupported-source"
assert_jq "$run_root_unsupported/summary.json" '.unsupported.placeholder == true' "unsupported-placeholder"
assert_jq "$run_root_unsupported/summary.json" '.unsupported.reason == "xUnit contour is not wired yet."' "unsupported-reason"
assert_contains "$run_root_unsupported/stderr.log" "unsupported contour: xUnit contour is not wired yet."
