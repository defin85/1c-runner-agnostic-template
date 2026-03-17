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
cat >"$project_dir/.copier-answers.yml" <<'EOF'
_src_path: git@github.com:defin85/1c-runner-agnostic-template.git
_commit: v0.1.1
EOF
git -C "$project_dir" add .copier-answers.yml
git -C "$project_dir" commit -qm "seed answers"

cat >"$bindir/copier" <<EOF
#!/usr/bin/env bash
set -euo pipefail
{
  printf 'cwd=%s\n' "\$PWD"
  printf '%s\n' "\$@"
} >"$tmpdir/copier-call.txt"
EOF

chmod +x "$bindir/copier"

assert_has_line() {
  local expected="$1"

  if ! grep -Fx -- "$expected" "$tmpdir/copier-call.txt" >/dev/null 2>&1; then
    printf 'expected line not found: %s\n' "$expected" >&2
    printf 'actual call:\n' >&2
    cat "$tmpdir/copier-call.txt" >&2
    exit 1
  fi
}

PATH="$bindir:$PATH" "$HELPER" "$project_dir" --vcs-ref v0.1.1 --pretend --skip-answered --skip-tasks --conflict rej >/dev/null

assert_has_line "cwd=$PROJECT_ROOT"
assert_has_line "update"
assert_has_line "--trust"
assert_has_line "--defaults"
assert_has_line "--vcs-ref"
assert_has_line "v0.1.1"
assert_has_line "--pretend"
assert_has_line "--skip-answered"
assert_has_line "--skip-tasks"
assert_has_line "--conflict"
assert_has_line "rej"
assert_has_line "$project_dir"
