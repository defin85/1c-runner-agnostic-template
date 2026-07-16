#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
fake_bin="$tmpdir/bin"
state_root="$tmpdir/state"
invocation_log="$tmpdir/stage-invocations.log"
profile_path="$fixture_root/env/local.json"
sync_run_root="$tmpdir/sync-run"
target_sync_run_root="$tmpdir/target-sync-run"
empty_run_root="$tmpdir/empty-run"
failed_run_root="$tmpdir/failed-run"
no_filter_run_root="$tmpdir/no-filter-run"

mkdir -p "$fixture_root" "$fake_bin" "$state_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fixture_root/env" \
  "$fixture_root/src/cfe/Smoke" \
  "$tmpdir/file-ib"

printf '%s\n' "smoke-source" >"$fixture_root/src/cfe/Smoke/marker.txt"

cat >"$fake_bin/1cv8" <<'EOF'
#!/usr/bin/env bash
printf '1cv8 should not be used directly\n' >&2
exit 99
EOF

cat >"$fake_bin/1cv8c" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

config=""
out=""
read_next_c_payload=0
for arg in "$@"; do
  if [ "$read_next_c_payload" = "1" ]; then
    case "$arg" in
      RunUnitTests=*)
        config="${arg#RunUnitTests=}"
        ;;
    esac
    read_next_c_payload=0
    continue
  fi

  case "$arg" in
    /CRunUnitTests=*)
      config="${arg#/CRunUnitTests=}"
      ;;
    /C)
      read_next_c_payload=1
      ;;
    /out*)
      out="${arg#/out}"
      ;;
  esac
done

[ -n "$config" ] || { printf 'missing RunUnitTests config\n' >&2; exit 41; }
[ -f "$config" ] || { printf 'config not found: %s\n' "$config" >&2; exit 42; }

exit_code_path="$(jq -r '.exitCode' "$config")"
junit_path="$(jq -r '.reports[] | select(.format == "jUnit") | .path' "$config")"
json_path="$(jq -r '.reports[] | select(.format == "dumpjson") | .path' "$config")"
allure_dir="$(jq -r '.reports[] | select(.format == "allure") | .path' "$config")"
if jq -e '(.filter.extensions // []) | index("Empty")' "$config" >/dev/null; then
  test_count=0
elif jq -e '(.filter.extensions // []) | index("Fail")' "$config" >/dev/null; then
  test_count=1
else
  test_count=1
fi

mkdir -p "$(dirname -- "$exit_code_path")" "$(dirname -- "$junit_path")" "$(dirname -- "$json_path")" "$allure_dir"
printf '<testsuites tests="%s" failures="0"></testsuites>\n' "$test_count" >"$junit_path"
if [ "$test_count" = "0" ]; then
  printf '[{"НаборыТестов":[]}]\n' >"$json_path"
  printf '[{"НаборыТестов":[{"Тесты":[{"Имя":"fixture","Метод":"fixture","Статус":"Failed"}]}]}]\n' >"$json_path"
else
  printf '[{"НаборыТестов":[{"Тесты":[{"Имя":"fixture","Метод":"fixture","Статус":"Passed"}]}]}]\n' >"$json_path"
fi
printf '{"uuid":"fixture"}\n' >"$allure_dir/fixture-result.json"
if [ -n "$out" ]; then
  mkdir -p "$(dirname -- "$out")"
  printf 'fake 1cv8c run\n' >"$out"
fi
EOF

cat >"$fake_bin/ibcmd" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

chmod +x "$fake_bin/1cv8" "$fake_bin/1cv8c" "$fake_bin/ibcmd"

write_stage_stub() {
  local path="$1"
  cat >"$path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

args=("$@")
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

[ -n "$run_root" ] || { printf 'missing --run-root\n' >&2; exit 64; }
mkdir -p "$run_root"
jq -n --arg status success --arg stage "$(basename -- "$0")" '{
  status: $status,
  stage: $stage,
  failure: null
}' >"$run_root/summary.json"
EOF
  chmod +x "$path"
}

write_stage_stub "$fixture_root/scripts/platform/load-cfe.sh"
write_stage_stub "$fixture_root/scripts/platform/configure-cfe-runtime-flags.sh"
write_stage_stub "$fixture_root/scripts/platform/check-cfe-applicability.sh"
write_stage_stub "$fixture_root/scripts/platform/check-cfe-config.sh"
write_stage_stub "$fixture_root/scripts/platform/update-db.sh"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_bin/1cv8",
    "ibcmdPath": "$fake_bin/ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/file-ib",
    "auth": {
      "mode": "os"
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/ibcmd-data"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/file-ib"
    }
  },
  "capabilities": {
    "updateDb": {
      "driver": "ibcmd"
    }
  }
}
EOF

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

  if ! jq -e "$expr" "$file" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

: >"$invocation_log"
(
  cd "$fixture_root"
)

assert_jq "$sync_run_root/summary.json" '.status == "success"' "sync-status"

(
  cd "$fixture_root"
)
assert_contains "$invocation_log" "update-db.sh --profile $profile_path --run-root $target_sync_run_root/update-db --target ut22"
assert_jq "$target_sync_run_root/summary.json" '.status == "success"' "target-sync-status"

(
  cd "$fixture_root"
)

assert_jq "$run_root/summary.json" '.status == "success"' "run-status"
assert_jq "$run_root/summary.json" '.classification == "success"' "run-classification"
assert_jq "$run_root/summary.json" '.sync.status == "current"' "run-sync-current"

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 2 ]; then
  printf 'unexpected empty-run exit code: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$empty_run_root/summary.json" '.status == "failed"' "empty-status"
assert_jq "$empty_run_root/summary.json" '.classification == "tests empty"' "empty-classification"

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 1 ]; then
  printf 'unexpected failed-run exit code: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$failed_run_root/summary.json" '.status == "failed"' "failed-status"
assert_jq "$failed_run_root/summary.json" '.classification == "tests failed"' "failed-classification"

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 64 ]; then
  printf 'unexpected no-filter exit code: %s\n' "$status" >&2
  exit 1
fi

assert_jq "$no_filter_run_root/summary.json" '.status == "failed"' "no-filter-status"
assert_jq "$no_filter_run_root/summary.json" '.classification == "config failed"' "no-filter-classification"
