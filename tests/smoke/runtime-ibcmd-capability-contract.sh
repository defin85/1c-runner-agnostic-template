#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"
standalone_profile="$tmpdir/standalone-profile.json"
file_profile="$tmpdir/file-profile.json"
dbms_profile="$tmpdir/dbms-profile.json"
mixed_profile="$tmpdir/mixed-profile.json"
expected_src_cf="$(realpath -m "$SOURCE_ROOT/src/cf")"

export ONEC_IBCMD_PASSWORD="ibcmd-secret"
export ONEC_DBMS_PASSWORD="dbms-secret"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done

printf 'fake-designer-stderr\n' >&2
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
  local text="$2"

  if grep -Fq -- "$text" "$file"; then
    printf 'unexpected text found: %s\n' "$text" >&2
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

write_ibcmd_profile() {
  local profile_path="$1"
  local profile_name="$2"
  local runtime_mode="$3"
  local topology_json="$4"
  local capabilities_json="$5"
  local data_dir="$6"
  local include_auth="$7"

  jq -n \
    --arg profile_name "$profile_name" \
    --arg fake_designer "$fake_designer" \
    --arg fake_ibcmd "$fake_ibcmd" \
    --arg data_dir "$data_dir" \
    --arg runtime_mode "$runtime_mode" \
    --argjson topology "$topology_json" \
    --argjson capabilities "$capabilities_json" \
    --argjson include_auth "$include_auth" \
    '{
      schemaVersion: 2,
      profileName: $profile_name,
      runnerAdapter: "direct-platform",
      platform: {
        binaryPath: $fake_designer,
        ibcmdPath: $fake_ibcmd
      },
      infobase: {
        mode: "file",
        filePath: "/var/tmp/ibcmd-fixture",
        auth: {
          mode: "os",
          user: null,
          passwordEnv: null
        }
      },
      ibcmd: (
        {
          runtimeMode: $runtime_mode,
          serverAccess: {
            mode: "data-dir",
            dataDir: $data_dir
          }
        }
        + (if $include_auth then {
            auth: {
              user: "ibcmd-user",
              passwordEnv: "ONEC_IBCMD_PASSWORD"
            }
          } else {} end)
        + $topology
      ),
      capabilities: $capabilities
    }' >"$profile_path"
}

all_ibcmd_capabilities_json='{
  "createIb": {"driver": "ibcmd"},
  "dumpSrc": {"driver": "ibcmd", "outputDir": "./src/cf"},
  "loadSrc": {"driver": "ibcmd", "sourceDir": "./src/cf"},
  "updateDb": {"driver": "ibcmd"},
  "xunit": {"command": ["bash", "-lc", "printf '\''xunit-ok\\n'\''"]},
  "bdd": {"command": ["bash", "-lc", "printf '\''bdd-ok\\n'\''"]},
  "smoke": {"command": ["bash", "-lc", "printf '\''smoke-ok\\n'\''"]}
}'

mixed_capabilities_json='{
  "loadSrc": {"driver": "ibcmd", "sourceDir": "./src/cf"},
  "xunit": {"command": ["bash", "-lc", "printf '\''xunit-ok\\n'\''"]},
  "bdd": {"command": ["bash", "-lc", "printf '\''bdd-ok\\n'\''"]},
  "smoke": {"command": ["bash", "-lc", "printf '\''smoke-ok\\n'\''"]}
}'

write_ibcmd_profile \
  "$standalone_profile" \
  "standalone-fixture" \
  "standalone-server" \
  "{\"standalone\":{\"databasePath\":\"$tmpdir/standalone/db\"}}" \
  "$all_ibcmd_capabilities_json" \
  "$tmpdir/standalone" \
  true

write_ibcmd_profile \
  "$file_profile" \
  "file-fixture" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$all_ibcmd_capabilities_json" \
  "$tmpdir/file-server" \
  true

write_ibcmd_profile \
  "$dbms_profile" \
  "dbms-fixture" \
  "dbms-infobase" \
  "{\"dbmsInfobase\":{\"kind\":\"PostgreSQL\",\"server\":\"127.0.0.1 port=5432;\",\"name\":\"runtime_fixture\",\"user\":\"db-admin\",\"passwordEnv\":\"ONEC_DBMS_PASSWORD\"}}" \
  "$all_ibcmd_capabilities_json" \
  "$tmpdir/dbms-server" \
  true

write_ibcmd_profile \
  "$mixed_profile" \
  "mixed-fixture" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/mixed-file-ib/db\"}}" \
  "$mixed_capabilities_json" \
  "$tmpdir/mixed-file-server" \
  true

run_capability() {
  local profile_path="$1"
  local run_root="$2"
  shift 2

  (
    cd "$SOURCE_ROOT"
    "$@" --profile "$profile_path" --run-root "$run_root" >/dev/null
  )
}

assert_ibcmd_summary() {
  local summary_path="$1"
  local runtime_mode="$2"

  assert_jq "$summary_path" '.status == "success"' "status"
  assert_jq "$summary_path" '.driver == "ibcmd"' "driver"
  assert_jq "$summary_path" '.execution.source == "ibcmd-builder"' "source"
  assert_jq "$summary_path" '.driver_context.runtime_mode == $ARGS.positional[0]' "runtime-mode" --args "$runtime_mode"
  assert_jq "$summary_path" '.driver_context.server_access.mode == "data-dir"' "server-access-mode"
}

standalone_create_run="$tmpdir/standalone-create"
standalone_dump_run="$tmpdir/standalone-dump"
standalone_load_full_run="$tmpdir/standalone-load-full"
standalone_load_partial_run="$tmpdir/standalone-load-partial"
standalone_update_run="$tmpdir/standalone-update"

run_capability "$standalone_profile" "$standalone_create_run" ./scripts/platform/create-ib.sh
assert_ibcmd_summary "$standalone_create_run/summary.json" "standalone-server"
assert_jq "$standalone_create_run/summary.json" '.driver_context.topology.database_path == $ARGS.positional[0]' "standalone-db-path" --args "$tmpdir/standalone/db"
assert_contains "$standalone_create_run/stdout.log" "infobase"
assert_contains "$standalone_create_run/stdout.log" "create"
assert_contains "$standalone_create_run/stdout.log" "--data=$tmpdir/standalone"
assert_contains "$standalone_create_run/stdout.log" "--database-path=$tmpdir/standalone/db"
assert_contains "$standalone_create_run/stdout.log" "--create-database"
assert_not_contains "$standalone_create_run/stdout.log" "--user=ibcmd-user"
assert_not_contains "$standalone_create_run/stdout.log" "--password=ibcmd-secret"

run_capability "$standalone_profile" "$standalone_dump_run" ./scripts/platform/dump-src.sh
assert_ibcmd_summary "$standalone_dump_run/summary.json" "standalone-server"
assert_contains "$standalone_dump_run/stdout.log" "config"
assert_contains "$standalone_dump_run/stdout.log" "export"
assert_contains "$standalone_dump_run/stdout.log" "--data=$tmpdir/standalone"
assert_contains "$standalone_dump_run/stdout.log" "--database-path=$tmpdir/standalone/db"
assert_contains "$standalone_dump_run/stdout.log" "--user=ibcmd-user"
assert_contains "$standalone_dump_run/stdout.log" "--password=ibcmd-secret"
assert_contains "$standalone_dump_run/stdout.log" "$expected_src_cf"
assert_not_contains "$standalone_dump_run/stdout.log" "--dir=$expected_src_cf"
assert_not_contains "$standalone_dump_run/stdout.log" "--format=hierarchical"

run_capability "$standalone_profile" "$standalone_load_full_run" ./scripts/platform/load-src.sh
assert_ibcmd_summary "$standalone_load_full_run/summary.json" "standalone-server"
assert_contains "$standalone_load_full_run/stdout.log" "config"
assert_contains "$standalone_load_full_run/stdout.log" "import"
assert_contains "$standalone_load_full_run/stdout.log" "--database-path=$tmpdir/standalone/db"
assert_contains "$standalone_load_full_run/stdout.log" "--user=ibcmd-user"
assert_contains "$standalone_load_full_run/stdout.log" "--password=ibcmd-secret"
assert_contains "$standalone_load_full_run/stdout.log" "$expected_src_cf"
assert_not_contains "$standalone_load_full_run/stdout.log" "--dir=$expected_src_cf"
assert_not_contains "$standalone_load_full_run/stdout.log" "--format=hierarchical"

(
  cd "$SOURCE_ROOT"
  ./scripts/platform/load-src.sh \
    --profile "$standalone_profile" \
    --run-root "$standalone_load_partial_run" \
    --files "Catalogs/Items.xml,Forms/List.xml" >/dev/null
)
assert_ibcmd_summary "$standalone_load_partial_run/summary.json" "standalone-server"
assert_jq "$standalone_load_partial_run/summary.json" '.driver_context.partial_import == true' "standalone-partial-import"
assert_contains "$standalone_load_partial_run/stdout.log" "config"
assert_contains "$standalone_load_partial_run/stdout.log" "import"
assert_contains "$standalone_load_partial_run/stdout.log" "files"
assert_contains "$standalone_load_partial_run/stdout.log" "--base-dir=$expected_src_cf"
assert_contains "$standalone_load_partial_run/stdout.log" "--partial"
assert_contains "$standalone_load_partial_run/stdout.log" "Catalogs/Items.xml"
assert_contains "$standalone_load_partial_run/stdout.log" "Forms/List.xml"

run_capability "$standalone_profile" "$standalone_update_run" ./scripts/platform/update-db.sh
assert_ibcmd_summary "$standalone_update_run/summary.json" "standalone-server"
assert_contains "$standalone_update_run/stdout.log" "config"
assert_contains "$standalone_update_run/stdout.log" "apply"
assert_contains "$standalone_update_run/stdout.log" "--database-path=$tmpdir/standalone/db"
assert_contains "$standalone_update_run/stdout.log" "--force"

file_create_run="$tmpdir/file-create"
file_dump_run="$tmpdir/file-dump"
file_load_run="$tmpdir/file-load"
file_update_run="$tmpdir/file-update"

run_capability "$file_profile" "$file_create_run" ./scripts/platform/create-ib.sh
assert_ibcmd_summary "$file_create_run/summary.json" "file-infobase"
assert_jq "$file_create_run/summary.json" '.driver_context.topology.database_path == $ARGS.positional[0]' "file-db-path" --args "$tmpdir/file-ib/db"
assert_contains "$file_create_run/stdout.log" "--data=$tmpdir/file-server"
assert_contains "$file_create_run/stdout.log" "--database-path=$tmpdir/file-ib/db"
assert_not_contains "$file_create_run/stdout.log" "--user=ibcmd-user"

run_capability "$file_profile" "$file_dump_run" ./scripts/platform/dump-src.sh
assert_ibcmd_summary "$file_dump_run/summary.json" "file-infobase"
assert_contains "$file_dump_run/stdout.log" "--database-path=$tmpdir/file-ib/db"
assert_contains "$file_dump_run/stdout.log" "--user=ibcmd-user"
assert_contains "$file_dump_run/stdout.log" "$expected_src_cf"

run_capability "$file_profile" "$file_load_run" ./scripts/platform/load-src.sh
assert_ibcmd_summary "$file_load_run/summary.json" "file-infobase"
assert_contains "$file_load_run/stdout.log" "--database-path=$tmpdir/file-ib/db"
assert_contains "$file_load_run/stdout.log" "$expected_src_cf"

run_capability "$file_profile" "$file_update_run" ./scripts/platform/update-db.sh
assert_ibcmd_summary "$file_update_run/summary.json" "file-infobase"
assert_contains "$file_update_run/stdout.log" "--database-path=$tmpdir/file-ib/db"
assert_contains "$file_update_run/stdout.log" "--force"

dbms_create_run="$tmpdir/dbms-create"
dbms_dump_run="$tmpdir/dbms-dump"
dbms_load_run="$tmpdir/dbms-load"
dbms_update_run="$tmpdir/dbms-update"

run_capability "$dbms_profile" "$dbms_create_run" ./scripts/platform/create-ib.sh
assert_ibcmd_summary "$dbms_create_run/summary.json" "dbms-infobase"
assert_jq "$dbms_create_run/summary.json" '.driver_context.topology.dbms.kind == "PostgreSQL"' "dbms-kind"
assert_jq "$dbms_create_run/summary.json" '.driver_context.topology.dbms.server == "127.0.0.1 port=5432;"' "dbms-server"
assert_jq "$dbms_create_run/summary.json" '.driver_context.topology.dbms.name == "runtime_fixture"' "dbms-name"
assert_jq "$dbms_create_run/summary.json" '.driver_context.topology.dbms.user == "db-admin"' "dbms-user"
assert_jq "$dbms_create_run/summary.json" '.driver_context.topology.dbms.password_configured == true' "dbms-password-configured"
assert_contains "$dbms_create_run/stdout.log" "--data=$tmpdir/dbms-server"
assert_contains "$dbms_create_run/stdout.log" "--dbms=PostgreSQL"
assert_contains "$dbms_create_run/stdout.log" "--db-server=127.0.0.1 port=5432;"
assert_contains "$dbms_create_run/stdout.log" "--db-name=runtime_fixture"
assert_contains "$dbms_create_run/stdout.log" "--db-user=db-admin"
assert_contains "$dbms_create_run/stdout.log" "--db-pwd=dbms-secret"
assert_not_contains "$dbms_create_run/stdout.log" "--user=ibcmd-user"
assert_not_contains "$dbms_create_run/stdout.log" "--password=ibcmd-secret"

run_capability "$dbms_profile" "$dbms_dump_run" ./scripts/platform/dump-src.sh
assert_ibcmd_summary "$dbms_dump_run/summary.json" "dbms-infobase"
assert_contains "$dbms_dump_run/stdout.log" "--dbms=PostgreSQL"
assert_contains "$dbms_dump_run/stdout.log" "--db-server=127.0.0.1 port=5432;"
assert_contains "$dbms_dump_run/stdout.log" "--db-name=runtime_fixture"
assert_contains "$dbms_dump_run/stdout.log" "--db-user=db-admin"
assert_contains "$dbms_dump_run/stdout.log" "--db-pwd=dbms-secret"
assert_contains "$dbms_dump_run/stdout.log" "--user=ibcmd-user"
assert_contains "$dbms_dump_run/stdout.log" "--password=ibcmd-secret"
assert_contains "$dbms_dump_run/stdout.log" "$expected_src_cf"

run_capability "$dbms_profile" "$dbms_load_run" ./scripts/platform/load-src.sh
assert_ibcmd_summary "$dbms_load_run/summary.json" "dbms-infobase"
assert_contains "$dbms_load_run/stdout.log" "--dbms=PostgreSQL"
assert_contains "$dbms_load_run/stdout.log" "--db-pwd=dbms-secret"
assert_contains "$dbms_load_run/stdout.log" "--user=ibcmd-user"
assert_contains "$dbms_load_run/stdout.log" "$expected_src_cf"

run_capability "$dbms_profile" "$dbms_update_run" ./scripts/platform/update-db.sh
assert_ibcmd_summary "$dbms_update_run/summary.json" "dbms-infobase"
assert_contains "$dbms_update_run/stdout.log" "--dbms=PostgreSQL"
assert_contains "$dbms_update_run/stdout.log" "--db-pwd=dbms-secret"
assert_contains "$dbms_update_run/stdout.log" "--force"

if grep -Fq -- "ibcmd-secret" "$dbms_create_run/summary.json"; then
  printf 'summary.json must not contain resolved infobase secrets\n' >&2
  cat "$dbms_create_run/summary.json" >&2
  exit 1
fi

if grep -Fq -- "dbms-secret" "$dbms_create_run/summary.json"; then
  printf 'summary.json must not contain resolved dbms secrets\n' >&2
  cat "$dbms_create_run/summary.json" >&2
  exit 1
fi

mixed_create_run="$tmpdir/mixed-create"
mixed_dump_run="$tmpdir/mixed-dump"
mixed_load_run="$tmpdir/mixed-load"
mixed_update_run="$tmpdir/mixed-update"

run_capability "$mixed_profile" "$mixed_create_run" ./scripts/platform/create-ib.sh
assert_jq "$mixed_create_run/summary.json" '.driver == "designer"' "mixed-create-driver"
assert_contains "$mixed_create_run/stdout.log" "CREATEINFOBASE"

run_capability "$mixed_profile" "$mixed_dump_run" ./scripts/platform/dump-src.sh
assert_jq "$mixed_dump_run/summary.json" '.driver == "designer"' "mixed-dump-driver"
assert_contains "$mixed_dump_run/stdout.log" "/DumpConfigToFiles"

run_capability "$mixed_profile" "$mixed_load_run" ./scripts/platform/load-src.sh
assert_ibcmd_summary "$mixed_load_run/summary.json" "file-infobase"
assert_contains "$mixed_load_run/stdout.log" "config"
assert_contains "$mixed_load_run/stdout.log" "import"
assert_contains "$mixed_load_run/stdout.log" "--database-path=$tmpdir/mixed-file-ib/db"

run_capability "$mixed_profile" "$mixed_update_run" ./scripts/platform/update-db.sh
assert_jq "$mixed_update_run/summary.json" '.driver == "designer"' "mixed-update-driver"
assert_contains "$mixed_update_run/stdout.log" "/UpdateDBCfg"
