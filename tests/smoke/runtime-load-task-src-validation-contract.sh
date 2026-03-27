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

  mkdir -p "$repo_root"
  cp -R "$SOURCE_ROOT/scripts" "$repo_root/scripts"
  mkdir -p "$repo_root/env" "$repo_root/src/cf/Catalogs" "$repo_root/src/cf/Forms"

  cat >"$repo_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "load-task-validation",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/load-task-validation",
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
  printf '<list baseline />\n' >"$repo_root/src/cf/Forms/List.xml"

  (
    cd "$repo_root"
    git init >/dev/null
    git config user.name "Smoke Fixture"
    git config user.email "smoke@example.invalid"
    git add .
    git commit -m "fixture baseline" >/dev/null
  )
}

run_expect_failure() {
  local repo_root="$1"
  local run_root="$2"
  local stderr_path="$3"
  shift 3

  set +e
  (
    cd "$repo_root"
    ./scripts/platform/load-task-src.sh --profile env/local.json --run-root "$run_root" "$@" >/dev/null
  ) 2>"$stderr_path"
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf 'load-task-src unexpectedly succeeded\n' >&2
    cat "$stderr_path" >&2
    exit 1
  fi
}

export ONEC_IBCMD_PASSWORD="load-task-secret"

repo_missing="$tmpdir/repo-missing"
write_fixture_repo "$repo_missing"
run_missing_root="$tmpdir/run-missing"
stderr_missing="$tmpdir/run-missing.stderr"
run_expect_failure "$repo_missing" "$run_missing_root" "$stderr_missing" --bead missing-bead
assert_stderr_contains "$stderr_missing" "no commits matched selector"
assert_jq "$run_missing_root/summary.json" '.status == "failed"' "missing-status"
assert_jq "$run_missing_root/summary.json" '.selection.selector.mode == "bead"' "missing-selector-mode"
assert_jq "$run_missing_root/summary.json" '.selection.selected_commits == []' "missing-commits-empty"
assert_jq "$run_missing_root/summary.json" '.selection.error == "no commits matched selector"' "missing-error"
assert_jq "$run_missing_root/summary.json" '.delegated == null' "missing-no-delegation"

repo_range="$tmpdir/repo-range"
write_fixture_repo "$repo_range"
printf '<items changed />\n' >"$repo_range/src/cf/Catalogs/Items.xml"
(
  cd "$repo_range"
  git add src/cf/Catalogs/Items.xml
  git commit -m $'range commit\n\nBead: range.1\nWork-Item: 1000' >/dev/null
)
range_commit="$(git -C "$repo_range" rev-parse HEAD)"
range_run_root="$tmpdir/run-range"
(
  cd "$repo_range"
  ./scripts/platform/load-task-src.sh --profile env/local.json --run-root "$range_run_root" --range "${range_commit}^..${range_commit}" >/dev/null
)
assert_jq "$range_run_root/summary.json" '.status == "success"' "range-status"
assert_jq "$range_run_root/summary.json" '.selection.selector.mode == "range"' "range-selector-mode"
range_revset="${range_commit}^..${range_commit}"
if ! jq -e --arg revset "$range_revset" '.selection.selector.value == $revset' "$range_run_root/summary.json" >/dev/null; then
  printf 'jq assertion failed (range-selector-value)\n' >&2
  cat "$range_run_root/summary.json" >&2
  exit 1
fi
assert_jq "$range_run_root/summary.json" '.selection.selected_files == ["Catalogs/Items.xml"]' "range-selected-files"

repo_deleted="$tmpdir/repo-deleted"
write_fixture_repo "$repo_deleted"
(
  cd "$repo_deleted"
  git rm -q src/cf/Catalogs/Items.xml
  git commit -m $'delete only\n\nBead: delete.1\nWork-Item: 1001' >/dev/null
)
run_deleted_root="$tmpdir/run-deleted"
stderr_deleted="$tmpdir/run-deleted.stderr"
run_expect_failure "$repo_deleted" "$run_deleted_root" "$stderr_deleted" --bead delete.1
assert_stderr_contains "$stderr_deleted" "no eligible committed files inside source tree"
assert_jq "$run_deleted_root/summary.json" '.status == "failed"' "deleted-status"
assert_jq "$run_deleted_root/summary.json" '.selection.selected_files == []' "deleted-selected-empty"
assert_jq "$run_deleted_root/summary.json" '.selection.deleted_paths | length == 1' "deleted-path-count"
assert_jq "$run_deleted_root/summary.json" '.delegated == null' "deleted-no-delegation"

repo_delegated_failure="$tmpdir/repo-delegated-failure"
write_fixture_repo "$repo_delegated_failure"
jq 'del(.platform.ibcmdPath)' "$repo_delegated_failure/env/local.json" >"$repo_delegated_failure/env/local.json.tmp"
mv "$repo_delegated_failure/env/local.json.tmp" "$repo_delegated_failure/env/local.json"
printf '<items delegated failure />\n' >"$repo_delegated_failure/src/cf/Catalogs/Items.xml"
(
  cd "$repo_delegated_failure"
  git add env/local.json src/cf/Catalogs/Items.xml
  git commit -m $'delegated failure\n\nBead: failure-bead' >/dev/null
)
run_delegated_failure_root="$tmpdir/run-delegated-failure"
stderr_delegated_failure="$tmpdir/run-delegated-failure.stderr"
run_expect_failure "$repo_delegated_failure" "$run_delegated_failure_root" "$stderr_delegated_failure" --bead failure-bead
assert_jq "$run_delegated_failure_root/summary.json" '.status == "failed"' "delegated-failure-status"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.capability == "load-src"' "delegated-failure-capability"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "delegated-failure-run-root" \
  --args "$run_delegated_failure_root/load-src"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "delegated-failure-summary-json" \
  --args "$run_delegated_failure_root/load-src/summary.json"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "delegated-failure-stdout-log" \
  --args "$run_delegated_failure_root/load-src/stdout.log"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "delegated-failure-stderr-log" \
  --args "$run_delegated_failure_root/load-src/stderr.log"
assert_jq "$run_delegated_failure_root/summary.json" '.delegated.summary_json | endswith("/load-src/summary.json")' "delegated-failure-summary-suffix"
if [ -e "$run_delegated_failure_root/load-src/summary.json" ]; then
  printf 'delegated load-src summary.json unexpectedly exists\n' >&2
  cat "$run_delegated_failure_root/summary.json" >&2
  exit 1
fi

repo_conflict="$tmpdir/repo-conflict"
write_fixture_repo "$repo_conflict"
run_conflict_root="$tmpdir/run-conflict"
stderr_conflict="$tmpdir/run-conflict.stderr"
run_expect_failure "$repo_conflict" "$run_conflict_root" "$stderr_conflict" --bead bead-1 --work-item 1002
assert_stderr_contains "$stderr_conflict" "load-task-src requires exactly one selector"
