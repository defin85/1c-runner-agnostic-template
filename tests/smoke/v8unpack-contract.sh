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

if ./scripts/platform/v8unpack.sh extract --tool "$fake_v8unpack" --input "$source_file" --dry-run >/dev/null 2>"$tmpdir/missing-output.stderr"; then
  printf 'extract without --output unexpectedly succeeded\n' >&2
  exit 1
fi
assert_contains "$tmpdir/missing-output.stderr" "--output is required for extract"
