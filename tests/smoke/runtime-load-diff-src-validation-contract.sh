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

assert_exists() {
  local path="$1"

  if [ ! -e "$path" ]; then
    printf 'expected path to exist: %s\n' "$path" >&2
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

create_minimal_path() {
  local target_dir="$1"
  shift
  local tool=""

  mkdir -p "$target_dir"
  for tool in "$@"; do
    ln -s "$(command -v "$tool")" "$target_dir/$tool"
  done
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

  run_expect_failure_with_args \
    "$repo_root" \
    "$stderr_path" \
    --profile env/local.json \
    --run-root "$run_root"
}

run_expect_failure_with_args() {
  local repo_root="$1"
  local stderr_path="$2"
  shift 2
  local status=0

  set +e
  (
    cd "$repo_root"
    ./scripts/platform/load-diff-src.sh "$@" >/dev/null
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

repo_cli_guard="$tmpdir/repo-cli-guard"
write_fixture_repo "$repo_cli_guard"
run_cli_guard_root="$tmpdir/run-cli-guard"
stderr_cli_guard="$tmpdir/run-cli-guard.stderr"
run_expect_failure_with_args \
  "$repo_cli_guard" \
  "$stderr_cli_guard" \
  --profile env/local.json \
  --run-root "$run_cli_guard_root" \
  --files "Catalogs/Items.xml"
assert_stderr_contains "$stderr_cli_guard" "load-diff-src derives file selection internally; --files is not supported"
assert_exists "$run_cli_guard_root/summary.json"
assert_jq "$run_cli_guard_root/summary.json" '.status == "failed"' "cli-guard-status"
assert_jq "$run_cli_guard_root/summary.json" '.selection.selected_files == []' "cli-guard-selected-empty"
assert_jq "$run_cli_guard_root/summary.json" '.selection.error == "load-diff-src derives file selection internally; --files is not supported"' "cli-guard-error"
assert_jq "$run_cli_guard_root/summary.json" '.delegated == null' "cli-guard-no-delegation"

repo_missing_profile="$tmpdir/repo-missing-profile"
write_fixture_repo "$repo_missing_profile"
run_missing_profile_root="$tmpdir/run-missing-profile"
stderr_missing_profile="$tmpdir/run-missing-profile.stderr"
run_expect_failure_with_args \
  "$repo_missing_profile" \
  "$stderr_missing_profile" \
  --profile env/missing.json \
  --run-root "$run_missing_profile_root"
assert_stderr_contains "$stderr_missing_profile" "runtime profile not found:"
assert_exists "$run_missing_profile_root/summary.json"
assert_jq "$run_missing_profile_root/summary.json" '.status == "failed"' "missing-profile-status"
assert_jq "$run_missing_profile_root/summary.json" '.selection.error | startswith("runtime profile not found: ")' "missing-profile-error"
assert_jq "$run_missing_profile_root/summary.json" '.delegated == null' "missing-profile-no-delegation"

repo_invalid_profile="$tmpdir/repo-invalid-profile"
write_fixture_repo "$repo_invalid_profile"
printf '[]\n' >"$repo_invalid_profile/env/invalid.json"
run_invalid_profile_root="$tmpdir/run-invalid-profile"
stderr_invalid_profile="$tmpdir/run-invalid-profile.stderr"
run_expect_failure_with_args \
  "$repo_invalid_profile" \
  "$stderr_invalid_profile" \
  --profile env/invalid.json \
  --run-root "$run_invalid_profile_root"
assert_stderr_contains "$stderr_invalid_profile" "runtime profile root must be an object:"
assert_exists "$run_invalid_profile_root/summary.json"
assert_jq "$run_invalid_profile_root/summary.json" '.status == "failed"' "invalid-profile-status"
assert_jq "$run_invalid_profile_root/summary.json" '.selection.error | startswith("runtime profile root must be an object: ")' "invalid-profile-error"
assert_jq "$run_invalid_profile_root/summary.json" '.delegated == null' "invalid-profile-no-delegation"

repo_missing_git="$tmpdir/repo-missing-git"
write_fixture_repo "$repo_missing_git"
run_missing_git_root="$tmpdir/run-missing-git"
stderr_missing_git="$tmpdir/run-missing-git.stderr"
missing_git_path="$tmpdir/path-no-git"
create_minimal_path "$missing_git_path" dirname realpath mkdir date jq
set +e
(
  cd "$repo_missing_git"
  PATH="$missing_git_path" "$BASH" ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$run_missing_git_root" >/dev/null
) 2>"$stderr_missing_git"
status=$?
set -e
if [ "$status" -eq 0 ]; then
  printf 'load-diff-src unexpectedly succeeded without git in PATH\n' >&2
  exit 1
fi
assert_stderr_contains "$stderr_missing_git" "command not found: git"
assert_exists "$run_missing_git_root/summary.json"
assert_jq "$run_missing_git_root/summary.json" '.status == "failed"' "missing-git-status"
assert_jq "$run_missing_git_root/summary.json" '.selection.error == "command not found: git"' "missing-git-error"
assert_jq "$run_missing_git_root/summary.json" '.delegated == null' "missing-git-no-delegation"

repo_missing_jq="$tmpdir/repo-missing-jq"
write_fixture_repo "$repo_missing_jq"
run_missing_jq_root="$tmpdir/run-missing-jq"
stderr_missing_jq="$tmpdir/run-missing-jq.stderr"
missing_jq_path="$tmpdir/path-no-jq"
create_minimal_path "$missing_jq_path" dirname realpath mkdir date git
set +e
(
  cd "$repo_missing_jq"
  PATH="$missing_jq_path" "$BASH" ./scripts/platform/load-diff-src.sh --profile env/local.json --run-root "$run_missing_jq_root" >/dev/null
) 2>"$stderr_missing_jq"
status=$?
set -e
if [ "$status" -eq 0 ]; then
  printf 'load-diff-src unexpectedly succeeded without jq in PATH\n' >&2
  exit 1
fi
assert_stderr_contains "$stderr_missing_jq" "command not found: jq"
assert_exists "$run_missing_jq_root/summary.json"
assert_jq "$run_missing_jq_root/summary.json" '.status == "failed"' "missing-jq-status"
assert_jq "$run_missing_jq_root/summary.json" '.selection.error == "command not found: jq"' "missing-jq-error"
assert_jq "$run_missing_jq_root/summary.json" '.delegated == null' "missing-jq-no-delegation"
