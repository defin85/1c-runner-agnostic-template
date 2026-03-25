#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

legacy_profile="$tmpdir/legacy.json"
converted_profile="$tmpdir/converted.json"
placeholder_profile="$tmpdir/placeholder.json"
placeholder_converted_profile="$tmpdir/placeholder-converted.json"

cat >"$legacy_profile" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "legacy",
  "projectName": "Legacy Project",
  "projectSlug": "legacy-project",
  "description": "legacy profile",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "/opt/1cv8/1cv8 CREATEINFOBASE File=\"/var/tmp/legacy-project\"",
    "DUMP_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/legacy-ref /N legacy-user /DumpConfigToFiles ./src/cf",
    "LOAD_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/legacy-ref /N legacy-user /LoadConfigFromFiles ./src/cf",
    "UPDATE_DB_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/legacy-ref /N legacy-user /UpdateDBCfg",
    "DIFF_SRC_CMD": "git diff -- ./src",
    "XUNIT_RUN_CMD": "echo legacy xunit",
    "BDD_RUN_CMD": "echo legacy bdd",
    "SMOKE_RUN_CMD": "echo legacy smoke"
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/template/migrate-runtime-profile-v2.sh "$legacy_profile" >"$converted_profile"
)

jq -e '.schemaVersion == 2' "$converted_profile" >/dev/null
jq -e '.profileName == "legacy"' "$converted_profile" >/dev/null
jq -e '.projectName == "Legacy Project"' "$converted_profile" >/dev/null
jq -e '.runnerAdapter == "direct-platform"' "$converted_profile" >/dev/null
jq -e '.platform.binaryPath == "/opt/1cv8/1cv8"' "$converted_profile" >/dev/null
jq -e '.infobase.mode == "client-server"' "$converted_profile" >/dev/null
jq -e '.infobase.server == "localhost"' "$converted_profile" >/dev/null
jq -e '.infobase.ref == "legacy-ref"' "$converted_profile" >/dev/null
jq -e '.infobase.auth.user == "legacy-user"' "$converted_profile" >/dev/null
jq -e '.capabilities.xunit.command[0] == "bash"' "$converted_profile" >/dev/null
jq -e '.capabilities.xunit.command[2] == "echo legacy xunit"' "$converted_profile" >/dev/null

cat >"$placeholder_profile" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "placeholder",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "/opt/1cv8/1cv8 CREATEINFOBASE File=\"/var/tmp/placeholder-project\"",
    "LOAD_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/placeholder-ref /N placeholder-user /LoadConfigFromFiles ./src/cf"
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/template/migrate-runtime-profile-v2.sh "$placeholder_profile" >"$placeholder_converted_profile"
)

jq -e '.capabilities.xunit.unsupportedReason == "xUnit contour is not wired yet; migrate it before treating this profile as green."' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.bdd.unsupportedReason == "BDD contour is not wired yet; migrate it before treating this profile as green."' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.smoke.unsupportedReason == "Smoke contour is not wired yet; migrate it before treating this profile as green."' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.publishHttp.unsupportedReason == "Publish HTTP contour is not wired yet; migrate it before treating this profile as green."' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.xunit.command == null' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.bdd.command == null' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.smoke.command == null' "$placeholder_converted_profile" >/dev/null
jq -e '.capabilities.publishHttp.command == null' "$placeholder_converted_profile" >/dev/null
