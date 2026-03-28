#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'designer-called\n'
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ibcmd-called\n'
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

assert_stderr_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected stderr text not found: %s\n' "$expected" >&2
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

write_fixture_repo() {
  local repo_root="$1"
  local init_git="${2:-yes}"

  mkdir -p "$repo_root"
  cp -R "$SOURCE_ROOT/scripts" "$repo_root/scripts"
  mkdir -p "$repo_root/env" "$repo_root/src/cf/Catalogs"

  cat >"$repo_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "load-diff-validation",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/load-diff-validation",
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

  printf '<items baseline />\n' >"$repo_root/src/cf/Catalogs/Items.xml"

  if [ "$init_git" = "yes" ]; then
    (
      cd "$repo_root"
      git init >/dev/null
      git config user.name "Smoke Fixture"
      git config user.email "smoke@example.invalid"
      git add .
      git commit -m "fixture baseline" >/dev/null
    )
  fi
}

run_expect_failure() {
  local repo_root="$1"
  local run_root="$2"
  local stderr_path="$3"

  set +e
  (
    cd "$repo_root"
    ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$run_root" >/dev/null
  ) 2>"$stderr_path"
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf 'load-diff-src unexpectedly succeeded\n' >&2
    cat "$stderr_path" >&2
    exit 1
  fi
}

export ONEC_IBCMD_PASSWORD="load-diff-secret"

repo_deleted="$tmpdir/repo-deleted"
write_fixture_repo "$repo_deleted"
rm "$repo_deleted/src/cf/Catalogs/Items.xml"
run_deleted_root="$tmpdir/run-deleted"
stderr_deleted="$tmpdir/run-deleted.stderr"
run_expect_failure "$repo_deleted" "$run_deleted_root" "$stderr_deleted"
assert_stderr_contains "$stderr_deleted" "no eligible changed files inside source tree"
assert_jq "$run_deleted_root/summary.json" '.status == "failed"' "deleted-status"
assert_jq "$run_deleted_root/summary.json" '.selection.selected_files == []' "deleted-selected-empty"
assert_jq "$run_deleted_root/summary.json" '.selection.ignored_files == [{"path":"src/cf/Catalogs/Items.xml","reason":"missing-or-deleted"}]' "deleted-ignored"
assert_jq "$run_deleted_root/summary.json" '.delegated == null' "deleted-no-delegation"

repo_outside="$tmpdir/repo-outside"
write_fixture_repo "$repo_outside"
printf 'outside change\n' >"$repo_outside/README.outside"
run_outside_root="$tmpdir/run-outside"
stderr_outside="$tmpdir/run-outside.stderr"
run_expect_failure "$repo_outside" "$run_outside_root" "$stderr_outside"
assert_stderr_contains "$stderr_outside" "no eligible changed files inside source tree"
assert_jq "$run_outside_root/summary.json" '.status == "failed"' "outside-status"
assert_jq "$run_outside_root/summary.json" '.selection.selected_files == []' "outside-selected-empty"
assert_jq "$run_outside_root/summary.json" '.selection.ignored_files == [{"path":"README.outside","reason":"outside-source-tree"}]' "outside-ignored"
assert_jq "$run_outside_root/summary.json" '.delegated == null' "outside-no-delegation"

repo_clean="$tmpdir/repo-clean"
write_fixture_repo "$repo_clean"
run_clean_root="$tmpdir/run-clean"
stderr_clean="$tmpdir/run-clean.stderr"
run_expect_failure "$repo_clean" "$run_clean_root" "$stderr_clean"
assert_stderr_contains "$stderr_clean" "no eligible changed files inside source tree"
assert_jq "$run_clean_root/summary.json" '.status == "failed"' "clean-status"
assert_jq "$run_clean_root/summary.json" '.selection.selected_files == []' "clean-selected-empty"
assert_jq "$run_clean_root/summary.json" '.selection.ignored_files == []' "clean-ignored-empty"
assert_jq "$run_clean_root/summary.json" '.delegated == null' "clean-no-delegation"

repo_nongit="$tmpdir/repo-nongit"
write_fixture_repo "$repo_nongit" "no"
printf '<config changed />\n' >"$repo_nongit/src/cf/Catalogs/Items.xml"
run_nongit_root="$tmpdir/run-nongit"
stderr_nongit="$tmpdir/run-nongit.stderr"
run_expect_failure "$repo_nongit" "$run_nongit_root" "$stderr_nongit"
assert_stderr_contains "$stderr_nongit" "git-backed diff requires a git worktree"
assert_jq "$run_nongit_root/summary.json" '.status == "failed"' "nongit-status"
assert_jq "$run_nongit_root/summary.json" '.selection.error == "git-backed diff requires a git worktree"' "nongit-selection-error"
assert_jq "$run_nongit_root/summary.json" '.delegated == null' "nongit-no-delegation"

repo_delegated_failure="$tmpdir/repo-delegated-failure"
write_fixture_repo "$repo_delegated_failure"
jq '.capabilities.loadSrc = {"command":["bash","-lc","printf '\''load-src override\n'\''"]}' \
  "$repo_delegated_failure/env/local.json" >"$repo_delegated_failure/env/local.json.tmp"
mv "$repo_delegated_failure/env/local.json.tmp" "$repo_delegated_failure/env/local.json"
printf '<config changed />\n' >"$repo_delegated_failure/src/cf/Catalogs/Items.xml"
run_delegated_failure_root="$tmpdir/run-delegated-failure"
stderr_delegated_failure="$tmpdir/run-delegated-failure.stderr"
run_expect_failure "$repo_delegated_failure" "$run_delegated_failure_root" "$stderr_delegated_failure"
assert_stderr_contains "$run_delegated_failure_root/stderr.log" "partial load-src is not supported when capabilities.loadSrc.command override is set"
assert_jq "$run_delegated_failure_root/summary.json" '.status == "failed"' "delegated-failure-status"
assert_jq "$run_delegated_failure_root/summary.json" '.selection.selected_files == ["Catalogs/Items.xml"]' "delegated-failure-selected"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.capability == "load-src"' "delegated-failure-capability"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "delegated-failure-run-root" \
  --args "$run_delegated_failure_root/load-src"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "delegated-failure-summary-json" \
  --args "$run_delegated_failure_root/load-src/summary.json"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "delegated-failure-stdout-log" \
  --args "$run_delegated_failure_root/load-src/stdout.log"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "delegated-failure-stderr-log" \
  --args "$run_delegated_failure_root/load-src/stderr.log"
if [ -e "$run_delegated_failure_root/load-src/summary.json" ]; then
  printf 'delegated load-src summary.json unexpectedly exists\n' >&2
  cat "$run_delegated_failure_root/summary.json" >&2
  exit 1
fi
