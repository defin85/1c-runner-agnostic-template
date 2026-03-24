#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
HELPER="$PROJECT_ROOT/tooling/update-1c-project"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bindir="$tmpdir/bin"
project_dir="$tmpdir/sample-project"
mkdir -p "$bindir" "$project_dir"

git -C "$project_dir" init -q
git -C "$project_dir" config user.name "Smoke Test"
git -C "$project_dir" config user.email "smoke@example.com"
mkdir -p "$project_dir/scripts/template"
cat >"$project_dir/scripts/template/update-template.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
{
  printf 'cwd=%s\n' "$PWD"
  printf '%s\n' "$@"
} >"$UPDATE_LOG"
EOF
chmod +x "$project_dir/scripts/template/update-template.sh"
git -C "$project_dir" add scripts/template/update-template.sh
git -C "$project_dir" commit -qm "seed generated repo"

update_log="$tmpdir/update-call.txt"

assert_has_line() {
  local expected="$1"

  if ! grep -Fx -- "$expected" "$update_log" >/dev/null 2>&1; then
    printf 'expected line not found: %s\n' "$expected" >&2
    printf 'actual call:\n' >&2
    cat "$update_log" >&2
    exit 1
  fi
}

UPDATE_LOG="$update_log" "$HELPER" "$project_dir" --vcs-ref v0.1.1 --pretend >/dev/null

assert_has_line "cwd=$project_dir"
assert_has_line "--vcs-ref"
assert_has_line "v0.1.1"
assert_has_line "--pretend"
