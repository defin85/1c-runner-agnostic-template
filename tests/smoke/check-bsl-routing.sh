#!/usr/bin/env bash
# Routing contract of check-bsl without 1C and without a real analyzer:
# module selection, analyzer arguments, platform dry-run and the "синтаксис:" verdict line.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

repo="$tmpdir/repo"
mkdir -p "$repo"
cp -R "$SOURCE_ROOT/scripts" "$repo/scripts"
rm -rf "$repo/scripts/python/__pycache__"

configuration_xml() {
  local name="$1"
  local extra="$2"
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration>
    <Properties>
      <Name>$name</Name>
      <Version>1.0.0.1</Version>
      $extra
    </Properties>
  </Configuration>
</MetaDataObject>
EOF
}

cf="$repo/src/cf"
cfe="$repo/src/cfe/DemoExtension"
epf="$repo/src/epf/managed/Report"
mkdir -p "$cf/CommonModules/Common/Ext" "$cfe/CommonModules/Patch/Ext" "$epf/DemoReport/Ext" "$repo/env" "$repo/bin"
configuration_xml DemoConfiguration \
  '<CompatibilityMode>Version8_3_24</CompatibilityMode><DefaultRunMode>ManagedApplication</DefaultRunMode>' \
  >"$cf/Configuration.xml"
configuration_xml DemoExtension '<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>' \
  >"$cfe/Configuration.xml"
printf '<x/>\n' >"$cf/CommonModules/Common.xml"
printf 'Procedure A()\nEndProcedure\n' >"$cf/CommonModules/Common/Ext/Module.bsl"
printf '\n' >"$cfe/CommonModules/Patch/Ext/Module.bsl"
printf '<x/>\n' >"$epf/DemoReport.xml"
printf '\n' >"$epf/DemoReport/Ext/ObjectModule.bsl"

# Fake analyzer: records argv and reports every changed file without diagnostics.
cat >"$repo/bin/fake-analyzer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >"$FAKE_ANALYZER_ARGV"
changed=""
previous=""
for arg in "$@"; do
  if [ "$previous" = "--changed-files" ]; then
    changed="$arg"
  fi
  previous="$arg"
done
IFS=',' read -r -a files <<<"$changed"
for file in "${files[@]}"; do
  printf '{"type":"file","path":"%s","diagnostics":[]}\n' "$file"
done
printf '{"type":"done","failed_files":0}\n'
EOF
chmod +x "$repo/bin/fake-analyzer"

jq --arg binary "$repo/bin/8.3.27.1859/1cv8" --arg infobase "$tmpdir/infobase" \
  '.profileName = "check-bsl-routing-fixture" | .platform.binaryPath = $binary | .infobase.filePath = $infobase' \
  "$SOURCE_ROOT/env/local.example.json" >"$repo/env/fixture.json"

fail() {
  printf 'check-bsl-routing: %s\n' "$1" >&2
  if [ -n "${2:-}" ] && [ -f "$2" ]; then
    cat "$2" >&2
  fi
  exit 1
}

assert_contains() {
  grep -Fq -- "$2" "$1" || fail "expected '$2'" "$1"
}

run_check() {
  local expected_code="$1"
  local output="$2"
  shift 2
  local code=0
  (cd "$repo" && ./scripts/qa/check-bsl.sh "$@") >"$output" 2>&1 || code=$?
  [ "$code" = "$expected_code" ] || fail "exit code $code, expected $expected_code for: $*" "$output"
}

common="src/cf/CommonModules/Common/Ext/Module.bsl"
patch_module="src/cfe/DemoExtension/CommonModules/Patch/Ext/Module.bsl"
report_module="src/epf/managed/Report/DemoReport/Ext/ObjectModule.bsl"
argv_file="$tmpdir/analyzer-argv.txt"

# 1. Neither analyzer nor profile: nothing is checked, verdict says so explicitly.
BSL_ANALYZER_APP="$tmpdir/missing-analyzer" \
  run_check 3 "$tmpdir/none.out" --run-root "$tmpdir/run-none" "$common"
assert_contains "$tmpdir/none.out" "синтаксис: не проверен"
assert_contains "$tmpdir/none.out" "static: not-run"
assert_contains "$tmpdir/none.out" "platform: not-run"

# 2. Main configuration: only the selected module, configuration root of the export.
BSL_ANALYZER_APP="$repo/bin/fake-analyzer" FAKE_ANALYZER_ARGV="$argv_file" \
  run_check 0 "$tmpdir/cf.out" --mode fast --run-root "$tmpdir/run-cf" "$common"
assert_contains "$tmpdir/cf.out" "target: configuration DemoConfiguration (src/cf)"
assert_contains "$tmpdir/cf.out" "синтаксис: проверен"
assert_contains "$argv_file" "--configuration-root"
grep -Fxq "src/cf" "$argv_file" || fail "configuration root src/cf not passed" "$argv_file"
grep -Fxq "$common" "$argv_file" || fail "changed-files is not exactly the selected module" "$argv_file"
if grep -Fxq -- "--extension" "$argv_file" || grep -Fxq -- "--external" "$argv_file"; then
  fail "configuration check must not declare extensions or externals" "$argv_file"
fi

# 3. Extension: declared over the main configuration.
BSL_ANALYZER_APP="$repo/bin/fake-analyzer" FAKE_ANALYZER_ARGV="$argv_file" \
  run_check 0 "$tmpdir/cfe.out" --mode fast --run-root "$tmpdir/run-cfe" "$patch_module"
assert_contains "$tmpdir/cfe.out" "target: extension DemoExtension"
grep -Fxq "DemoExtension=src/cfe/DemoExtension" "$argv_file" || fail "extension not declared" "$argv_file"
grep -Fxq "$patch_module" "$argv_file" || fail "extension module not selected" "$argv_file"

# 4. EPF/ERF: external artifact, no platform module check.
BSL_ANALYZER_APP="$repo/bin/fake-analyzer" FAKE_ANALYZER_ARGV="$argv_file" \
  run_check 0 "$tmpdir/epf.out" --run-root "$tmpdir/run-epf" "$report_module"
assert_contains "$tmpdir/epf.out" "target: external DemoReport"
assert_contains "$tmpdir/epf.out" "platform: not-run"
grep -Fxq "DemoReport=$epf" "$argv_file" || fail "external artifact not declared" "$argv_file"

# 5. Modules of different roots are rejected.
run_check 2 "$tmpdir/mixed.out" --run-root "$tmpdir/run-mixed" "$common" "$patch_module"
assert_contains "$tmpdir/mixed.out" "different source roots"

# 6. Platform dry-run: platform version, compatibility mode and partial load are reported.
BSL_ANALYZER_APP="$tmpdir/missing-analyzer" \
  run_check 3 "$tmpdir/dry.out" --profile env/fixture.json --dry-run --run-root "$tmpdir/run-dry" "$common"
assert_contains "$tmpdir/dry.out" "platform 8.3.27.1859, compatibility Version8_3_24"
assert_contains "$tmpdir/dry.out" "синтаксис: не проверен"
platform_summary="$tmpdir/run-dry/platform/summary.json"
[ -f "$platform_summary" ] || fail "platform summary is missing" "$tmpdir/dry.out"
for expected in '"/LoadConfigFromFiles"' '"-listFile"' '"-partial"' '"/CheckModules"' '"CommonModules/Common.xml"'; do
  assert_contains "$platform_summary" "$expected"
done

printf 'check-bsl-routing: ok\n'
