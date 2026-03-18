#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bindir="$tmpdir/bin"
profile_path="$tmpdir/profile.json"
profile_disabled_path="$tmpdir/profile-disabled.json"
profile_missing_lib_path="$tmpdir/profile-missing-lib.json"
profile_relative_lib_path="$tmpdir/profile-relative-lib.json"
doctor_run_root="$tmpdir/doctor-run"
create_run_root="$tmpdir/create-run"
xunit_run_root="$tmpdir/xunit-run"
default_run_root="$tmpdir/default-run"
runtime_missing_lib_run_root="$tmpdir/runtime-missing-lib-run"
runtime_relative_lib_run_root="$tmpdir/runtime-relative-lib-run"
doctor_missing_lib_run_root="$tmpdir/doctor-missing-lib-run"
doctor_relative_lib_run_root="$tmpdir/doctor-relative-lib-run"
invocation_log="$tmpdir/invocations.log"
fake_binary="$bindir/1cv8"
fake_client="$bindir/1cv8c"
fake_libstdcpp="$tmpdir/libstdc++.so.6"
fake_libgcc="$tmpdir/libgcc_s.so.1"
missing_library="$tmpdir/missing-libstdc++.so.6"

mkdir -p "$bindir"
: >"$invocation_log"
: >"$fake_libstdcpp"
: >"$fake_libgcc"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ -n "${ONEC_INVOCATION_LOG:-}" ]; then
  printf '%s\n' "$(basename "$0")" >>"$ONEC_INVOCATION_LOG"
fi

printf 'fake-%s\n' "$(basename "$0")"
printf 'ld-preload=%s\n' "${LD_PRELOAD:-}"
for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cp "$fake_binary" "$fake_client"
chmod +x "$fake_binary" "$fake_client"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "ld-preload-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary",
    "ldPreload": {
      "enabled": true,
      "libraries": ["$fake_libstdcpp", "$fake_libgcc"]
    }
  },
  "infobase": {
    "mode": "file",
    "filePath": "/tmp/ld-preload-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "xunit": {
      "command": ["$fake_client", "ENTERPRISE", "/F", "/tmp/ld-preload-fixture"]
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

jq 'del(.platform.ldPreload)' "$profile_path" >"$profile_disabled_path"
jq --arg missing_library "$missing_library" '.platform.ldPreload.libraries = [$missing_library, .platform.ldPreload.libraries[1]]' \
  "$profile_path" >"$profile_missing_lib_path"
jq '.platform.ldPreload.libraries = ["relative/libstdc++.so.6", .platform.ldPreload.libraries[1]]' \
  "$profile_path" >"$profile_relative_lib_path"

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
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_run_root" >/dev/null
)

assert_jq "$doctor_run_root/summary.json" '.status == "success"' "doctor-status"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.ld_preload.enabled == true' "doctor-ldpreload-enabled"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.ld_preload.libraries == $ARGS.positional' "doctor-ldpreload-libraries" \
  --args "$fake_libstdcpp" "$fake_libgcc"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ldPreload.enabled" and .status == "present")] | length == 1' "doctor-required-enabled"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ldPreload.libraries" and .status == "present")] | length == 1' "doctor-required-libraries"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "create-ib" and .status == "present")] | length == 1' "doctor-create-capability"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .status == "present")] | length == 1' "doctor-xunit-capability"

(
  cd "$SOURCE_ROOT"
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$create_run_root" >/dev/null
)

assert_jq "$create_run_root/summary.json" '.status == "success"' "create-status"
assert_jq "$create_run_root/summary.json" '.execution.executor == "adapter-wrapper"' "create-executor"
assert_jq "$create_run_root/summary.json" '.adapter_context.ld_preload.enabled == true' "create-ldpreload-enabled"
assert_jq "$create_run_root/summary.json" '.adapter_context.ld_preload.libraries == $ARGS.positional' "create-ldpreload-libraries" \
  --args "$fake_libstdcpp" "$fake_libgcc"
assert_contains "$create_run_root/stdout.log" "fake-1cv8"
assert_contains "$create_run_root/stdout.log" "ld-preload=$fake_libstdcpp:$fake_libgcc"
assert_contains "$invocation_log" "1cv8"

(
  cd "$SOURCE_ROOT"
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_path" --run-root "$xunit_run_root" >/dev/null
)

assert_jq "$xunit_run_root/summary.json" '.status == "success"' "xunit-status"
assert_jq "$xunit_run_root/summary.json" '.execution.source == "profile-command"' "xunit-source"
assert_jq "$xunit_run_root/summary.json" '.execution.executor == "adapter-wrapper"' "xunit-executor"
assert_jq "$xunit_run_root/summary.json" '.adapter_context.ld_preload.enabled == true' "xunit-ldpreload-enabled"
assert_contains "$xunit_run_root/stdout.log" "fake-1cv8c"
assert_contains "$xunit_run_root/stdout.log" "ld-preload=$fake_libstdcpp:$fake_libgcc"
assert_contains "$invocation_log" "1cv8c"

(
  cd "$SOURCE_ROOT"
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_disabled_path" --run-root "$default_run_root" >/dev/null
)

assert_jq "$default_run_root/summary.json" '.status == "success"' "default-status"
assert_jq "$default_run_root/summary.json" 'has("adapter_context") | not' "default-no-adapter-context"
assert_contains "$default_run_root/stdout.log" "fake-1cv8c"
assert_contains "$default_run_root/stdout.log" "ld-preload="
assert_not_contains "$default_run_root/stdout.log" "ld-preload=$fake_libstdcpp:$fake_libgcc"

set +e
(
  cd "$SOURCE_ROOT"
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/platform/create-ib.sh --profile "$profile_missing_lib_path" --run-root "$runtime_missing_lib_run_root" >/dev/null
)
status_missing_lib=$?
set -e

if [ "$status_missing_lib" -eq 0 ]; then
  printf 'expected create-ib to fail when ld-preload library is missing\n' >&2
  exit 1
fi

assert_jq "$runtime_missing_lib_run_root/summary.json" '.status == "failed"' "runtime-missing-lib-status"
assert_contains "$runtime_missing_lib_run_root/stderr.log" "missing direct-platform ld-preload library: $missing_library"

set +e
(
  cd "$SOURCE_ROOT"
  ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-xunit.sh --profile "$profile_relative_lib_path" --run-root "$runtime_relative_lib_run_root" >/dev/null
)
status_relative_lib=$?
set -e

if [ "$status_relative_lib" -eq 0 ]; then
  printf 'expected run-xunit to fail when ld-preload library path is relative\n' >&2
  exit 1
fi

assert_jq "$runtime_relative_lib_run_root/summary.json" '.status == "failed"' "runtime-relative-lib-status"
assert_contains "$runtime_relative_lib_run_root/stderr.log" "direct-platform ld-preload library path must be absolute: relative/libstdc++.so.6"

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$profile_missing_lib_path" --run-root "$doctor_missing_lib_run_root" >/dev/null
)
status_doctor_missing_lib=$?
set -e

if [ "$status_doctor_missing_lib" -eq 0 ]; then
  printf 'expected doctor to fail when ld-preload library is missing\n' >&2
  exit 1
fi

assert_jq "$doctor_missing_lib_run_root/summary.json" '.status == "failed"' "doctor-missing-lib-status"
assert_jq "$doctor_missing_lib_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "create-ib" and .reason == $ARGS.positional[0])] | length == 1' "doctor-missing-lib-create" \
  --args "missing direct-platform ld-preload library: $missing_library"
assert_jq "$doctor_missing_lib_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .reason == $ARGS.positional[0])] | length == 1' "doctor-missing-lib-xunit" \
  --args "missing direct-platform ld-preload library: $missing_library"

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$profile_relative_lib_path" --run-root "$doctor_relative_lib_run_root" >/dev/null
)
status_doctor_relative_lib=$?
set -e

if [ "$status_doctor_relative_lib" -eq 0 ]; then
  printf 'expected doctor to fail when ld-preload library path is relative\n' >&2
  exit 1
fi

assert_jq "$doctor_relative_lib_run_root/summary.json" '.status == "failed"' "doctor-relative-lib-status"
assert_jq "$doctor_relative_lib_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "create-ib" and .reason == "direct-platform ld-preload library path must be absolute: relative/libstdc++.so.6")] | length == 1' "doctor-relative-lib-create"
assert_jq "$doctor_relative_lib_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .reason == "direct-platform ld-preload library path must be absolute: relative/libstdc++.so.6")] | length == 1' "doctor-relative-lib-xunit"
