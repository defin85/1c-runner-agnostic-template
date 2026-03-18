#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/doctor-profile.json"
run_root="$tmpdir/doctor-run"
command_override_profile_path="$tmpdir/doctor-command-profile.json"
command_override_run_root="$tmpdir/doctor-command-run"
ld_preload_profile_path="$tmpdir/doctor-ld-preload-profile.json"
ld_preload_run_root="$tmpdir/doctor-ld-preload-run"
fake_binary="$tmpdir/fake-1cv8"
fake_libstdcpp="$tmpdir/libstdc++.so.6"
fake_libgcc="$tmpdir/libgcc_s.so.1"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$fake_binary"
: >"$fake_libstdcpp"
: >"$fake_libgcc"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-fixture",
    "auth": {
      "mode": "user-password",
      "user": "doctor-user",
      "passwordEnv": "ONEC_DOCTOR_PASSWORD"
    }
  },
  "capabilities": {
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

export ONEC_DOCTOR_PASSWORD="doctor-secret"

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
  ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$run_root" >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success"' "doctor-status"
assert_jq "$run_root/summary.json" '.capability.id == "doctor"' "doctor-capability"
assert_jq "$run_root/summary.json" '.adapter == "direct-platform"' "doctor-adapter"
assert_jq "$run_root/summary.json" '.artifacts.stdout_log == ($ARGS.positional[0])' "doctor-stdout-log" --args "$run_root/stdout.log"
assert_jq "$run_root/summary.json" '.artifacts.stderr_log == ($ARGS.positional[0])' "doctor-stderr-log" --args "$run_root/stderr.log"
assert_jq "$run_root/summary.json" '.capability_drivers["create-ib"].driver == "designer"' "doctor-create-driver"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].driver == "designer"' "doctor-load-driver"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.status != "present")] | length == 0' "doctor-required-fields"
assert_jq "$run_root/summary.json" '[.checks.required_env_refs[] | select(.status != "set")] | length == 0' "doctor-required-env-refs"
assert_jq "$run_root/summary.json" '[.checks.required_capabilities[] | select(.status != "present")] | length == 0' "doctor-required-capabilities"
assert_jq "$run_root/summary.json" '[.checks.required_tools[] | select(.status != "present")] | length == 0' "doctor-required-tools"

if [ ! -f "$run_root/stdout.log" ] || [ ! -f "$run_root/stderr.log" ]; then
  printf 'doctor run must create stdout.log and stderr.log\n' >&2
  exit 1
fi

if ! grep -Fq -- "Run 1C runtime doctor" "$run_root/stdout.log"; then
  printf 'doctor stdout.log must contain execution log\n' >&2
  cat "$run_root/stdout.log" >&2
  exit 1
fi

if grep -Fq -- "doctor-secret" "$run_root/summary.json"; then
  printf 'doctor summary.json must not contain resolved secrets\n' >&2
  cat "$run_root/summary.json" >&2
  exit 1
fi

cat >"$command_override_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-command-override-fixture",
  "runnerAdapter": "direct-platform",
  "capabilities": {
    "createIb": {
      "command": ["bash", "-lc", "printf 'create-command-ok\\\\n'"]
    },
    "dumpSrc": {
      "command": ["bash", "-lc", "printf 'dump-command-ok\\\\n'"]
    },
    "loadSrc": {
      "command": ["bash", "-lc", "printf 'load-command-ok\\\\n'"]
    },
    "updateDb": {
      "command": ["bash", "-lc", "printf 'update-command-ok\\\\n'"]
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

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$command_override_profile_path" --run-root "$command_override_run_root" >/dev/null
)

assert_jq "$command_override_run_root/summary.json" '.status == "success"' "doctor-command-status"
assert_jq "$command_override_run_root/summary.json" '.checks.required_profile_fields == [{"name":"runnerAdapter","status":"present","required":true,"reason":null}]' "doctor-command-required-fields"
assert_jq "$command_override_run_root/summary.json" '.checks.required_env_refs == []' "doctor-command-required-env-refs"
assert_jq "$command_override_run_root/summary.json" '.capability_drivers["create-ib"].source == "profile-command"' "doctor-command-create-source"
assert_jq "$command_override_run_root/summary.json" '.capability_drivers["create-ib"].driver == null' "doctor-command-create-driver"
assert_jq "$command_override_run_root/summary.json" '.capability_drivers["load-src"].source == "profile-command"' "doctor-command-load-source"
assert_jq "$command_override_run_root/summary.json" '.capability_drivers["load-src"].driver == null' "doctor-command-load-driver"

cat >"$ld_preload_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-ld-preload-fixture",
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
    "filePath": "/var/tmp/doctor-ld-preload-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "xunit": {
      "command": ["$fake_binary", "ENTERPRISE", "/F", "/tmp/doctor-ld-preload-fixture"]
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

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$ld_preload_profile_path" --run-root "$ld_preload_run_root" >/dev/null
)

assert_jq "$ld_preload_run_root/summary.json" '.status == "success"' "doctor-ld-preload-status"
assert_jq "$ld_preload_run_root/summary.json" '.adapter_context.ld_preload.enabled == true' "doctor-ld-preload-enabled"
assert_jq "$ld_preload_run_root/summary.json" '.adapter_context.ld_preload.libraries == $ARGS.positional' "doctor-ld-preload-libraries" \
  --args "$fake_libstdcpp" "$fake_libgcc"
assert_jq "$ld_preload_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ldPreload.enabled" and .status == "present")] | length == 1' "doctor-ld-preload-required-enabled"
assert_jq "$ld_preload_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ldPreload.libraries" and .status == "present")] | length == 1' "doctor-ld-preload-required-libraries"
assert_jq "$ld_preload_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .status == "present")] | length == 1' "doctor-ld-preload-capability"

if grep -Fq -- "LD_PRELOAD=" "$ld_preload_run_root/summary.json"; then
  printf 'doctor summary.json must not contain raw LD_PRELOAD prefixes\n' >&2
  cat "$ld_preload_run_root/summary.json" >&2
  exit 1
fi
