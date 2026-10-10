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

write_fixture_repo() {
  local repo_root="$1"
  local init_git="${2:-yes}"

  mkdir -p "$repo_root"
  cp -R "$SOURCE_ROOT/scripts" "$repo_root/scripts"
  # Python bytecode written while the fixture runs must not show up as a git change.
  printf '__pycache__/\n*.pyc\n' >"$repo_root/.gitignore"
  mkdir -p "$repo_root/env" "$repo_root/src/cf/Catalogs"

  cat >"$repo_root/env/local.json" <<EOF
{
  "schemaVersion": 3,
  "profileName": "load-diff-validation",
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
    "bdd": {
      "unsupportedReason": "bdd is outside this fixture"
    },
    "smoke": {
      "unsupportedReason": "smoke is outside this fixture"
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
assert_jq "$run_deleted_root/summary.json" '.selection.error == "no eligible changed files inside source tree"' "deleted-selection-error"
assert_stderr_contains "$stderr_deleted" "error: no eligible changed files inside source tree"
assert_stderr_contains "$run_deleted_root/stderr.log" "error: no eligible changed files inside source tree"
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
assert_jq "$run_outside_root/summary.json" '.selection.error == "no eligible changed files inside source tree"' "outside-selection-error"
assert_stderr_contains "$stderr_outside" "error: no eligible changed files inside source tree"
assert_stderr_contains "$run_outside_root/stderr.log" "error: no eligible changed files inside source tree"
assert_jq "$run_outside_root/summary.json" '.status == "failed"' "outside-status"
assert_jq "$run_outside_root/summary.json" '.selection.selected_files == []' "outside-selected-empty"
assert_jq "$run_outside_root/summary.json" '.selection.ignored_files == [{"path":"README.outside","reason":"outside-source-tree"}]' "outside-ignored"
assert_jq "$run_outside_root/summary.json" '.delegated == null' "outside-no-delegation"

repo_clean="$tmpdir/repo-clean"
write_fixture_repo "$repo_clean"
run_clean_root="$tmpdir/run-clean"
stderr_clean="$tmpdir/run-clean.stderr"
run_expect_failure "$repo_clean" "$run_clean_root" "$stderr_clean"
assert_jq "$run_clean_root/summary.json" '.selection.error == "no eligible changed files inside source tree"' "clean-selection-error"
assert_stderr_contains "$stderr_clean" "error: no eligible changed files inside source tree"
assert_stderr_contains "$run_clean_root/stderr.log" "error: no eligible changed files inside source tree"
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
assert_jq "$run_nongit_root/summary.json" '.status == "failed"' "nongit-status"
assert_jq "$run_nongit_root/summary.json" '.selection.error == "git-backed diff requires a git worktree"' "nongit-selection-error"
assert_jq "$run_nongit_root/summary.json" '.delegated == null' "nongit-no-delegation"
assert_stderr_contains "$stderr_nongit" "git-backed diff requires a git worktree"
assert_stderr_contains "$run_nongit_root/stderr.log" "git-backed diff requires a git worktree"

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
assert_jq "$run_cli_guard_root/summary.json" '.status == "failed" and .exit_code != 0' "cli-guard-status"
assert_jq "$run_cli_guard_root/summary.json" '.selection.selected_files == []' "cli-guard-selected-empty"
assert_jq "$run_cli_guard_root/summary.json" '.selection.error == "load-diff-src derives file selection internally; --files is not supported"' "cli-guard-error"
assert_jq "$run_cli_guard_root/summary.json" '.delegated == null' "cli-guard-no-delegation"
assert_stderr_contains "$run_cli_guard_root/stderr.log" "error: load-diff-src derives file selection internally; --files is not supported"

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

repo_legacy_profile="$tmpdir/repo-legacy-profile"
write_fixture_repo "$repo_legacy_profile"
jq '.schemaVersion = 2 | .runnerAdapter = "direct-platform"' "$repo_legacy_profile/env/local.json" >"$repo_legacy_profile/env/legacy.json"
run_legacy_profile_root="$tmpdir/run-legacy-profile"
stderr_legacy_profile="$tmpdir/run-legacy-profile.stderr"
run_expect_failure_with_args \
  "$repo_legacy_profile" \
  "$stderr_legacy_profile" \
  --profile env/legacy.json \
  --run-root "$run_legacy_profile_root"
assert_stderr_contains "$stderr_legacy_profile" "runtime profile schemaVersion=2 is no longer supported"
assert_jq "$run_legacy_profile_root/summary.json" '.status == "failed" and .delegated == null' "legacy-profile-status"
assert_jq "$run_legacy_profile_root/summary.json" '.selection.error | startswith("runtime profile schemaVersion=2 is no longer supported")' "legacy-profile-error"
