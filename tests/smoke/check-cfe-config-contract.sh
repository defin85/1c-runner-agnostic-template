#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
run_root="$tmpdir/run"
warning_root="$tmpdir/run-warning"
dry_run_root="$tmpdir/run-dry"
fake_binary="$tmpdir/1cv8"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fixture_root/env" \
  "$fixture_root/src/cfe/FixtureCommon" \
  "$fixture_root/src/cfe/FixtureLogistics" \
  "$fixture_root/src/cf/CommonForms/Расширения/Ext/Form"

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
  if [ "${CONFIG_DIAGNOSTIC_EXTENSION_NAME:-}" = "$extension_name" ]; then
    {
      printf '%s ОбщаяФорма.Расширения.Форма Handler missing:  ПроверитьВозможностьПримененияВсехРасширений "ПроверитьВозможностьПримененияВсехРасширений"\n' "$extension_name"
      printf '{%s Документ.ЗаданиеНаПеревозку.МодульОбъекта(148,2)}: Procedure or function with the specified name is not defined (ОчиститьТоварыКДоставкеПоУдаленнымИзЗаданияРаспоряжениям)\n' "$extension_name"
    } >"$out_log"
  elif [ "${CONFIG_WARNING_ONLY_EXTENSION_NAME:-}" = "$extension_name" ]; then
    printf '%s ОбщаяФорма.Расширения.Форма Handler missing:  Обновить "Обновить"\n' "$extension_name" >"$out_log"
  else
    printf 'No errors found\n' >"$out_log"
  fi
fi

if [ "${FAIL_EXTENSION_NAME:-}" = "$extension_name" ]; then
  exit 101
fi
EOF

chmod +x "$fake_binary"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "check-cfe-config-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/check-cfe-config-fixture",
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
cat >"$fixture_root/src/cf/CommonForms/Расширения/Ext/Form/Module.bsl" <<'EOF'
Процедура Обновить(Команда)
КонецПроцедуры
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

set +e
(
  cd "$fixture_root"
  CONFIG_DIAGNOSTIC_EXTENSION_NAME="FixtureLogistics" \
  FAIL_EXTENSION_NAME="FixtureLogistics" \
  ./scripts/platform/check-cfe-config.sh --profile env/local.json --run-root "$run_root" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 101 ]; then
  printf 'unexpected exit code for config verification failure: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$run_root/summary.json" '.status == "failed"' "wrapper-status"
assert_jq "$run_root/summary.json" '.capability.id == "check-cfe-config"' "wrapper-capability"
assert_jq "$run_root/summary.json" '.failure.classification == "extension-config-verification failed"' "wrapper-failure-classification"
assert_jq "$run_root/summary.json" '.failure.extensions == ["FixtureLogistics"]' "wrapper-failure-extensions"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics_count == 2' "extension-diagnostics-count"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.blocking_diagnostics_count == 2' "extension-blocking-count"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.inherited_diagnostics_count == 0' "extension-inherited-count"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics[0].severity == "warning"' "extension-warning-severity"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics[1].severity == "error"' "extension-error-severity"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics[0].classification == "blocking"' "extension-warning-classification"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.diagnostics[0].resolution.kind == "unresolved_handler"' "extension-warning-resolution"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.blocking_diagnostics | length == 2' "extension-blocking-list"
assert_jq "$run_root/extensions/FixtureLogistics/summary.json" '.inherited_diagnostics == []' "extension-inherited-list"
assert_contains "$run_root/extensions/FixtureLogistics/designer.out.log" "Handler missing:"
assert_contains "$run_root/extensions/FixtureLogistics/designer.out.log" "Procedure or function with the specified name is not defined"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "/CheckConfig"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "-HandlersExistence"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "-ThinClient"
assert_contains "$run_root/extensions/FixtureCommon/stdout.log" "-ThickClientManagedApplication"

set +e
(
  cd "$fixture_root"
  CONFIG_WARNING_ONLY_EXTENSION_NAME="FixtureCommon" \
  ./scripts/platform/check-cfe-config.sh --profile env/local.json --extension FixtureCommon --run-root "$warning_root" >/dev/null
)
status=$?
set -e

if [ "$status" -ne 0 ]; then
  printf 'unexpected exit code for inherited handler config diagnostics: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$warning_root/summary.json" '.status == "success"' "warning-wrapper-status"
assert_jq "$warning_root/summary.json" '.failure == null' "warning-wrapper-failure"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.diagnostics_count == 1' "warning-diagnostics-count"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.blocking_diagnostics_count == 0' "warning-blocking-count"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.inherited_diagnostics_count == 1' "warning-inherited-count"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.status == "success"' "warning-extension-status"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.diagnostics[0].classification == "inherited_handler"' "warning-classification"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.diagnostics[0].resolution.kind == "resolved_in_base_form_module"' "warning-resolution"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.diagnostics[0].resolution.base_form_module == "src/cf/CommonForms/Расширения/Ext/Form/Module.bsl"' "warning-base-module"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.blocking_diagnostics == []' "warning-blocking-list"
assert_jq "$warning_root/extensions/FixtureCommon/summary.json" '.inherited_diagnostics | length == 1' "warning-inherited-list"

(
  cd "$fixture_root"
  ./scripts/platform/check-cfe-config.sh --profile env/local.json --run-root "$dry_run_root" --dry-run >/dev/null
)

assert_jq "$dry_run_root/summary.json" '.status == "dry-run"' "dry-run-status"
assert_jq "$dry_run_root/extensions/FixtureCommon/summary.json" '.status == "dry-run"' "dry-run-extension-status"
assert_jq "$dry_run_root/extensions/FixtureLogistics/summary.json" '.status == "dry-run"' "dry-run-extension-status-2"
