#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
HELPER="$PROJECT_ROOT/tooling/new-1c-project"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bindir="$tmpdir/bin"
workdir="$tmpdir/my-sample-project"
mkdir -p "$bindir" "$workdir"

cat >"$bindir/copier" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "\$@" >"$tmpdir/copier-args.txt"
EOF

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$bindir/copier" "$bindir/openspec"

assert_has_arg() {
  local log_file="$1"
  local expected="$2"

  if ! grep -Fx -- "$expected" "$log_file" >/dev/null 2>&1; then
    printf 'expected copier arg not found: %s\n' "$expected" >&2
    printf 'actual args:\n' >&2
    cat "$log_file" >&2
    exit 1
  fi
}

run_helper() {
  local cwd="$1"
  shift

  (
    cd "$cwd"
    PATH="$bindir:$PATH" "$HELPER" "$@" >/dev/null
  )
}

current_dir_log="$tmpdir/copier-current-dir.txt"
explicit_dir_log="$tmpdir/copier-explicit-dir.txt"

run_helper "$workdir" --defaults --no-git --no-beads
mv "$tmpdir/copier-args.txt" "$current_dir_log"

assert_has_arg "$current_dir_log" "project_name=my sample project"
assert_has_arg "$current_dir_log" "project_slug=my-sample-project"

run_helper "$tmpdir" "$tmpdir/other-sample-project" --defaults --no-git --no-beads
mv "$tmpdir/copier-args.txt" "$explicit_dir_log"

assert_has_arg "$explicit_dir_log" "project_name=other sample project"
assert_has_arg "$explicit_dir_log" "project_slug=other-sample-project"
