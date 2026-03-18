#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bindir="$tmpdir/bin"
path_success="$tmpdir/path-success"
path_missing_xauth="$tmpdir/path-missing-xauth"
path_missing_xvfb="$tmpdir/path-missing-xvfb"
profile_path="$tmpdir/profile.json"
profile_disabled_path="$tmpdir/profile-disabled.json"
doctor_run_root="$tmpdir/doctor-run"
create_run_root="$tmpdir/create-run"
xunit_run_root="$tmpdir/xunit-run"
default_run_root="$tmpdir/default-run"
runtime_missing_xauth_run_root="$tmpdir/runtime-missing-xauth-run"
runtime_missing_xvfb_run_root="$tmpdir/runtime-missing-xvfb-run"
doctor_missing_xauth_run_root="$tmpdir/doctor-missing-xauth-run"
doctor_missing_xvfb_run_root="$tmpdir/doctor-missing-xvfb-run"
invocation_log="$tmpdir/invocations.log"
fake_binary="$bindir/1cv8"
fake_client="$bindir/1cv8c"
fake_xvfb_run="$bindir/xvfb-run"
fake_xauth="$bindir/xauth"

mkdir -p "$bindir"
: >"$invocation_log"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ -n "${ONEC_INVOCATION_LOG:-}" ]; then
  printf '%s\n' "$(basename "$0")" >>"$ONEC_INVOCATION_LOG"
fi

printf 'fake-%s\n' "$(basename "$0")"
for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cp "$fake_binary" "$fake_client"

cat >"$fake_xvfb_run" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'fake-xvfb-run\n'
for arg in "$@"; do
  printf 'wrapper-arg=%s\n' "$arg"
done

while [ "$#" -gt 0 ]; do
  case "$1" in
    -a|--auto-servernum)
      shift
      ;;
    --error-file=*|--server-args=*)
      shift
      ;;
    --error-file|--server-args)
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      shift
      ;;
    *)
      break
      ;;
  esac
done

"$@"
EOF

cat >"$fake_xauth" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$fake_binary" "$fake_client" "$fake_xvfb_run" "$fake_xauth"

mirror_commands() {
  local target_dir="$1"
  local command_name=""

  mkdir -p "$target_dir"
  for command_name in bash basename cat date dirname env git jq mkdir mktemp realpath rg tee; do
    ln -sf "$(command -v "$command_name")" "$target_dir/$command_name"
  done
}

mirror_commands "$path_success"
mirror_commands "$path_missing_xauth"
mirror_commands "$path_missing_xvfb"
ln -sf "$fake_xvfb_run" "$path_success/xvfb-run"
ln -sf "$fake_xauth" "$path_success/xauth"
ln -sf "$fake_xvfb_run" "$path_missing_xauth/xvfb-run"
ln -sf "$fake_xauth" "$path_missing_xvfb/xauth"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "xvfb-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary",
    "xvfb": {
      "enabled": true,
      "serverArgs": ["-screen", "0", "1440x900x24", "-noreset"]
    }
  },
  "infobase": {
    "mode": "file",
    "filePath": "/tmp/xvfb-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "xunit": {
      "command": ["$fake_client", "ENTERPRISE", "/F", "/tmp/xvfb-fixture"]
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

jq 'del(.platform.xvfb)' "$profile_path" >"$profile_disabled_path"

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

assert_not_contains() {
  local file="$1"
  local unexpected="$2"

  if grep -Fq -- "$unexpected" "$file"; then
    printf 'unexpected text found: %s\n' "$unexpected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"
  shift 3

  if ! jq -e "$expr" "$file" "$@" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

(
  cd "$SOURCE_ROOT"
  PATH="$path_success" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_run_root" >/dev/null
)

assert_jq "$doctor_run_root/summary.json" '.status == "success"' "doctor-status"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.wrapper == "xvfb-run"' "doctor-wrapper"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.xvfb.enabled == true' "doctor-xvfb-enabled"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.xvfb.server_args == ["-screen","0","1440x900x24","-noreset"]' "doctor-server-args"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xvfb-run" and .status == "present")] | length == 1' "doctor-required-xvfb-run"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xauth" and .status == "present")] | length == 1' "doctor-required-xauth"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .status == "present")] | length == 1' "doctor-xunit-capability"

(
  cd "$SOURCE_ROOT"
  PATH="$path_success" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$create_run_root" >/dev/null
)

assert_jq "$create_run_root/summary.json" '.status == "success"' "create-status"
assert_jq "$create_run_root/summary.json" '.execution.executor == "adapter-wrapper"' "create-executor"
assert_jq "$create_run_root/summary.json" '.adapter_context.wrapper == "xvfb-run"' "create-wrapper"
assert_jq "$create_run_root/summary.json" '.adapter_context.xvfb.server_args == ["-screen","0","1440x900x24","-noreset"]' "create-server-args"
assert_contains "$create_run_root/stdout.log" "fake-xvfb-run"
assert_contains "$create_run_root/stdout.log" "wrapper-arg=--error-file=/dev/stderr"
assert_contains "$create_run_root/stdout.log" "wrapper-arg=--server-args=-screen 0 1440x900x24 -noreset"
assert_contains "$create_run_root/stdout.log" "fake-1cv8"
assert_contains "$invocation_log" "1cv8"

(
  cd "$SOURCE_ROOT"
  PATH="$path_success" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_path" --run-root "$xunit_run_root" >/dev/null
)

assert_jq "$xunit_run_root/summary.json" '.status == "success"' "xunit-status"
assert_jq "$xunit_run_root/summary.json" '.execution.source == "profile-command"' "xunit-source"
assert_jq "$xunit_run_root/summary.json" '.execution.executor == "adapter-wrapper"' "xunit-executor"
assert_jq "$xunit_run_root/summary.json" '.adapter_context.wrapper == "xvfb-run"' "xunit-wrapper"
assert_contains "$xunit_run_root/stdout.log" "fake-xvfb-run"
assert_contains "$xunit_run_root/stdout.log" "fake-1cv8c"
assert_contains "$invocation_log" "1cv8c"

(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xvfb" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_disabled_path" --run-root "$default_run_root" >/dev/null
)

assert_jq "$default_run_root/summary.json" '.status == "success"' "default-status"
assert_jq "$default_run_root/summary.json" 'has("adapter_context") | not' "default-no-adapter-context"
assert_not_contains "$default_run_root/stdout.log" "fake-xvfb-run"
assert_contains "$default_run_root/stdout.log" "fake-1cv8c"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xauth" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$runtime_missing_xauth_run_root" >/dev/null
)
status_missing_xauth=$?
set -e

if [ "$status_missing_xauth" -eq 0 ]; then
  printf 'expected create-ib to fail when xauth is missing\n' >&2
  exit 1
fi

assert_jq "$runtime_missing_xauth_run_root/summary.json" '.status == "failed"' "runtime-missing-xauth-status"
assert_contains "$runtime_missing_xauth_run_root/stderr.log" "command not found: xauth"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xvfb" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_path" --run-root "$runtime_missing_xvfb_run_root" >/dev/null
)
status_missing_xvfb=$?
set -e

if [ "$status_missing_xvfb" -eq 0 ]; then
  printf 'expected run-xunit to fail when xvfb-run is missing\n' >&2
  exit 1
fi

assert_jq "$runtime_missing_xvfb_run_root/summary.json" '.status == "failed"' "runtime-missing-xvfb-status"
assert_contains "$runtime_missing_xvfb_run_root/stderr.log" "command not found: xvfb-run"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xauth" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_missing_xauth_run_root" >/dev/null
)
status_doctor_missing_xauth=$?
set -e

if [ "$status_doctor_missing_xauth" -eq 0 ]; then
  printf 'expected doctor to fail when xauth is missing\n' >&2
  exit 1
fi

assert_jq "$doctor_missing_xauth_run_root/summary.json" '.status == "failed"' "doctor-missing-xauth-status"
assert_jq "$doctor_missing_xauth_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xauth" and .status == "missing")] | length == 1' "doctor-missing-xauth-tool"
assert_jq "$doctor_missing_xauth_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "create-ib" and .reason == "missing xauth for direct-platform xvfb wrapper")] | length == 1' "doctor-missing-xauth-create"
assert_jq "$doctor_missing_xauth_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .reason == "missing xauth for direct-platform xvfb wrapper")] | length == 1' "doctor-missing-xauth-xunit"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xvfb" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_missing_xvfb_run_root" >/dev/null
)
status_doctor_missing_xvfb=$?
set -e

if [ "$status_doctor_missing_xvfb" -eq 0 ]; then
  printf 'expected doctor to fail when xvfb-run is missing\n' >&2
  exit 1
fi

assert_jq "$doctor_missing_xvfb_run_root/summary.json" '.status == "failed"' "doctor-missing-xvfb-status"
assert_jq "$doctor_missing_xvfb_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xvfb-run" and .status == "missing")] | length == 1' "doctor-missing-xvfb-tool"
assert_jq "$doctor_missing_xvfb_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "create-ib" and .reason == "missing xvfb-run for direct-platform xvfb wrapper")] | length == 1' "doctor-missing-xvfb-create"
assert_jq "$doctor_missing_xvfb_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .reason == "missing xvfb-run for direct-platform xvfb wrapper")] | length == 1' "doctor-missing-xvfb-xunit"
