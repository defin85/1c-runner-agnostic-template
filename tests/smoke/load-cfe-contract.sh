#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"
dry_run_root="$tmpdir/run-dry"
selected_run_root="$tmpdir/run-selected"
failure_run_root="$tmpdir/run-failure"
fake_ibcmd="$tmpdir/ibcmd"
data_dir="$tmpdir/ibcmd-data"
database_path="$tmpdir/load-cfe-fixture-db"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p "$fixture_root/env" "$fixture_root/src/cfe/FixtureCommon" "$fixture_root/src/cfe/FixtureLogistics" "$data_dir"

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

step=""
extension=""

for arg in "$@"; do
  printf '%s\n' "$arg"
  case "$arg" in
    import|check|apply)
      step="$arg"
      ;;
    --extension=*)
      extension="${arg#--extension=}"
      ;;
  esac
done

if [ "${LOAD_CFE_FAIL_EXTENSION:-}" = "$extension" ] && [ "${LOAD_CFE_FAIL_STEP:-}" = "$step" ]; then
  exit "${LOAD_CFE_FAIL_EXIT_CODE:-31}"
fi
EOF

chmod +x "$fake_ibcmd"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "load-cfe-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/load-cfe-fixture",
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
      "dataDir": "$data_dir"
    },
    "fileInfobase": {
      "databasePath": "$database_path"
    }
  },
  "capabilities": {}
}
EOF

printf '<extension name="FixtureCommon" />\n' >"$fixture_root/src/cfe/FixtureCommon/Configuration.xml"
printf '<extension name="FixtureLogistics" />\n' >"$fixture_root/src/cfe/FixtureLogistics/Configuration.xml"

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
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

(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --run-root "$run_root" >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success"' "wrapper-status"
assert_jq "$run_root/summary.json" '.capability.id == "load-cfe"' "wrapper-capability"
assert_jq "$run_root/summary.json" '.driver == "ibcmd"' "wrapper-driver"
assert_jq "$run_root/summary.json" '.execution.mode == "ibcmd-sequential-extension-import-check-apply"' "wrapper-mode"
assert_jq "$run_root/summary.json" '(.extension_source.selected_names | sort) == ["FixtureCommon", "FixtureLogistics"]' "wrapper-extensions"
assert_jq "$run_root/summary.json" '.failure == null' "wrapper-no-failure"
assert_jq "$run_root/summary.json" '[.results[] | select(.status == "success")] | length == 2' "wrapper-results-success"
assert_jq "$run_root/extensions/FixtureCommon/summary.json" '.status == "success"' "delanscommon-summary-status"
assert_jq "$run_root/extensions/FixtureCommon/summary.json" '[.steps[] | select(.id == "import" and .status == "success")] | length == 1' "delanscommon-import-step"
assert_jq "$run_root/extensions/FixtureCommon/summary.json" '[.steps[] | select(.id == "check" and .status == "success")] | length == 1' "delanscommon-check-step"
assert_jq "$run_root/extensions/FixtureCommon/summary.json" '[.steps[] | select(.id == "apply" and .status == "success")] | length == 1' "delanscommon-apply-step"
assert_contains "$run_root/extensions/FixtureCommon/import.command.txt" "config"
assert_contains "$run_root/extensions/FixtureCommon/import.command.txt" "import"
assert_contains "$run_root/extensions/FixtureCommon/import.command.txt" "--extension=FixtureCommon"
assert_contains "$run_root/extensions/FixtureCommon/import.command.txt" "--database-path=$database_path"
assert_contains "$run_root/extensions/FixtureCommon/import.command.txt" "--data=$data_dir"
assert_contains "$run_root/extensions/FixtureCommon/check.command.txt" "--force"
assert_contains "$run_root/extensions/FixtureCommon/apply.command.txt" "--force"
assert_contains "$run_root/extensions/FixtureCommon/import.stdout.log" "--extension=FixtureCommon"
assert_contains "$run_root/extensions/FixtureLogistics/apply.stdout.log" "--extension=FixtureLogistics"

(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --run-root "$dry_run_root" --dry-run >/dev/null
)

assert_jq "$dry_run_root/summary.json" '.status == "dry-run"' "wrapper-dry-run-status"
assert_jq "$dry_run_root/summary.json" '[.results[] | select(.status == "dry-run")] | length == 2' "wrapper-dry-run-results"
assert_jq "$dry_run_root/extensions/FixtureCommon/summary.json" '[.steps[] | select(.status == "dry-run")] | length == 3' "dry-run-steps"

(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --run-root "$selected_run_root" --extension FixtureLogistics >/dev/null
)

assert_jq "$selected_run_root/summary.json" '.status == "success"' "selected-wrapper-status"
assert_jq "$selected_run_root/summary.json" '.extension_source.selected_names == ["FixtureLogistics"]' "selected-wrapper-extension"
assert_jq "$selected_run_root/summary.json" '[.results[] | select(.status == "success")] | length == 1' "selected-wrapper-result-count"
[ ! -d "$selected_run_root/extensions/FixtureCommon" ] || {
  printf 'unexpected unselected extension run root: %s\n' "$selected_run_root/extensions/FixtureCommon" >&2
  exit 1
}
assert_contains "$selected_run_root/extensions/FixtureLogistics/import.stdout.log" "--extension=FixtureLogistics"

set +e
(
  cd "$fixture_root"
  LOAD_CFE_FAIL_EXTENSION="FixtureCommon" \
  LOAD_CFE_FAIL_STEP="apply" \
  LOAD_CFE_FAIL_EXIT_CODE="31" \
  ./scripts/platform/load-cfe.sh --profile env/local.json --run-root "$failure_run_root" >/dev/null 2>"$tmpdir/load-cfe-failure.stderr"
)
status=$?
set -e

if [ "$status" -ne 31 ]; then
  printf 'unexpected exit code for load-cfe failure: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$failure_run_root/summary.json" '.status == "failed"' "wrapper-failure-status"
assert_jq "$failure_run_root/summary.json" '.failure.classification == "extension-sync failed"' "wrapper-failure-classification"
assert_jq "$failure_run_root/summary.json" '.failed_extension == "FixtureCommon"' "wrapper-failed-extension"
assert_jq "$failure_run_root/summary.json" '.failed_step == "apply"' "wrapper-failed-step"
assert_jq "$failure_run_root/summary.json" '.extension_source.failed_names == ["FixtureCommon"]' "wrapper-failed-names"
assert_jq "$failure_run_root/extensions/FixtureCommon/summary.json" '.status == "failed"' "failed-extension-status"
assert_jq "$failure_run_root/extensions/FixtureCommon/summary.json" '.failed_step == "apply"' "failed-extension-step"
assert_jq "$failure_run_root/summary.json" '[.results[] | select(.extension_name == "FixtureLogistics" and .status == null)] | length == 1' "second-extension-not-run"
