#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

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

valid_message="$tmpdir/valid-message.txt"
invalid_message="$tmpdir/invalid-message.txt"
rendered="$tmpdir/rendered.txt"
repo_root="$tmpdir/repo"

cat >"$valid_message" <<'EOF'
Implement task-scoped load wrapper

Bead: do-rolf-sdd-jiy.3
Work-Item: 93984
EOF

cat >"$invalid_message" <<'EOF'
Invalid task trailers

Bead:
Work-Item: 93984
Work-Item: 93984-dup
EOF

"$SOURCE_ROOT/scripts/git/task-trailers.sh" render --bead do-rolf-sdd-jiy.3 --work-item 93984 >"$rendered"
assert_contains "$rendered" "Bead: do-rolf-sdd-jiy.3"
assert_contains "$rendered" "Work-Item: 93984"

"$SOURCE_ROOT/scripts/git/task-trailers.sh" validate-message --file "$valid_message" --require-any

set +e
"$SOURCE_ROOT/scripts/git/task-trailers.sh" validate-message --file "$invalid_message" --require-any >"$tmpdir/invalid.stdout" 2>"$tmpdir/invalid.stderr"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  printf 'validate-message unexpectedly succeeded for invalid message\n' >&2
  exit 1
fi

assert_contains "$tmpdir/invalid.stderr" "empty value for trailer: Bead"
assert_not_contains "$tmpdir/invalid.stderr" "unexpected success"

mkdir -p "$repo_root"
cp -R "$SOURCE_ROOT/scripts" "$repo_root/scripts"
mkdir -p "$repo_root/src/cf/Catalogs"
printf '<items baseline />\n' >"$repo_root/src/cf/Catalogs/Items.xml"

(
  cd "$repo_root"
  git init >/dev/null
  git config user.name "Smoke Fixture"
  git config user.email "smoke@example.invalid"
  git add .
  git commit -m "baseline" >/dev/null
)

printf '<items changed />\n' >"$repo_root/src/cf/Catalogs/Items.xml"
(
  cd "$repo_root"
  git add src/cf/Catalogs/Items.xml
  git commit -m $'task change\n\nBead: do-rolf-sdd-jiy.3\nWork-Item: 93984' >/dev/null
)

printf '<items malformed />\n' >"$repo_root/src/cf/Catalogs/Items.xml"
(
  cd "$repo_root"
  git add src/cf/Catalogs/Items.xml
  git commit -m $'unrelated malformed task\n\nBead: malformed.1\nBead: malformed.2\nWork-Item: 77777' >/dev/null
)

"$SOURCE_ROOT/scripts/git/task-trailers.sh" select-commits --repo "$repo_root" --bead do-rolf-sdd-jiy.3 >"$tmpdir/selected-commits.txt"
assert_contains "$tmpdir/selected-commits.txt" "$(git -C "$repo_root" rev-parse HEAD~1)"
