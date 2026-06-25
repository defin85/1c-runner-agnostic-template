#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
fake_ibcmd="$tmpdir/fake-ibcmd"
fake_platform_dir="$tmpdir/platform"
fake_designer="$fake_platform_dir/1cv8"
fake_client="$fake_platform_dir/1cv8c"
run_root="$tmpdir/run"
load_cfe_root="$tmpdir/load-cfe"
load_cfe_selected_root="$tmpdir/load-cfe-selected"
yaxunit_root="$tmpdir/yaxunit"
warm_root="$tmpdir/yaxunit-warm"
metadata_root="$tmpdir/metadata"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fake_platform_dir" \
  "$fixture_root/automation/context" \
  "$fixture_root/env" \
  "$fixture_root/src/cf/ut22/CommonModules" \
  "$fixture_root/src/cf/unf/CommonModules" \
  "$fixture_root/src/cfe/ExtCommon" \
  "$fixture_root/src/cfe/ExtUt" \
  "$fixture_root/src/cfe/ExtUnf"

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@"
EOF
chmod +x "$fake_ibcmd"
cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@"
EOF
cp "$fake_designer" "$fake_client"
chmod +x "$fake_designer" "$fake_client"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "multi-target-fixture",
  "runnerAdapter": "direct-platform",
  "target": {
    "id": "ut22"
  },
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/ib",
    "auth": {
      "mode": "os"
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/server"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/db"
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
      "id": "ut22",
      "sourcePath": "src/cf/ut22"
    },
    {
      "id": "unf",
      "sourcePath": "src/cf/unf"
    }
  ],
  "extensionMatrix": {
    "ut22": ["ExtCommon", "ExtUt"],
    "unf": ["ExtCommon", "ExtUnf"]
  }
}
EOF

cat >"$fixture_root/automation/context/project-delta-hints.json" <<'EOF'
{
  "selectors": {
    "pathPrefixes": [],
    "pathKeywords": []
  },
  "representativePaths": []
}
EOF

printf '<Configuration name="UT22" uuid="ut22-uuid" />\n' >"$fixture_root/src/cf/ut22/Configuration.xml"
printf '<Configuration name="UNF" uuid="unf-uuid" />\n' >"$fixture_root/src/cf/unf/Configuration.xml"
printf '<extension />\n' >"$fixture_root/src/cfe/ExtCommon/Configuration.xml"
printf '<extension />\n' >"$fixture_root/src/cfe/ExtUt/Configuration.xml"
printf '<extension />\n' >"$fixture_root/src/cfe/ExtUnf/Configuration.xml"

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
  ./scripts/platform/load-src.sh --profile env/local.json --run-root "$run_root/missing-target" --dry-run 2>"$tmpdir/missing-target.stderr"
)
status=$?
set -e
[ "$status" -ne 0 ] || {
  printf 'load-src without --target unexpectedly succeeded\n' >&2
  exit 1
}
assert_contains "$tmpdir/missing-target.stderr" "multi-target workspace requires --target <id>"

jq 'del(.target)' "$fixture_root/env/local.json" >"$fixture_root/env/no-target.json"
set +e
(
  cd "$fixture_root"
  ./scripts/platform/load-src.sh --profile env/no-target.json --target ut22 --run-root "$run_root/missing-profile-target" --dry-run 2>"$tmpdir/missing-profile-target.stderr"
)
status=$?
set -e
[ "$status" -ne 0 ] || {
  printf 'load-src with profile missing target.id unexpectedly succeeded\n' >&2
  exit 1
}
assert_contains "$tmpdir/missing-profile-target.stderr" "runtime profile target.id is required"

(
  cd "$fixture_root"
  ./scripts/platform/load-src.sh --profile env/local.json --target ut22 --run-root "$run_root/load-src" --dry-run >/dev/null
)
assert_jq "$run_root/load-src/summary.json" '.status == "dry-run"' "load-src-target-status"
assert_jq "$run_root/load-src/summary.json" '.runtime_profile.target == "ut22"' "load-src-profile-target"
assert_jq "$run_root/load-src/summary.json" '.driver_context.source_dir == $ARGS.positional[0]' "load-src-source-dir" \
  --args "$fixture_root/src/cf/ut22"

(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --target ut22 --run-root "$load_cfe_root" --dry-run >/dev/null
)
assert_jq "$load_cfe_root/summary.json" '(.extension_source.selected_names | sort) == ["ExtCommon", "ExtUt"]' "target-extension-set"
assert_jq "$load_cfe_root/summary.json" '.extension_source.target_id == "ut22"' "target-extension-id"

(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --target ut22 --extension ExtCommon --run-root "$load_cfe_selected_root" --dry-run >/dev/null
)
assert_jq "$load_cfe_selected_root/summary.json" '.extension_source.selected_names == ["ExtCommon"]' "target-selected-extension"
assert_jq "$load_cfe_selected_root/summary.json" '.extension_source.target_id == "ut22"' "target-selected-extension-id"

set +e
(
  cd "$fixture_root"
  ./scripts/platform/load-cfe.sh --profile env/local.json --target ut22 --extension ExtUnf --run-root "$tmpdir/load-cfe-wrong-target" --dry-run 2>"$tmpdir/load-cfe-wrong-target.stderr"
)
status=$?
set -e
[ "$status" -ne 0 ] || {
  printf 'load-cfe accepted extension outside target matrix\n' >&2
  exit 1
}
assert_contains "$tmpdir/load-cfe-wrong-target.stderr" "requested extension is not present in target matrix for target=ut22: ExtUnf"

(
  cd "$fixture_root"
  ./scripts/test/run-yaxunit.sh --profile env/local.json --target ut22 --module SmokeModule --run-root "$yaxunit_root" --dry-run >/dev/null
)
assert_jq "$yaxunit_root/summary.json" '.status == "dry-run"' "yaxunit-target-dry-run"
assert_jq "$yaxunit_root/summary.json" '.runtime_profile.target == "ut22"' "yaxunit-target-summary"

(
  cd "$fixture_root"
  ./scripts/test/run-yaxunit-warm-service.sh status --profile env/local.json --target ut22 --run-root "$warm_root" >/dev/null
)
assert_jq "$warm_root/summary.json" '.status == "success"' "yaxunit-warm-target-status"
assert_jq "$warm_root/summary.json" '.runtime_profile.target == "ut22"' "yaxunit-warm-target-summary"

(
  cd "$fixture_root"
  ./scripts/llm/export-context.sh --write >/dev/null
)
assert_jq "$fixture_root/automation/context/metadata-index.generated.json" '.targetMetadata.targets | length == 2' "target-metadata-count"
assert_jq "$fixture_root/automation/context/metadata-index.generated.json" '.targetMetadata.extensionMatrix.ut22 == ["ExtCommon", "ExtUt"]' "target-metadata-matrix"

cp "$fixture_root/automation/context/target-matrix.json" "$metadata_root.json"
jq '.extensionMatrix.ut22 += ["MissingExtension"]' "$metadata_root.json" >"$fixture_root/automation/context/target-matrix.json"

set +e
(
  cd "$fixture_root"
  ./scripts/llm/export-context.sh --check 2>"$tmpdir/stale-context.stderr"
)
status=$?
set -e
[ "$status" -ne 0 ] || {
  printf 'export-context --check accepted stale target matrix\n' >&2
  exit 1
}
assert_contains "$tmpdir/stale-context.stderr" "target matrix extension not found under src/cfe: MissingExtension"

cp "$metadata_root.json" "$fixture_root/automation/context/target-matrix.json"
cat >"$fixture_root/automation/context/runtime-support-matrix.json" <<'EOF'
{
  "matrixRole": "project-owned-runtime-support-matrix",
  "contours": [
    {
      "id": "load-cfe",
      "targets": ["missing-target"],
      "extensionMatrix": {
        "ut22": ["MissingExtension"]
      }
    }
  ]
}
EOF

set +e
(
  cd "$fixture_root"
  ./scripts/llm/export-context.sh --check 2>"$tmpdir/stale-runtime-matrix.stderr"
)
status=$?
set -e
[ "$status" -ne 0 ] || {
  printf 'export-context --check accepted stale runtime support matrix\n' >&2
  exit 1
}
assert_contains "$tmpdir/stale-runtime-matrix.stderr" "runtime support matrix references unknown target: missing-target"
