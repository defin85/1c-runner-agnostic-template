#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/doctor-ibcmd-profile.json"
run_root="$tmpdir/doctor-ibcmd-run"
fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-ibcmd-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-designer-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "doctor-ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "createIb": {
      "driver": "ibcmd"
    },
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "loadSrc": {
      "driver": "ibcmd"
    },
    "updateDb": {
      "driver": "ibcmd"
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

export ONEC_IBCMD_PASSWORD="doctor-ibcmd-secret"

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
assert_jq "$run_root/summary.json" '.adapter == "direct-platform"' "doctor-adapter"
assert_jq "$run_root/summary.json" '.artifacts.stdout_log == ($ARGS.positional[0])' "doctor-stdout-log" --args "$run_root/stdout.log"
assert_jq "$run_root/summary.json" '.artifacts.stderr_log == ($ARGS.positional[0])' "doctor-stderr-log" --args "$run_root/stderr.log"
assert_jq "$run_root/summary.json" '.capability_drivers["create-ib"].driver == "ibcmd"' "doctor-create-driver"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].driver == "ibcmd"' "doctor-load-driver"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].context.connection_mode == "data-dir"' "doctor-load-connection-mode"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ibcmdPath" and .status == "present")] | length == 1' "doctor-ibcmd-path"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.connectionMode" and .status == "present")] | length == 1' "doctor-connection-mode"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dataDir" and .status == "present")] | length == 1' "doctor-data-dir"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.databasePath" and .status == "present")] | length == 1' "doctor-database-path"
assert_jq "$run_root/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_IBCMD_PASSWORD" and .status == "set")] | length == 1' "doctor-env-ref"
assert_jq "$run_root/summary.json" '[.checks.required_capabilities[] | select(.status != "present")] | length == 0' "doctor-required-capabilities"

if [ ! -f "$run_root/stdout.log" ] || [ ! -f "$run_root/stderr.log" ]; then
  printf 'doctor run must create stdout.log and stderr.log\n' >&2
  exit 1
fi

if grep -Fq -- "doctor-ibcmd-secret" "$run_root/summary.json"; then
  printf 'doctor summary.json must not contain resolved secrets\n' >&2
  cat "$run_root/summary.json" >&2
  exit 1
fi
