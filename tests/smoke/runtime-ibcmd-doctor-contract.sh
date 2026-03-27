#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/doctor-ibcmd-profile.json"
run_root="$tmpdir/doctor-ibcmd-run"
invalid_profile_path="$tmpdir/doctor-ibcmd-invalid-profile.json"
invalid_run_root="$tmpdir/doctor-ibcmd-invalid-run"
create_only_profile_path="$tmpdir/doctor-ibcmd-create-only-profile.json"
create_only_run_root="$tmpdir/doctor-ibcmd-create-only-run"
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

export ONEC_IBCMD_PASSWORD="doctor-ibcmd-secret"
export ONEC_DBMS_PASSWORD="doctor-dbms-secret"

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
    "filePath": "/var/tmp/doctor-ibcmd-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/dbms-server"
    },
    "auth": {
      "user": "doctor-ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    },
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "127.0.0.1 port=5432;",
      "name": "doctor_runtime",
      "user": "doctor-db-admin",
      "passwordEnv": "ONEC_DBMS_PASSWORD"
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
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].context.runtime_mode == "dbms-infobase"' "doctor-load-runtime-mode"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].context.server_access.mode == "data-dir"' "doctor-load-server-access"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].context.topology.dbms.kind == "PostgreSQL"' "doctor-load-dbms-kind"
assert_jq "$run_root/summary.json" '.capability_drivers["load-src"].context.topology.dbms.password_configured == true' "doctor-load-dbms-password"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "platform.ibcmdPath" and .status == "present")] | length == 1' "doctor-ibcmd-path"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.runtimeMode" and .status == "present")] | length == 1' "doctor-runtime-mode"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.serverAccess.mode" and .status == "present")] | length == 1' "doctor-server-access-mode"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.serverAccess.dataDir" and .status == "present")] | length == 1' "doctor-data-dir"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dbmsInfobase.kind" and .status == "present")] | length == 1' "doctor-dbms-kind-field"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dbmsInfobase.server" and .status == "present")] | length == 1' "doctor-dbms-server-field"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dbmsInfobase.name" and .status == "present")] | length == 1' "doctor-dbms-name-field"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dbmsInfobase.user" and .status == "present")] | length == 1' "doctor-dbms-user-field"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.dbmsInfobase.passwordEnv" and .status == "present")] | length == 1' "doctor-dbms-password-field"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.auth.user" and .status == "present")] | length == 1' "doctor-ibcmd-auth-user"
assert_jq "$run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.auth.passwordEnv" and .status == "present")] | length == 1' "doctor-ibcmd-auth-password-env"
assert_jq "$run_root/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_DBMS_PASSWORD" and .status == "set")] | length == 1' "doctor-dbms-env-ref"
assert_jq "$run_root/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_IBCMD_PASSWORD" and .status == "set")] | length == 1' "doctor-ibcmd-env-ref"
assert_jq "$run_root/summary.json" '[.checks.required_capabilities[] | select(.status != "present")] | length == 0' "doctor-required-capabilities"
assert_jq "$run_root/summary.json" '[.checks.derived_contours[] | select(.name == "load-diff-src" and .status == "present" and .driver == "ibcmd" and .reason == null)] | length == 1' "doctor-load-diff-derived-present"
assert_jq "$run_root/summary.json" '[.checks.derived_contours[] | select(.name == "load-task-src" and .status == "present" and .driver == "ibcmd" and .reason == null)] | length == 1' "doctor-load-task-derived-present"

if [ ! -f "$run_root/stdout.log" ] || [ ! -f "$run_root/stderr.log" ]; then
  printf 'doctor run must create stdout.log and stderr.log\n' >&2
  exit 1
fi

if grep -Fq -- "doctor-ibcmd-secret" "$run_root/summary.json"; then
  printf 'doctor summary.json must not contain resolved ibcmd secrets\n' >&2
  cat "$run_root/summary.json" >&2
  exit 1
fi

if grep -Fq -- "doctor-dbms-secret" "$run_root/summary.json"; then
  printf 'doctor summary.json must not contain resolved dbms secrets\n' >&2
  cat "$run_root/summary.json" >&2
  exit 1
fi

cat >"$invalid_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-ibcmd-invalid-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-ibcmd-invalid-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/dbms-server"
    },
    "auth": {
      "user": "doctor-ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    },
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "127.0.0.1 port=5432;",
      "user": "doctor-db-admin",
      "passwordEnv": "ONEC_DBMS_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
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

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$invalid_profile_path" --run-root "$invalid_run_root" >/dev/null
)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  printf 'doctor unexpectedly succeeded for invalid ibcmd profile\n' >&2
  exit 1
fi

assert_jq "$invalid_run_root/summary.json" '.status == "failed"' "doctor-invalid-status"
assert_jq "$invalid_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "dump-src" and .status == "missing" and .reason == "missing ibcmd.dbmsInfobase.name")] | length == 1' "doctor-invalid-dump-reason"
assert_jq "$invalid_run_root/summary.json" '.capability_drivers["dump-src"].status == "missing"' "doctor-invalid-driver-status"
assert_jq "$invalid_run_root/summary.json" '.capability_drivers["dump-src"].reason == "missing ibcmd.dbmsInfobase.name"' "doctor-invalid-driver-reason"

cat >"$create_only_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-ibcmd-create-only",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-ibcmd-create-only",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/create-only-server"
    },
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "127.0.0.1 port=5432;",
      "name": "doctor_create_only",
      "user": "doctor-db-admin",
      "passwordEnv": "ONEC_DBMS_PASSWORD"
    }
  },
  "capabilities": {
    "createIb": {
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

(
  cd "$SOURCE_ROOT"
  ./scripts/diag/doctor.sh --profile "$create_only_profile_path" --run-root "$create_only_run_root" >/dev/null
)

assert_jq "$create_only_run_root/summary.json" '.status == "success"' "doctor-create-only-status"
assert_jq "$create_only_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.auth.user")] | length == 0' "doctor-create-only-no-auth-user-field"
assert_jq "$create_only_run_root/summary.json" '[.checks.required_profile_fields[] | select(.name == "ibcmd.auth.passwordEnv")] | length == 0' "doctor-create-only-no-auth-password-field"
assert_jq "$create_only_run_root/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_IBCMD_PASSWORD")] | length == 0' "doctor-create-only-no-ibcmd-env-ref"
assert_jq "$create_only_run_root/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_DBMS_PASSWORD" and .status == "set")] | length == 1' "doctor-create-only-dbms-env-ref"
assert_jq "$create_only_run_root/summary.json" '[.checks.derived_contours[] | select(.name == "load-task-src" and .status == "missing" and .driver == "designer" and .reason == "partial load-src requires capabilities.loadSrc.driver=ibcmd")] | length == 1' "doctor-create-only-derived-missing"

helper_repo="$tmpdir/doctor-helper-gap-repo"
cp -R "$SOURCE_ROOT" "$helper_repo"
rm -f "$helper_repo/scripts/git/task-trailers.sh"

cat >"$helper_repo/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "doctor-helper-gap",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/doctor-helper-gap",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/helper-gap-server"
    },
    "auth": {
      "user": "doctor-ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/helper-gap-db"
    }
  },
  "capabilities": {
    "createIb": {
      "driver": "designer"
    },
    "dumpSrc": {
      "driver": "designer"
    },
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf"
    },
    "updateDb": {
      "driver": "designer"
    },
    "diffSrc": {
      "command": ["git", "diff", "--", "./src"]
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

helper_gap_run_root="$tmpdir/doctor-helper-gap-run"
(
  cd "$helper_repo"
  ./scripts/diag/doctor.sh --profile env/local.json --run-root "$helper_gap_run_root" >/dev/null
)

assert_jq "$helper_gap_run_root/summary.json" '[.checks.derived_contours[] | select(.name == "load-task-src" and .status == "missing" and .driver == "ibcmd" and .reason == "missing repo helper: scripts/git/task-trailers.sh")] | length == 1' "doctor-helper-gap-load-task-derived"
assert_jq "$helper_gap_run_root/summary.json" '[.checks.derived_contours[] | select(.name == "load-diff-src" and .status == "present" and .driver == "ibcmd")] | length == 1' "doctor-helper-gap-load-diff-present"
