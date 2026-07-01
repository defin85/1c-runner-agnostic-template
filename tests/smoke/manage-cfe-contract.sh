#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_list="$tmpdir/run-list"
run_delete="$tmpdir/run-delete"
fake_ibcmd="$tmpdir/ibcmd"
invocation_log="$tmpdir/ibcmd.invocations.log"
data_dir="$tmpdir/ibcmd-data"

mkdir -p "$fixture_root" "$data_dir"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p "$fixture_root/env" "$fixture_root/automation/context"

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  case "$arg" in
    --password=*|--db-pwd=*)
      arg="${arg%%=*}=__SECRET_SEEN__"
      ;;
  esac
  printf '%s\n' "$arg"
  printf '%s\n' "$arg" >>"$MANAGE_CFE_INVOCATION_LOG"
done
printf '%s\n' '---' >>"$MANAGE_CFE_INVOCATION_LOG"
EOF

chmod +x "$fake_ibcmd"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "manage-cfe-fixture",
  "runnerAdapter": "direct-platform",
  "target": {
    "id": "fixture-target"
  },
  "platform": {
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "client-server",
    "server": "fixture-server",
    "ref": "fixture-ref",
    "auth": {
      "mode": "user-password",
      "user": "ib-user",
      "passwordEnv": "TEST_IB_PASSWORD"
    }
  },
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$data_dir"
    },
    "auth": {
      "user": "ib-user",
      "passwordEnv": "TEST_IB_PASSWORD"
    },
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "fixture-db port=5432",
      "name": "fixture_db",
      "user": "postgres",
      "passwordEnv": "TEST_DB_PASSWORD"
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf"
    }
  }
}
EOF

cat >"$fixture_root/automation/context/target-matrix.json" <<'EOF'
{
  "schemaVersion": 1,
  "targets": [
    {
      "id": "fixture-target",
      "role": "test",
      "server": "fixture-server",
      "ref": "fixture-ref",
      "sourcePath": "src/cf"
    }
  ],
  "extensionMatrix": {}
}
EOF

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"

  if grep -Fq -- "$unexpected" "$file"; then
    printf 'unexpected text found: %s\n' "$unexpected" >&2
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

: >"$invocation_log"
(
  cd "$fixture_root"
  TEST_IB_PASSWORD="ib-secret" \
  TEST_DB_PASSWORD="db-secret" \
  MANAGE_CFE_INVOCATION_LOG="$invocation_log" \
  ./scripts/platform/manage-cfe.sh list --profile env/local.json --target fixture-target --run-root "$run_list" >/dev/null
)

assert_jq "$run_list/summary.json" '.status == "success" and .action == "list" and .target_id == "fixture-target"' "list-summary"
assert_contains "$run_list/command.txt" "config"
assert_contains "$run_list/command.txt" "extension"
assert_contains "$run_list/command.txt" "list"
assert_contains "$run_list/command.txt" "--data=$data_dir"
assert_contains "$run_list/command.txt" "--dbms=PostgreSQL"
assert_contains "$run_list/command.txt" "--db-server=fixture-db\\ port=5432"
assert_contains "$run_list/command.txt" "--db-name=fixture_db"
assert_contains "$run_list/command.txt" "--db-user=postgres"
assert_contains "$run_list/command.txt" "--user=ib-user"
assert_contains "$run_list/command.txt" "--password=__REDACTED_SECRET__"
assert_contains "$run_list/command.txt" "--db-pwd=__REDACTED_SECRET__"
assert_not_contains "$run_list/command.txt" "ib-secret"
assert_not_contains "$run_list/command.txt" "db-secret"

(
  cd "$fixture_root"
  TEST_IB_PASSWORD="ib-secret" \
  TEST_DB_PASSWORD="db-secret" \
  MANAGE_CFE_INVOCATION_LOG="$invocation_log" \
  ./scripts/platform/manage-cfe.sh delete --profile env/local.json --target fixture-target --extension FixtureExtension --run-root "$run_delete" >/dev/null
)

assert_jq "$run_delete/summary.json" '.status == "success" and .action == "delete" and .extension_name == "FixtureExtension"' "delete-summary"
assert_contains "$run_delete/command.txt" "delete"
assert_contains "$run_delete/command.txt" "--name=FixtureExtension"
assert_contains "$run_delete/stdout.log" "--password=__SECRET_SEEN__"
assert_contains "$run_delete/stdout.log" "--db-pwd=__SECRET_SEEN__"

if ./scripts/platform/manage-cfe.sh delete --profile "$fixture_root/env/local.json" --dry-run >/dev/null 2>"$tmpdir/missing-extension.stderr"; then
  printf 'delete without --extension unexpectedly succeeded\n' >&2
  exit 1
fi
assert_contains "$tmpdir/missing-extension.stderr" "delete requires --extension"
