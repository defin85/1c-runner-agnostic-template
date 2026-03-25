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
jq -e '.capabilities.xunit.unsupportedReason == "Legacy xUnit contour looked like a placeholder or no-op command; replace it with a repo-owned entrypoint before treating this profile as green."' "$converted_profile" >/dev/null
jq -e '.capabilities.bdd.unsupportedReason == "Legacy BDD contour looked like a placeholder or no-op command; replace it with a repo-owned entrypoint before treating this profile as green."' "$converted_profile" >/dev/null
jq -e '.capabilities.smoke.unsupportedReason == "Legacy smoke contour looked like a placeholder or no-op command; replace it with a repo-owned entrypoint before treating this profile as green."' "$converted_profile" >/dev/null
jq -e '.capabilities.xunit.command == null' "$converted_profile" >/dev/null
jq -e '.capabilities.bdd.command == null' "$converted_profile" >/dev/null
jq -e '.capabilities.smoke.command == null' "$converted_profile" >/dev/null

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

repo_owned_profile="$tmpdir/repo-owned.json"
repo_owned_converted_profile="$tmpdir/repo-owned-converted.json"
wrapped_repo_owned_profile="$tmpdir/wrapped-repo-owned.json"
wrapped_repo_owned_converted_profile="$tmpdir/wrapped-repo-owned-converted.json"

cat >"$repo_owned_profile" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "repo-owned",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "LOAD_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/repo-owned-ref /N repo-owned-user /LoadConfigFromFiles ./src/cf",
    "SMOKE_RUN_CMD": "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/repo-owned-smoke"
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/template/migrate-runtime-profile-v2.sh "$repo_owned_profile" >"$repo_owned_converted_profile"
)

jq -e '.capabilities.smoke.command == ["bash", "-lc", "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/repo-owned-smoke"]' "$repo_owned_converted_profile" >/dev/null
jq -e '.capabilities.smoke.unsupportedReason == null' "$repo_owned_converted_profile" >/dev/null

cat >"$wrapped_repo_owned_profile" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "wrapped-repo-owned",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "LOAD_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/wrapped-ref /N wrapped-user /LoadConfigFromFiles ./src/cf",
    "SMOKE_RUN_CMD": "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/wrapped-smoke || true"
  }
}
EOF

(
  cd "$SOURCE_ROOT"
  ./scripts/template/migrate-runtime-profile-v2.sh "$wrapped_repo_owned_profile" >"$wrapped_repo_owned_converted_profile"
)

jq -e '.capabilities.smoke.unsupportedReason == "Legacy smoke contour looked like a placeholder or no-op command; replace it with a repo-owned entrypoint before treating this profile as green."' "$wrapped_repo_owned_converted_profile" >/dev/null
jq -e '.capabilities.smoke.command == null' "$wrapped_repo_owned_converted_profile" >/dev/null
