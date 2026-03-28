#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"
run_root="$tmpdir/run"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fixture_root/env" \
  "$fixture_root/src/cf/Catalogs" \
  "$fixture_root/src/cf/Forms" \
  "$fixture_root/src/cf/EventSubscriptions"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "load-diff-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/load-diff-fixture",
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
      "dataDir": "$tmpdir/server"
    },
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/file-ib/db"
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "ibcmd",
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

printf '<items baseline />\n' >"$fixture_root/src/cf/Catalogs/Items.xml"
printf '<list baseline />\n' >"$fixture_root/src/cf/Forms/List.xml"
printf '<config baseline />\n' >"$fixture_root/src/cf/Configuration.xml"

(
  cd "$fixture_root"
  git init >/dev/null
  git config user.name "Smoke Fixture"
  git config user.email "smoke@example.invalid"
  git add .
  git commit -m "fixture baseline" >/dev/null
)

printf '<config changed />\n' >"$fixture_root/src/cf/Configuration.xml"
printf '<subscription new />\n' >"$fixture_root/src/cf/EventSubscriptions/LoadDiff.xml"

export ONEC_IBCMD_PASSWORD="load-diff-secret"

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
  shift 3

  if ! jq -e "$expr" "$file" "$@" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

(
  cd "$fixture_root"
  ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$run_root" >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success"' "wrapper-status"
assert_jq "$run_root/summary.json" '.capability.id == "load-diff-src"' "wrapper-capability"
assert_jq "$run_root/summary.json" '.execution.source == "git-diff-to-load-src"' "wrapper-source"
assert_jq "$run_root/summary.json" '.selection.selected_files == ["Configuration.xml", "EventSubscriptions/LoadDiff.xml"]' "wrapper-selected-files"
assert_jq "$run_root/summary.json" '.selection.ignored_files == []' "wrapper-no-ignored-files"
assert_jq "$run_root/summary.json" '.delegated.capability == "load-src"' "wrapper-delegated-capability"
assert_jq "$run_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "wrapper-delegated-run-root" \
  --args "$run_root/load-src"
assert_jq "$run_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "wrapper-delegated-summary" \
  --args "$run_root/load-src/summary.json"
assert_jq "$run_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "wrapper-delegated-stdout-log" \
  --args "$run_root/load-src/stdout.log"
assert_jq "$run_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "wrapper-delegated-stderr-log" \
  --args "$run_root/load-src/stderr.log"
assert_jq "$run_root/load-src/summary.json" '.status == "success"' "delegated-status"
assert_jq "$run_root/load-src/summary.json" '.driver == "ibcmd"' "delegated-driver"
assert_jq "$run_root/load-src/summary.json" '.driver_context.partial_import == true' "delegated-partial-import"
assert_contains "$run_root/load-src/stdout.log" "config"
assert_contains "$run_root/load-src/stdout.log" "import"
assert_contains "$run_root/load-src/stdout.log" "files"
assert_contains "$run_root/load-src/stdout.log" "--partial"
assert_contains "$run_root/load-src/stdout.log" "Configuration.xml"
assert_contains "$run_root/load-src/stdout.log" "EventSubscriptions/LoadDiff.xml"

dry_run_root="$tmpdir/run-dry-run"

(
  cd "$fixture_root"
  ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$dry_run_root" --dry-run >/dev/null
)

assert_jq "$dry_run_root/summary.json" '.status == "dry-run"' "wrapper-dry-run-status"
assert_jq "$dry_run_root/summary.json" '.selection.selected_files == ["Configuration.xml", "EventSubscriptions/LoadDiff.xml"]' "wrapper-dry-run-selected-files"
assert_jq "$dry_run_root/summary.json" '.delegated.capability == "load-src"' "wrapper-dry-run-delegated-capability"
assert_jq "$dry_run_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "wrapper-dry-run-delegated-run-root" \
  --args "$dry_run_root/load-src"
assert_jq "$dry_run_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "wrapper-dry-run-delegated-summary" \
  --args "$dry_run_root/load-src/summary.json"
assert_jq "$dry_run_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "wrapper-dry-run-delegated-stdout-log" \
  --args "$dry_run_root/load-src/stdout.log"
assert_jq "$dry_run_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "wrapper-dry-run-delegated-stderr-log" \
  --args "$dry_run_root/load-src/stderr.log"
assert_jq "$dry_run_root/load-src/summary.json" '.status == "dry-run"' "delegated-dry-run-status"
assert_jq "$dry_run_root/load-src/summary.json" '.driver_context.partial_import == true' "delegated-dry-run-partial-import"

jq '.capabilities.diffSrc = {"command":["bash","-lc","printf '\''profile-defined diffSrc must not run\n'\'' >&2; exit 42"]}' \
  "$fixture_root/env/local.json" >"$fixture_root/env/local.json.tmp"
mv "$fixture_root/env/local.json.tmp" "$fixture_root/env/local.json"

cat >"$fixture_root/scripts/platform/diff-src.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'repo diff-src entrypoint must not run\n' >&2
exit 42
EOF

chmod +x "$fixture_root/scripts/platform/diff-src.sh"

independent_run_root="$tmpdir/run-independent"

(
  cd "$fixture_root"
  ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$independent_run_root" >/dev/null
)

assert_jq "$independent_run_root/summary.json" '.status == "success"' "wrapper-independent-status"
assert_jq "$independent_run_root/summary.json" '.selection.selected_files == ["Configuration.xml", "EventSubscriptions/LoadDiff.xml"]' "wrapper-independent-selected-files"
assert_not_contains "$independent_run_root/stderr.log" "profile-defined diffSrc must not run"
assert_not_contains "$independent_run_root/stderr.log" "repo diff-src entrypoint must not run"
