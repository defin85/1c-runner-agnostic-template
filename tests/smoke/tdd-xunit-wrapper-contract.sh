#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

create_fixture_repo() {
  local root="$1"
  local invocation_log="$2"

  mkdir -p "$root"
  cp -R "$SOURCE_ROOT/scripts" "$root/scripts"
  mkdir -p "$root/env" "$root/src/cf/Catalogs"

  cat >"$root/env/local.json" <<'EOF'
{
  "schemaVersion": 2,
  "profileName": "tdd-xunit-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "/tmp/fake-1cv8"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/tdd-xunit-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {}
}
EOF

  cat >"$root/scripts/platform/load-diff-src.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

run_root=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-root)
      run_root="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

mkdir -p "$run_root"
printf 'load-diff-src\n' >>"$WRAPPER_INVOCATION_LOG"
printf '{"status":"success"}\n' >"$run_root/summary.json"
EOF

  cat >"$root/scripts/platform/update-db.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

run_root=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-root)
      run_root="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

mkdir -p "$run_root"
printf 'update-db\n' >>"$WRAPPER_INVOCATION_LOG"
printf '{"status":"success"}\n' >"$run_root/summary.json"
EOF

  cat >"$root/scripts/test/run-xunit.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

run_root=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-root)
      run_root="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

mkdir -p "$run_root"
printf 'run-xunit\n' >>"$WRAPPER_INVOCATION_LOG"
printf '{"status":"success"}\n' >"$run_root/summary.json"
EOF

  chmod +x \
    "$root/scripts/platform/load-diff-src.sh" \
    "$root/scripts/platform/update-db.sh" \
    "$root/scripts/test/run-xunit.sh"

  printf '<items baseline />\n' >"$root/src/cf/Catalogs/Items.xml"

  (
    cd "$root"
    git init >/dev/null
    git config user.name "Smoke Fixture"
    git config user.email "smoke@example.invalid"
    git add .
    git commit -m "fixture baseline" >/dev/null
  )

  : >"$invocation_log"
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_file_equals() {
  local file="$1"
  local expected="$2"
  local diff_file="$tmpdir/assert-file-equals.diff"

  if ! diff -u <(printf '%s' "$expected") "$file" >"$diff_file"; then
    printf 'unexpected file contents: %s\n' "$file" >&2
    cat "$diff_file" >&2
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

modified_root="$tmpdir/modified"
modified_log="$tmpdir/modified.log"
create_fixture_repo "$modified_root" "$modified_log"
printf '<items modified />\n' >"$modified_root/src/cf/Catalogs/Items.xml"

(
  cd "$modified_root"
  WRAPPER_INVOCATION_LOG="$modified_log" ./scripts/test/tdd-xunit.sh --profile env/local.json --run-root "$tmpdir/modified-run" >/dev/null
)

assert_file_equals "$modified_log" $'load-diff-src\nupdate-db\nrun-xunit\n'
assert_jq "$tmpdir/modified-run/summary.json" '.status == "success"' "modified-status"
assert_jq "$tmpdir/modified-run/summary.json" '.sync.required == true' "modified-sync-required"
assert_jq "$tmpdir/modified-run/summary.json" '.sync.action == "load-diff-src-and-update-db"' "modified-sync-action"

clean_root="$tmpdir/clean"
clean_log="$tmpdir/clean.log"
create_fixture_repo "$clean_root" "$clean_log"

(
  cd "$clean_root"
  WRAPPER_INVOCATION_LOG="$clean_log" ./scripts/test/tdd-xunit.sh --profile env/local.json --run-root "$tmpdir/clean-run" >/dev/null
)

assert_file_equals "$clean_log" $'run-xunit\n'
assert_jq "$tmpdir/clean-run/summary.json" '.status == "success"' "clean-status"
assert_jq "$tmpdir/clean-run/summary.json" '.sync.required == false' "clean-sync-skipped"
assert_jq "$tmpdir/clean-run/summary.json" '.sync.action == "skip-clean-src-cf"' "clean-sync-action"

deleted_root="$tmpdir/deleted"
deleted_log="$tmpdir/deleted.log"
create_fixture_repo "$deleted_root" "$deleted_log"
rm "$deleted_root/src/cf/Catalogs/Items.xml"

set +e
(
  cd "$deleted_root"
  WRAPPER_INVOCATION_LOG="$deleted_log" ./scripts/test/tdd-xunit.sh --profile env/local.json --run-root "$tmpdir/deleted-run" >"$tmpdir/deleted.stdout" 2>"$tmpdir/deleted.stderr"
)
status=$?
set -e

if [ "$status" -ne 65 ]; then
  printf 'unexpected exit code for delete-only delta: %s\n' "$status" >&2
  exit 1
fi

assert_file_equals "$deleted_log" ""
assert_contains "$tmpdir/deleted.stderr" "load-src.sh -> ./scripts/platform/update-db.sh -> ./scripts/test/run-xunit.sh manually"
assert_jq "$tmpdir/deleted-run/summary.json" '.status == "failed"' "deleted-status"
assert_jq "$tmpdir/deleted-run/summary.json" '.sync.action == "unsupported-delta-shape"' "deleted-sync-action"
assert_jq "$tmpdir/deleted-run/summary.json" '.sync.unsupported_cf_changes | length == 1' "deleted-unsupported-count"
