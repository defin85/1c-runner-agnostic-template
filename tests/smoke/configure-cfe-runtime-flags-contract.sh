#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"
dry_run_root="$tmpdir/run-dry"
failure_run_root="$tmpdir/run-failure"
fake_ibcmd="$tmpdir/ibcmd"
invocation_log="$tmpdir/ibcmd.invocations.log"
data_dir="$tmpdir/ibcmd-data"

mkdir -p "$fixture_root" "$data_dir"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fixture_root/env" \
  "$fixture_root/src/cfe/FixtureUITests" \
  "$fixture_root/src/cfe/FixtureCommon" \
  "$fixture_root/src/cfe/FixtureLogistics" \
  "$fixture_root/src/cfe/FixtureSupport" \
  "$fixture_root/src/cfe/MCP_Сервер"

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

extension=""
for arg in "$@"; do
  case "$arg" in
    --name=*)
      extension="${arg#--name=}"
      ;;
  esac

  case "$arg" in
    --password=*|--db-pwd=*)
      log_arg="${arg%%=*}=__SECRET_SEEN__"
      ;;
    *)
      log_arg="$arg"
      ;;
  esac

  printf '%s\n' "$log_arg"
  printf '%s\n' "$log_arg" >>"$CONFIGURE_FLAGS_INVOCATION_LOG"
done
printf '%s\n' '---' >>"$CONFIGURE_FLAGS_INVOCATION_LOG"

if [ "${CONFIGURE_FLAGS_FAIL_EXTENSION:-}" = "$extension" ]; then
  exit "${CONFIGURE_FLAGS_FAIL_EXIT_CODE:-31}"
fi
EOF

chmod +x "$fake_ibcmd"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "configure-cfe-runtime-flags-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "server",
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
  "capabilities": {}
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

assert_file_equals() {
  local file="$1"
  local expected="$2"
  local diff_file="$tmpdir/assert-file-equals.diff"

  if ! diff -u <(printf '%s' "$expected") "$file" >"$diff_file"; then
    printf 'unexpected file contents: %s\n' "$file" >&2
    cat "$diff_file" >&2
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

: >"$invocation_log"
(
  cd "$fixture_root"
  TEST_IB_PASSWORD="ib-secret" \
  TEST_DB_PASSWORD="db-secret" \
  CONFIGURE_FLAGS_INVOCATION_LOG="$invocation_log" \
  ./scripts/platform/configure-cfe-runtime-flags.sh --profile env/local.json --run-root "$run_root" >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success"' "wrapper-status"
assert_jq "$run_root/summary.json" '.capability.id == "configure-cfe-runtime-flags"' "wrapper-capability"
assert_jq "$run_root/summary.json" '.requested_flags.safe_mode == "no"' "wrapper-safe-mode"
assert_jq "$run_root/summary.json" '.requested_flags.unsafe_action_protection == "no"' "wrapper-unsafe-action-protection"
assert_jq "$run_root/summary.json" '(.extension_source.selected_names | sort) == ["FixtureCommon", "FixtureLogistics", "FixtureSupport", "FixtureUITests", "MCP_Сервер"]' "wrapper-selected-defaults"
assert_jq "$run_root/summary.json" '[.results[] | select(.status == "success")] | length == 5' "wrapper-results-success"
assert_jq "$run_root/summary.json" '.failure == null' "wrapper-no-failure"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "infobase"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "extension"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "update"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--name=FixtureCommon"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--safe-mode=no"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--unsafe-action-protection=no"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--data=$data_dir"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--dbms=PostgreSQL"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--db-server=fixture-db\\ port=5432"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--db-name=fixture_db"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--db-user=postgres"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--user=ib-user"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--password=__REDACTED_SECRET__"
assert_contains "$run_root/extensions/FixtureCommon/update.command.txt" "--db-pwd=__REDACTED_SECRET__"
assert_not_contains "$run_root/extensions/FixtureCommon/update.command.txt" "ib-secret"
assert_not_contains "$run_root/extensions/FixtureCommon/update.command.txt" "db-secret"
assert_contains "$run_root/extensions/FixtureCommon/update.stdout.log" "--password=__SECRET_SEEN__"
assert_contains "$run_root/extensions/FixtureCommon/update.stdout.log" "--db-pwd=__SECRET_SEEN__"
assert_not_contains "$run_root/extensions/FixtureCommon/update.stdout.log" "ib-secret"
assert_not_contains "$run_root/extensions/FixtureCommon/update.stdout.log" "db-secret"

: >"$invocation_log"
(
  cd "$fixture_root"
  CONFIGURE_FLAGS_INVOCATION_LOG="$invocation_log" \
  ./scripts/platform/configure-cfe-runtime-flags.sh --profile env/local.json --run-root "$dry_run_root" --dry-run >/dev/null
)

assert_file_equals "$invocation_log" ""
assert_jq "$dry_run_root/summary.json" '.status == "dry-run"' "wrapper-dry-run-status"
assert_jq "$dry_run_root/summary.json" '[.results[] | select(.status == "dry-run")] | length == 5' "wrapper-dry-run-results"
assert_contains "$dry_run_root/extensions/FixtureCommon/update.command.txt" "--password=__REDACTED_SECRET__"
assert_contains "$dry_run_root/extensions/FixtureCommon/update.command.txt" "--db-pwd=__REDACTED_SECRET__"

: >"$invocation_log"
set +e
(
  cd "$fixture_root"
  TEST_IB_PASSWORD="ib-secret" \
  TEST_DB_PASSWORD="db-secret" \
  CONFIGURE_FLAGS_INVOCATION_LOG="$invocation_log" \
  CONFIGURE_FLAGS_FAIL_EXTENSION="FixtureLogistics" \
  CONFIGURE_FLAGS_FAIL_EXIT_CODE="31" \
  ./scripts/platform/configure-cfe-runtime-flags.sh --profile env/local.json --run-root "$failure_run_root" >/dev/null 2>"$tmpdir/configure-flags-failure.stderr"
)
status=$?
set -e

if [ "$status" -ne 31 ]; then
  printf 'unexpected exit code for configure-cfe-runtime-flags failure: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$failure_run_root/summary.json" '.status == "failed"' "wrapper-failure-status"
assert_jq "$failure_run_root/summary.json" '.exit_code == 31' "wrapper-failure-exit-code"
assert_jq "$failure_run_root/summary.json" '.failed_extension == "FixtureLogistics"' "wrapper-failed-extension"
assert_jq "$failure_run_root/summary.json" '.failure.classification == "extension-runtime-flags failed"' "wrapper-failure-classification"
assert_jq "$failure_run_root/extensions/FixtureLogistics/summary.json" '.status == "failed"' "failed-extension-status"
assert_jq "$failure_run_root/summary.json" '[.results[] | select(.extension_name == "FixtureSupport" and .status == null)] | length == 1' "remaining-extension-not-run"
