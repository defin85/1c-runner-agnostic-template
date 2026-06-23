#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"
single_root="$tmpdir/run-single"
dry_run_root="$tmpdir/run-dry"
fake_binary="$tmpdir/1cv8"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p "$fixture_root/env" "$fixture_root/src/cfe/FixtureCommon" "$fixture_root/src/cfe/FixtureLogistics"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

extension_name=""
out_log=""
previous=""
for arg in "$@"; do
  printf '%s\n' "$arg"
  if [ "$previous" = "/Out" ]; then
    out_log="$arg"
  fi
  if [ "$previous" = "-Extension" ]; then
    extension_name="$arg"
  fi
  previous="$arg"
done

if [ -n "$out_log" ]; then
  if [ "${APPLICABILITY_DIAGNOSTIC_EXTENSION_NAME:-}" = "$extension_name" ]; then
    printf '%s\n' "${APPLICABILITY_DIAGNOSTIC_TEXT:-$extension_name warning}" >"$out_log"
  else
    printf 'No errors found\n' >"$out_log"
  fi
fi

if [ "${FAIL_EXTENSION_NAME:-}" = "$extension_name" ]; then
  exit 23
fi
EOF

chmod +x "$fake_binary"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "check-cfe-applicability-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/check-cfe-applicability-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
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

warning_text='FixtureLogistics (2.0.5.35): Cannot find method "Подключаемый_ПроверитьВыполнениеЗаданияПоПолучениюДокументовНаОсновании" specified in the annotation of method "ESПодключаемый_ПроверитьВыполнениеЗаданияПоПолучениюДокументовНаОсновании".'

set +e
(
  cd "$fixture_root"
  APPLICABILITY_DIAGNOSTIC_EXTENSION_NAME="FixtureLogistics" \
  APPLICABILITY_DIAGNOSTIC_TEXT="$warning_text" \
  ./scripts/platform/check-cfe-applicability.sh --profile env/local.json --run-root "$run_root" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 1 ]; then
  printf 'unexpected exit code for applicability diagnostics failure: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$run_root/summary.json" '.status == "failed"' "wrapper-status"
assert_jq "$run_root/summary.json" '.capability.id == "check-cfe-applicability"' "wrapper-capability"
assert_jq "$run_root/summary.json" '.failure.classification == "extension-applicability failed"' "wrapper-failure-classification"
assert_jq "$run_root/summary.json" '.failure.extensions == ["FixtureLogistics"]' "wrapper-failure-extensions"
assert_jq "$run_root/summary.json" '[.results[] | select(.extension_name == "FixtureCommon" and .status == "success")] | length == 1' "wrapper-success-result"
assert_jq "$run_root/summary.json" '[.results[] | select(.extension_name == "FixtureLogistics" and .status == "failed")] | length == 1' "wrapper-failure-result"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics_count == 1' "wrapper-diagnostics-count"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.blocking_diagnostics_count == 1' "wrapper-blocking-diagnostics-count"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics[0].severity == "warning"' "wrapper-diagnostic-severity"
if ! jq -e --arg warning_text "$warning_text" '.diagnostics[0].message == $warning_text' "$run_root/extensions/FixtureLogistics/summary.json" >/dev/null; then
  printf 'jq assertion failed (wrapper-diagnostic-message)\n' >&2
  cat "$run_root/extensions/FixtureLogistics/summary.json" >&2
  exit 1
fi
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "/CheckCanApplyConfigurationExtensions"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "-Extension"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "/Out"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "FixtureCommon"
assert_contains "$run_root/extensions/FixtureLogistics/stdout.log" "FixtureLogistics"
assert_contains "$run_root/extensions/FixtureLogistics/designer.out.log" "Cannot find method"

exit_failure_root="$tmpdir/run-exit-failure"
set +e
(
  cd "$fixture_root"
  FAIL_EXTENSION_NAME="FixtureLogistics" \
  ./scripts/platform/check-cfe-applicability.sh --profile env/local.json --run-root "$exit_failure_root" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 23 ]; then
  printf 'unexpected exit code for applicability command failure: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$exit_failure_root/summary.json" '.status == "failed"' "exit-failure-status"
assert_jq "$exit_failure_root/extensions/FixtureLogistics/summary.json" '.exit_code == 23' "exit-failure-extension-exit-code"

(
  cd "$fixture_root"
  ./scripts/platform/check-cfe-applicability.sh \
    --profile env/local.json \
    --extension FixtureCommon \
    --run-root "$single_root" >/dev/null
)

assert_jq "$single_root/summary.json" '.status == "success"' "single-status"
assert_jq "$single_root/summary.json" '.extension_source.selected_names == ["FixtureCommon"]' "single-selected"
assert_jq "$single_root/summary.json" '.results | length == 1' "single-results-count"
assert_jq "$single_root/extensions/FixtureCommon/summary.json" '.status == "success"' "single-extension-summary"
assert_jq "$single_root/extensions/FixtureCommon/summary.json" '.diagnostics_count == 0' "single-diagnostics-count"

(
  cd "$fixture_root"
  ./scripts/platform/check-cfe-applicability.sh --profile env/local.json --run-root "$dry_run_root" --dry-run >/dev/null
)

assert_jq "$dry_run_root/summary.json" '.status == "dry-run"' "dry-run-status"
assert_jq "$dry_run_root/extensions/FixtureCommon/summary.json" '.status == "dry-run"' "dry-run-extension-status"
assert_jq "$dry_run_root/extensions/FixtureLogistics/summary.json" '.status == "dry-run"' "dry-run-extension-status-2"
