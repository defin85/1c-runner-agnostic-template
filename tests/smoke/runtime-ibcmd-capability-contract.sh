#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/ibcmd-profile.json"
run_root_create="$tmpdir/run-create"
run_root_dump="$tmpdir/run-dump"
run_root_load_full="$tmpdir/run-load-full"
run_root_load_partial="$tmpdir/run-load-partial"
run_root_update="$tmpdir/run-update"
fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"
mixed_profile_path="$tmpdir/mixed-profile.json"
mixed_run_root_create="$tmpdir/mixed-run-create"
mixed_run_root_dump="$tmpdir/mixed-run-dump"
mixed_run_root_load="$tmpdir/mixed-run-load"
mixed_run_root_update="$tmpdir/mixed-run-update"
mixed_fake_designer="$tmpdir/mixed-fake-1cv8"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'designer-must-not-run\n' >&2
exit 99
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done

printf 'fake-ibcmd-stderr\n' >&2
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

cat >"$mixed_fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done

printf 'mixed-fake-designer-stderr\n' >&2
EOF

chmod +x "$mixed_fake_designer"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "ibcmd-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/designer-fallback-should-not-run",
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
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "createIb": {
      "driver": "ibcmd"
    },
    "dumpSrc": {
      "driver": "ibcmd",
      "outputDir": "./src/cf"
    },
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf"
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

export ONEC_IBCMD_PASSWORD="ibcmd-secret"

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
  ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$run_root_create" >/dev/null
)

assert_jq "$run_root_create/summary.json" '.status == "success"' "create-status"
assert_jq "$run_root_create/summary.json" '.driver == "ibcmd"' "create-driver"
assert_jq "$run_root_create/summary.json" '.execution.source == "ibcmd-builder"' "create-source"
assert_jq "$run_root_create/summary.json" '.driver_context.connection_mode == "data-dir"' "create-connection-mode"
assert_contains "$run_root_create/stdout.log" "infobase"
assert_contains "$run_root_create/stdout.log" "create"
assert_contains "$run_root_create/stdout.log" "--data=$tmpdir/standalone"
assert_contains "$run_root_create/stdout.log" "--database-path=$tmpdir/standalone/db-data"
assert_contains "$run_root_create/stdout.log" "--create-database"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/dump-src.sh --profile "$profile_path" --run-root "$run_root_dump" >/dev/null
)

assert_jq "$run_root_dump/summary.json" '.status == "success"' "dump-status"
assert_jq "$run_root_dump/summary.json" '.driver == "ibcmd"' "dump-driver"
assert_jq "$run_root_dump/summary.json" '.execution.source == "ibcmd-builder"' "dump-source"
assert_contains "$run_root_dump/stdout.log" "config"
assert_contains "$run_root_dump/stdout.log" "export"
assert_contains "$run_root_dump/stdout.log" "./src/cf"
assert_contains "$run_root_dump/stdout.log" "--format=hierarchical"
assert_contains "$run_root_dump/stdout.log" "--user=ibcmd-user"
assert_contains "$run_root_dump/stdout.log" "--password=ibcmd-secret"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/load-src.sh --profile "$profile_path" --run-root "$run_root_load_full" >/dev/null
)

assert_jq "$run_root_load_full/summary.json" '.status == "success"' "load-full-status"
assert_jq "$run_root_load_full/summary.json" '.driver == "ibcmd"' "load-full-driver"
assert_contains "$run_root_load_full/stdout.log" "config"
assert_contains "$run_root_load_full/stdout.log" "import"
assert_contains "$run_root_load_full/stdout.log" "./src/cf"
assert_contains "$run_root_load_full/stdout.log" "--format=hierarchical"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/load-src.sh \
    --profile "$profile_path" \
    --run-root "$run_root_load_partial" \
    --files "Catalogs/Items.xml,Forms/List.xml" >/dev/null
)

assert_jq "$run_root_load_partial/summary.json" '.status == "success"' "load-partial-status"
assert_jq "$run_root_load_partial/summary.json" '.driver == "ibcmd"' "load-partial-driver"
assert_jq "$run_root_load_partial/summary.json" '.driver_context.partial_import == true' "load-partial-flag"
assert_contains "$run_root_load_partial/stdout.log" "import"
assert_contains "$run_root_load_partial/stdout.log" "files"
assert_contains "$run_root_load_partial/stdout.log" "--partial"
assert_contains "$run_root_load_partial/stdout.log" "--base-dir=./src/cf"
assert_contains "$run_root_load_partial/stdout.log" "Catalogs/Items.xml"
assert_contains "$run_root_load_partial/stdout.log" "Forms/List.xml"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/update-db.sh --profile "$profile_path" --run-root "$run_root_update" >/dev/null
)

assert_jq "$run_root_update/summary.json" '.status == "success"' "update-status"
assert_jq "$run_root_update/summary.json" '.driver == "ibcmd"' "update-driver"
assert_jq "$run_root_update/summary.json" '.execution.source == "ibcmd-builder"' "update-source"
assert_contains "$run_root_update/stdout.log" "config"
assert_contains "$run_root_update/stdout.log" "apply"

if grep -Fq -- "ibcmd-secret" "$run_root_create/summary.json"; then
  printf 'summary.json must not contain resolved secrets\n' >&2
  cat "$run_root_create/summary.json" >&2
  exit 1
fi

cat >"$mixed_profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "mixed-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$mixed_fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/mixed-driver-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/mixed-standalone",
    "databasePath": "$tmpdir/mixed-standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "ibcmd",
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

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/create-ib.sh --profile "$mixed_profile_path" --run-root "$mixed_run_root_create" >/dev/null
)

assert_jq "$mixed_run_root_create/summary.json" '.driver == "designer"' "mixed-create-driver"
assert_contains "$mixed_run_root_create/stdout.log" "CREATEINFOBASE"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/dump-src.sh --profile "$mixed_profile_path" --run-root "$mixed_run_root_dump" >/dev/null
)

assert_jq "$mixed_run_root_dump/summary.json" '.driver == "designer"' "mixed-dump-driver"
assert_contains "$mixed_run_root_dump/stdout.log" "/DumpConfigToFiles"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/load-src.sh --profile "$mixed_profile_path" --run-root "$mixed_run_root_load" >/dev/null
)

assert_jq "$mixed_run_root_load/summary.json" '.driver == "ibcmd"' "mixed-load-driver"
assert_contains "$mixed_run_root_load/stdout.log" "config"
assert_contains "$mixed_run_root_load/stdout.log" "import"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/update-db.sh --profile "$mixed_profile_path" --run-root "$mixed_run_root_update" >/dev/null
)

assert_jq "$mixed_run_root_update/summary.json" '.driver == "designer"' "mixed-update-driver"
assert_contains "$mixed_run_root_update/stdout.log" "/UpdateDBCfg"
