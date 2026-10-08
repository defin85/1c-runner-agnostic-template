#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
fake_v8unpack="$tmpdir/v8unpack"
run_extract="$tmpdir/run-extract"
run_build="$tmpdir/run-build"
run_index="$tmpdir/run-index"
run_container="$tmpdir/run-container"
source_file="$tmpdir/input.cf"
source_dir="$tmpdir/source"
output_file="$tmpdir/output.cf"
output_dir="$tmpdir/output"

mkdir -p "$fixture_root" "$source_dir"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
printf 'fake cf\n' >"$source_file"

cat >"$fake_v8unpack" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'tmpdir=%s\n' "${TMPDIR:-}"
printf '%s\n' "$@"
EOF
chmod +x "$fake_v8unpack"

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

(
  cd "$fixture_root"
  ./scripts/platform/v8unpack.sh extract \
    --tool "$fake_v8unpack" \
    --input "$source_file" \
    --output "$output_dir" \
    --run-root "$run_extract" >/dev/null
)
assert_jq "$run_extract/summary.json" '.status == "success" and .action == "extract" and .exit_code == 0' "extract-summary"
assert_contains "$run_extract/command.txt" "-E"
assert_contains "$run_extract/command.txt" "$source_file"
assert_contains "$run_extract/command.txt" "$output_dir"
assert_contains "$run_extract/stdout.log" "-E"

(
  cd "$fixture_root"
  ./scripts/platform/v8unpack.sh build \
    --tool "$fake_v8unpack" \
    --input "$source_dir" \
    --output "$output_file" \
    --run-root "$run_build" \
    --extra-arg "--auto_include" >/dev/null
)
assert_jq "$run_build/summary.json" '.status == "success" and .action == "build" and .output_path == $output' "build-summary" --arg output "$output_file"
assert_contains "$run_build/command.txt" "-B"
assert_contains "$run_build/command.txt" "--auto_include"
assert_contains "$run_build/stdout.log" "tmpdir=$run_build/tmp"

(
  cd "$fixture_root"
  ./scripts/platform/v8unpack.sh index \
    --tool "$fake_v8unpack" \
    --input "$source_dir" \
    --run-root "$run_index" \
    --dry-run >/dev/null
)
assert_jq "$run_index/summary.json" '.status == "dry-run" and .action == "index" and .output_path == null' "index-dry-run-summary"
assert_contains "$run_index/command.txt" "-I"

(
  cd "$fixture_root"
  ./scripts/platform/v8unpack.sh container-extract \
    --tool "$fake_v8unpack" \
    --input "$source_file" \
    --output "$output_dir" \
    --run-root "$run_container" \
    --dry-run >/dev/null
)
assert_jq "$run_container/summary.json" '.status == "dry-run" and .action == "container-extract"' "container-dry-run-summary"
assert_contains "$run_container/command.txt" "scripts/python/v8unpack_container.py"
assert_contains "$run_container/command.txt" "container-extract"
# The container round-trip needs the v8unpack Python package; the wrapper contract above does not.
container_python="${ONEC_PYTHON:-python3}"
if "$container_python" -c 'import v8unpack' >/dev/null 2>&1; then
  "$container_python" - "$SOURCE_ROOT/scripts/python/v8unpack_container.py" "$tmpdir" <<'PY'
import subprocess
import sys
from pathlib import Path

helper, work = Path(sys.argv[1]), Path(sys.argv[2])
raw = work / 'raw/0'
raw.mkdir(parents=True)
files = {'form': b'\xef\xbb\xbf{0,1}\r\n', 'module': b'\xef\xbb\xbf// module\r\n'}
for name, data in files.items():
    (raw / name).write_bytes(data)
for action, source, target in [('container-build', raw.parent, work / 'Form.bin'),
                               ('container-extract', work / 'Form.bin', work / 'decoded')]:
    subprocess.run([sys.executable, str(helper), action, '--input', str(source), '--output', str(target)], check=True)
assert {p.name: p.read_bytes() for p in (work / 'decoded/0').iterdir()} == files
PY
else
  printf 'v8unpack-contract: container round-trip skipped, v8unpack package is not installed for %s\n' "$container_python"
fi

if ./scripts/platform/v8unpack.sh extract --tool "$fake_v8unpack" --input "$source_file" --dry-run >/dev/null 2>"$tmpdir/missing-output.stderr"; then
  printf 'extract without --output unexpectedly succeeded\n' >&2
  exit 1
fi
assert_contains "$tmpdir/missing-output.stderr" "--output is required for extract"
