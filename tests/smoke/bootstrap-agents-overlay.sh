#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

project_root="$tmpdir/project"
bindir="$tmpdir/bin"
bd_log="$tmpdir/bd.log"

mkdir -p "$project_root/scripts/bootstrap" "$project_root/scripts/lib" "$bindir"
git init -q "$project_root" >/dev/null 2>&1

cp "$SOURCE_ROOT/scripts/bootstrap/agents-overlay.sh" "$project_root/scripts/bootstrap/agents-overlay.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/copier-post-copy.sh" "$project_root/scripts/bootstrap/copier-post-copy.sh"
cp "$SOURCE_ROOT/scripts/lib/common.sh" "$project_root/scripts/lib/common.sh"

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ] || [ "$1" != "init" ] || [ "$2" != "--tools" ]; then
  printf 'unexpected openspec args: %s\n' "$*" >&2
  exit 1
fi

if [ ! -f AGENTS.md ]; then
  cat >AGENTS.md <<'EOT'
<!-- OPENSPEC:START -->
# OpenSpec Instructions
<!-- OPENSPEC:END -->
EOT
fi
EOF

cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$BD_LOG"
EOF

chmod +x "$bindir/openspec" "$bindir/bd"

run_bootstrap() {
  (
    cd "$project_root"
    PATH="$bindir:$PATH" BD_LOG="$bd_log" bash ./scripts/bootstrap/copier-post-copy.sh \
      "Sample Project" \
      "sample-project" \
      "direct-platform" \
      "none" \
      "no" \
      "yes" \
      "sample-project" \
      >/dev/null
  )
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_count() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local actual_count

  actual_count="$(grep -Fc -- "$pattern" "$file" || true)"
  if [ "$actual_count" != "$expected_count" ]; then
    printf 'unexpected count for %s: expected %s, got %s\n' "$pattern" "$expected_count" "$actual_count" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_bootstrap
run_bootstrap

agents_file="$project_root/AGENTS.md"

assert_contains "$agents_file" "We operate in a cycle: **OpenSpec (What) -> Beads (How) -> Code (Implementation)**."
assert_contains "$agents_file" 'Do not move to production code for new or major changes without explicit approval. Canonical signal: `Go!`.'
assert_contains "$agents_file" 'Use `bd` as the source of truth for code-change tracking.'
assert_contains "$agents_file" 'Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.'
assert_contains "$agents_file" '1. `mcp__claude-context__search_code`, if available in the current environment'
assert_contains "$agents_file" 'A session with code changes is not complete until `git push` succeeds.'
assert_count "$agents_file" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->" "1"
