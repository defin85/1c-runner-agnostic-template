#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
root_drift_profile_path="$SOURCE_ROOT/env/runtime-doctor-drift.fixture.json"
policy_path="$SOURCE_ROOT/automation/context/runtime-profile-policy.json"
policy_backup="$tmpdir/runtime-profile-policy.backup"

cleanup() {
  rm -rf "$tmpdir"
  rm -f "$root_drift_profile_path"
  if [ -f "$policy_backup" ]; then
    mv "$policy_backup" "$policy_path"
  else
    rm -f "$policy_path"
  fi
}

if [ -f "$policy_path" ]; then
  cp "$policy_path" "$policy_backup"
fi

trap cleanup EXIT

profile_path="$tmpdir/doctor-profile.json"
run_root="$tmpdir/doctor-run"
unsupported_profile_path="$tmpdir/doctor-unsupported-profile.json"
unsupported_run_root="$tmpdir/doctor-unsupported-run"
command_override_profile_path="$tmpdir/doctor-command-profile.json"
command_override_run_root="$tmpdir/doctor-command-run"
ld_preload_profile_path="$tmpdir/doctor-ld-preload-profile.json"
ld_preload_run_root="$tmpdir/doctor-ld-preload-run"
layout_warning_run_root="$tmpdir/doctor-layout-warning-run"
layout_clean_run_root="$tmpdir/doctor-layout-clean-run"
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

cat >"$unsupported_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-unsupported-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-unsupported-fixture",
    "auth": {
      "mode": "os"
    }
  },
  "capabilities": {
    "xunit": {
      "unsupportedReason": "xUnit contour is not wired yet"
    },
    "bdd": {
      "unsupportedReason": "BDD contour is not wired yet"
    },
    "smoke": {
      "unsupportedReason": "Smoke contour is not wired yet"
    },
    "publishHttp": {
      "unsupportedReason": "Publish contour is not wired yet"
    }
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$unsupported_profile_path" --run-root "$unsupported_run_root" >/dev/null
)

assert_jq "$unsupported_run_root/summary.json" '.status == "success"' "doctor-unsupported-status"
assert_jq "$unsupported_run_root/summary.json" '[.checks.required_capabilities[] | select(.status == "missing")] | length == 0' "doctor-unsupported-no-missing"
assert_jq "$unsupported_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-xunit" and .status == "unsupported" and .reason == "xUnit contour is not wired yet")] | length == 1' "doctor-unsupported-xunit"
assert_jq "$unsupported_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-bdd" and .status == "unsupported" and .reason == "BDD contour is not wired yet")] | length == 1' "doctor-unsupported-bdd"
assert_jq "$unsupported_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-smoke" and .status == "unsupported" and .reason == "Smoke contour is not wired yet")] | length == 1' "doctor-unsupported-smoke"
assert_jq "$unsupported_run_root/summary.json" '[.checks.optional_capabilities[] | select(.name == "publish-http" and .status == "unsupported" and .reason == "Publish contour is not wired yet")] | length == 1' "doctor-unsupported-publish-http"

cat >"$root_drift_profile_path" <<'EOF'
{
  "fixture": true
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$layout_warning_run_root" >/dev/null
)

assert_jq "$layout_warning_run_root/summary.json" '.status == "success"' "doctor-layout-warning-status"
assert_jq "$layout_warning_run_root/summary.json" '.warnings.runtime_profile_layout.status == "warning"' "doctor-layout-warning-state"
assert_jq "$layout_warning_run_root/summary.json" '.warnings.runtime_profile_layout.recommended_sandbox == "env/.local/"' "doctor-layout-warning-sandbox"
assert_jq "$layout_warning_run_root/summary.json" '.warnings.runtime_profile_layout.policy_path == "automation/context/runtime-profile-policy.json"' "doctor-layout-warning-policy-path"
assert_jq "$layout_warning_run_root/summary.json" '.warnings.runtime_profile_layout.unexpected_root_profiles | index($ARGS.positional[0]) != null' "doctor-layout-warning-path" \
  --args "env/runtime-doctor-drift.fixture.json"

if ! grep -Fq -- "env/.local/" "$layout_warning_run_root/stdout.log"; then
  printf 'doctor stdout.log must mention env/.local/ recommendation when layout drifts\n' >&2
  cat "$layout_warning_run_root/stdout.log" >&2
  exit 1
fi

cat >"$policy_path" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [
      "env/runtime-doctor-drift.fixture.json"
    ],
    "localSandbox": "env/.local/"
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$layout_clean_run_root" >/dev/null
)

assert_jq "$layout_clean_run_root/summary.json" '.status == "success"' "doctor-layout-clean-status"
assert_jq "$layout_clean_run_root/summary.json" '.warnings.runtime_profile_layout.status == "clean"' "doctor-layout-clean-warning-state"
assert_jq "$layout_clean_run_root/summary.json" '.warnings.runtime_profile_layout.unexpected_root_profiles == []' "doctor-layout-clean-drift-empty"
assert_jq "$layout_clean_run_root/summary.json" '.warnings.runtime_profile_layout.sanctioned_additional_profiles == ["env/runtime-doctor-drift.fixture.json"]' "doctor-layout-clean-sanctioned"

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
