#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/doctor-profile.json"
run_root="$tmpdir/doctor-run"
fake_binary="$tmpdir/fake-1cv8"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$fake_binary"

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
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.status != "present")] | length == 0' "doctor-required-fields"
assert_jq "$run_root/summary.json" '[.checks.required_env_refs[] | select(.status != "set")] | length == 0' "doctor-required-env-refs"
assert_jq "$run_root/summary.json" '[.checks.required_capabilities[] | select(.status != "present")] | length == 0' "doctor-required-capabilities"
assert_jq "$run_root/summary.json" '[.checks.required_tools[] | select(.status != "present")] | length == 0' "doctor-required-tools"

if grep -Fq -- "doctor-secret" "$run_root/summary.json"; then
  printf 'doctor summary.json must not contain resolved secrets\n' >&2
  cat "$run_root/summary.json" >&2
  exit 1
fi
