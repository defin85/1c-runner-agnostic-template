#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"

export ONEC_IBCMD_PASSWORD="ibcmd-validation-secret"
export ONEC_DBMS_PASSWORD="dbms-validation-secret"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'designer-invoked\n'
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

assert_stderr_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected stderr text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_stdout_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected stdout text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_stdout_not_contains() {
  local file="$1"
  local unexpected="$2"

  if grep -Fq -- "$unexpected" "$file"; then
    printf 'unexpected stdout text found: %s\n' "$unexpected" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_expect_failure() {
  local stderr_path="$1"
  shift

  set +e
  (
    cd "$SOURCE_ROOT"
    "$@"
  ) >/dev/null 2>"$stderr_path"
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf 'command unexpectedly succeeded\n' >&2
    cat "$stderr_path" >&2
    exit 1
  fi
}

run_expect_success() {
  local stdout_path="$1"
  local stderr_path="$2"
  shift 2

  (
    cd "$SOURCE_ROOT"
    "$@"
  ) >"$stdout_path" 2>"$stderr_path"
}

write_profile() {
  local profile_path="$1"
  local profile_name="$2"
  local adapter="$3"
  local runtime_mode="$4"
  local topology_json="$5"
  local capabilities_json="$6"
  local include_auth="$7"
  local server_access_mode="$8"
  local data_dir="${9:-}"

  [ -n "$data_dir" ] || {
    printf 'write_profile requires data_dir\n' >&2
    exit 1
  }

  jq -n \
    --arg profile_name "$profile_name" \
    --arg adapter "$adapter" \
    --arg fake_designer "$fake_designer" \
    --arg fake_ibcmd "$fake_ibcmd" \
    --arg runtime_mode "$runtime_mode" \
    --arg server_access_mode "$server_access_mode" \
    --arg data_dir "$data_dir" \
    --argjson topology "$topology_json" \
    --argjson capabilities "$capabilities_json" \
    --argjson include_auth "$include_auth" \
    '{
      schemaVersion: 2,
      profileName: $profile_name,
      runnerAdapter: $adapter,
      platform: {
        binaryPath: $fake_designer,
        ibcmdPath: $fake_ibcmd
      },
      infobase: {
        mode: "file",
        filePath: "/var/tmp/validation-fixture",
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
            mode: $server_access_mode,
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

dump_src_capability_json='{
  "dumpSrc": {"driver": "ibcmd"},
  "xunit": {"command": ["bash", "-lc", "printf '\''xunit-ok\\n'\''"]},
  "bdd": {"command": ["bash", "-lc", "printf '\''bdd-ok\\n'\''"]},
  "smoke": {"command": ["bash", "-lc", "printf '\''smoke-ok\\n'\''"]}
}'

create_only_capability_json='{
  "createIb": {"driver": "ibcmd"},
  "xunit": {"command": ["bash", "-lc", "printf '\''xunit-ok\\n'\''"]},
  "bdd": {"command": ["bash", "-lc", "printf '\''bdd-ok\\n'\''"]},
  "smoke": {"command": ["bash", "-lc", "printf '\''smoke-ok\\n'\''"]}
}'

designer_partial_profile="$tmpdir/designer-partial.json"
cat >"$designer_partial_profile" <<EOF
{
  "schemaVersion": 2,
  "profileName": "designer-partial",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/designer-partial",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "designer",
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

profile_driver_and_command="$tmpdir/profile-driver-and-command.json"
write_profile \
  "$profile_driver_and_command" \
  "driver-and-command" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  '{"dumpSrc":{"driver":"ibcmd","command":["bash","-lc","printf '\''bad-mix\\n'\''"]},"xunit":{"command":["bash","-lc","printf '\''xunit-ok\\n'\''"]},"bdd":{"command":["bash","-lc","printf '\''bdd-ok\\n'\''"]},"smoke":{"command":["bash","-lc","printf '\''smoke-ok\\n'\''"]}}' \
  true \
  "data-dir" \
  "$tmpdir/driver-and-command-server"

stderr_driver_and_command="$tmpdir/driver-and-command.stderr"
run_expect_failure \
  "$stderr_driver_and_command" \
  ./scripts/platform/dump-src.sh --profile "$profile_driver_and_command"
assert_stderr_contains "$stderr_driver_and_command" "must not define both driver and command"

profile_remote_adapter="$tmpdir/profile-remote-adapter.json"
write_profile \
  "$profile_remote_adapter" \
  "remote-adapter" \
  "remote-windows" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/remote-server"

stderr_remote_adapter="$tmpdir/remote-adapter.stderr"
run_expect_failure \
  "$stderr_remote_adapter" \
  ./scripts/platform/dump-src.sh --profile "$profile_remote_adapter"
assert_stderr_contains "$stderr_remote_adapter" "ibcmd driver is supported only with runnerAdapter=direct-platform"

stderr_designer_partial="$tmpdir/designer-partial.stderr"
run_expect_failure \
  "$stderr_designer_partial" \
  ./scripts/platform/load-src.sh --profile "$designer_partial_profile" --files "Catalogs/Items.xml"
assert_stderr_contains "$stderr_designer_partial" "partial load-src is supported only for ibcmd driver"

profile_missing_ibcmd_path="$tmpdir/profile-missing-ibcmd-path.json"
write_profile \
  "$profile_missing_ibcmd_path" \
  "missing-ibcmd-path" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/missing-path-server"
jq 'del(.platform.ibcmdPath)' "$profile_missing_ibcmd_path" >"$profile_missing_ibcmd_path.tmp"
mv "$profile_missing_ibcmd_path.tmp" "$profile_missing_ibcmd_path"

stderr_missing_ibcmd_path="$tmpdir/missing-ibcmd-path.stderr"
run_expect_failure \
  "$stderr_missing_ibcmd_path" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_path"
assert_stderr_contains "$stderr_missing_ibcmd_path" "platform.ibcmdPath"

profile_missing_runtime_mode="$tmpdir/profile-missing-runtime-mode.json"
write_profile \
  "$profile_missing_runtime_mode" \
  "missing-runtime-mode" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/missing-runtime-mode-server"
jq 'del(.ibcmd.runtimeMode)' "$profile_missing_runtime_mode" >"$profile_missing_runtime_mode.tmp"
mv "$profile_missing_runtime_mode.tmp" "$profile_missing_runtime_mode"

stderr_missing_runtime_mode="$tmpdir/missing-runtime-mode.stderr"
run_expect_failure \
  "$stderr_missing_runtime_mode" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_runtime_mode"
assert_stderr_contains "$stderr_missing_runtime_mode" "ibcmd.runtimeMode"

profile_missing_server_access_mode="$tmpdir/profile-missing-server-access-mode.json"
write_profile \
  "$profile_missing_server_access_mode" \
  "missing-server-access-mode" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/missing-server-access-mode-server"
jq 'del(.ibcmd.serverAccess.mode)' "$profile_missing_server_access_mode" >"$profile_missing_server_access_mode.tmp"
mv "$profile_missing_server_access_mode.tmp" "$profile_missing_server_access_mode"

stderr_missing_server_access_mode="$tmpdir/missing-server-access-mode.stderr"
run_expect_failure \
  "$stderr_missing_server_access_mode" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_server_access_mode"
assert_stderr_contains "$stderr_missing_server_access_mode" "ibcmd.serverAccess.mode"

profile_bad_server_access_mode="$tmpdir/profile-bad-server-access-mode.json"
write_profile \
  "$profile_bad_server_access_mode" \
  "bad-server-access-mode" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "remote" \
  "$tmpdir/bad-server-access-mode-server"

stderr_bad_server_access_mode="$tmpdir/bad-server-access-mode.stderr"
run_expect_failure \
  "$stderr_bad_server_access_mode" \
  ./scripts/platform/dump-src.sh --profile "$profile_bad_server_access_mode"
assert_stderr_contains "$stderr_bad_server_access_mode" "ibcmd.serverAccess.mode=remote is unsupported in the current release; use data-dir"

profile_missing_data_dir="$tmpdir/profile-missing-data-dir.json"
write_profile \
  "$profile_missing_data_dir" \
  "missing-data-dir" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/missing-data-dir-server"
jq 'del(.ibcmd.serverAccess.dataDir)' "$profile_missing_data_dir" >"$profile_missing_data_dir.tmp"
mv "$profile_missing_data_dir.tmp" "$profile_missing_data_dir"

stderr_missing_data_dir="$tmpdir/missing-data-dir.stderr"
run_expect_failure \
  "$stderr_missing_data_dir" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_data_dir"
assert_stderr_contains "$stderr_missing_data_dir" "ibcmd.serverAccess.dataDir"

profile_missing_standalone_db_path="$tmpdir/profile-missing-standalone-db-path.json"
write_profile \
  "$profile_missing_standalone_db_path" \
  "missing-standalone-db-path" \
  "direct-platform" \
  "standalone-server" \
  '{"standalone":{}}' \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/standalone-server"

stderr_missing_standalone_db_path="$tmpdir/missing-standalone-db-path.stderr"
run_expect_failure \
  "$stderr_missing_standalone_db_path" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_standalone_db_path"
assert_stderr_contains "$stderr_missing_standalone_db_path" "ibcmd.standalone.databasePath"

profile_missing_file_db_path="$tmpdir/profile-missing-file-db-path.json"
write_profile \
  "$profile_missing_file_db_path" \
  "missing-file-db-path" \
  "direct-platform" \
  "file-infobase" \
  '{"fileInfobase":{}}' \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/file-server"

stderr_missing_file_db_path="$tmpdir/missing-file-db-path.stderr"
run_expect_failure \
  "$stderr_missing_file_db_path" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_file_db_path"
assert_stderr_contains "$stderr_missing_file_db_path" "ibcmd.fileInfobase.databasePath"

profile_missing_dbms_kind="$tmpdir/profile-missing-dbms-kind.json"
write_profile \
  "$profile_missing_dbms_kind" \
  "missing-dbms-kind" \
  "direct-platform" \
  "dbms-infobase" \
  "{\"dbmsInfobase\":{\"server\":\"127.0.0.1 port=5432;\",\"name\":\"runtime_fixture\",\"user\":\"db-admin\",\"passwordEnv\":\"ONEC_DBMS_PASSWORD\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/dbms-server"

stderr_missing_dbms_kind="$tmpdir/missing-dbms-kind.stderr"
run_expect_failure \
  "$stderr_missing_dbms_kind" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_dbms_kind"
assert_stderr_contains "$stderr_missing_dbms_kind" "ibcmd.dbmsInfobase.kind"

profile_missing_dbms_password_env="$tmpdir/profile-missing-dbms-password-env.json"
write_profile \
  "$profile_missing_dbms_password_env" \
  "missing-dbms-password-env" \
  "direct-platform" \
  "dbms-infobase" \
  "{\"dbmsInfobase\":{\"kind\":\"PostgreSQL\",\"server\":\"127.0.0.1 port=5432;\",\"name\":\"runtime_fixture\",\"user\":\"db-admin\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/dbms-server"

stderr_missing_dbms_password_env="$tmpdir/missing-dbms-password-env.stderr"
run_expect_failure \
  "$stderr_missing_dbms_password_env" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_dbms_password_env"
assert_stderr_contains "$stderr_missing_dbms_password_env" "ibcmd.dbmsInfobase.passwordEnv"

profile_missing_ibcmd_auth_user="$tmpdir/profile-missing-ibcmd-auth-user.json"
write_profile \
  "$profile_missing_ibcmd_auth_user" \
  "missing-ibcmd-auth-user" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/file-server"
jq 'del(.ibcmd.auth.user)' "$profile_missing_ibcmd_auth_user" >"$profile_missing_ibcmd_auth_user.tmp"
mv "$profile_missing_ibcmd_auth_user.tmp" "$profile_missing_ibcmd_auth_user"

stderr_missing_ibcmd_auth_user="$tmpdir/missing-ibcmd-auth-user.stderr"
run_expect_failure \
  "$stderr_missing_ibcmd_auth_user" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_auth_user"
assert_stderr_contains "$stderr_missing_ibcmd_auth_user" "ibcmd.auth.user"

profile_missing_ibcmd_auth_password_env="$tmpdir/profile-missing-ibcmd-auth-password-env.json"
write_profile \
  "$profile_missing_ibcmd_auth_password_env" \
  "missing-ibcmd-auth-password-env" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  "$dump_src_capability_json" \
  true \
  "data-dir" \
  "$tmpdir/file-server"
jq 'del(.ibcmd.auth.passwordEnv)' "$profile_missing_ibcmd_auth_password_env" >"$profile_missing_ibcmd_auth_password_env.tmp"
mv "$profile_missing_ibcmd_auth_password_env.tmp" "$profile_missing_ibcmd_auth_password_env"

stderr_missing_ibcmd_auth_password_env="$tmpdir/missing-ibcmd-auth-password-env.stderr"
run_expect_failure \
  "$stderr_missing_ibcmd_auth_password_env" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_auth_password_env"
assert_stderr_contains "$stderr_missing_ibcmd_auth_password_env" "ibcmd.auth.passwordEnv"

profile_path_escape="$tmpdir/profile-path-escape.json"
write_profile \
  "$profile_path_escape" \
  "path-escape" \
  "direct-platform" \
  "file-infobase" \
  "{\"fileInfobase\":{\"databasePath\":\"$tmpdir/file-ib/db\"}}" \
  '{"loadSrc":{"driver":"ibcmd","sourceDir":"./src/cf"},"xunit":{"command":["bash","-lc","printf '\''xunit-ok\\n'\''"]},"bdd":{"command":["bash","-lc","printf '\''bdd-ok\\n'\''"]},"smoke":{"command":["bash","-lc","printf '\''smoke-ok\\n'\''"]}}' \
  true \
  "data-dir" \
  "$tmpdir/file-server"

stderr_path_escape="$tmpdir/path-escape.stderr"
run_expect_failure \
  "$stderr_path_escape" \
  ./scripts/platform/load-src.sh --profile "$profile_path_escape" --files "../Catalogs/Items.xml"
assert_stderr_contains "$stderr_path_escape" "must stay within the configured source tree"

profile_create_only_dbms="$tmpdir/profile-create-only-dbms.json"
write_profile \
  "$profile_create_only_dbms" \
  "create-only-dbms" \
  "direct-platform" \
  "dbms-infobase" \
  "{\"dbmsInfobase\":{\"kind\":\"PostgreSQL\",\"server\":\"127.0.0.1 port=5432;\",\"name\":\"runtime_fixture\",\"user\":\"db-admin\",\"passwordEnv\":\"ONEC_DBMS_PASSWORD\"}}" \
  "$create_only_capability_json" \
  false \
  "data-dir" \
  "$tmpdir/create-only-dbms-server"

create_only_run_root="$tmpdir/create-only-dbms-run"
(
  cd "$SOURCE_ROOT"
  ./scripts/platform/create-ib.sh --profile "$profile_create_only_dbms" --run-root "$create_only_run_root" >/dev/null
)
assert_stdout_contains "$create_only_run_root/stdout.log" "--dbms=PostgreSQL"
assert_stdout_contains "$create_only_run_root/stdout.log" "--db-pwd=dbms-validation-secret"
assert_stdout_not_contains "$create_only_run_root/stdout.log" "--user=ibcmd-user"
assert_stdout_not_contains "$create_only_run_root/stdout.log" "--password=ibcmd-validation-secret"
