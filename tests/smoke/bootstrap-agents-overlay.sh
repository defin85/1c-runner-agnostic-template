#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

project_root="$tmpdir/project"
bindir="$tmpdir/bin"
bd_log="$tmpdir/bd.log"

mkdir -p "$project_root/scripts/bootstrap" "$project_root/scripts/lib" "$project_root/scripts/llm" "$bindir"
git init -q "$project_root" >/dev/null 2>&1

cp "$SOURCE_ROOT/scripts/bootstrap/agents-overlay.sh" "$project_root/scripts/bootstrap/agents-overlay.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/copier-post-copy.sh" "$project_root/scripts/bootstrap/copier-post-copy.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/generated-project-surface.sh" "$project_root/scripts/bootstrap/generated-project-surface.sh"
cp "$SOURCE_ROOT/scripts/lib/common.sh" "$project_root/scripts/lib/common.sh"
cp "$SOURCE_ROOT/scripts/llm/export-context.sh" "$project_root/scripts/llm/export-context.sh"

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
      "$SOURCE_ROOT" \
      "Sample Project" \
      "sample-project" \
      "Тестовый generated проект" \
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

assert_next_line() {
  local file="$1"
  local expected_current="$2"
  local expected_next="$3"

  if ! awk -v expected_current="$expected_current" -v expected_next="$expected_next" '
    $0 == expected_current {
      found = 1
      if (getline next_line <= 0) {
        exit 2
      }
      if (next_line != expected_next) {
        exit 1
      }
      exit 0
    }
    END {
      if (!found) {
        exit 3
      }
    }
  ' "$file"; then
    printf 'expected "%s" to be followed immediately by "%s"\n' "$expected_current" "$expected_next" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_bootstrap
run_bootstrap

agents_file="$project_root/AGENTS.md"
readme_file="$project_root/README.md"
project_map_file="$project_root/automation/context/project-map.md"
metadata_index_file="$project_root/automation/context/metadata-index.generated.json"
source_tree_file="$project_root/automation/context/source-tree.generated.txt"
openspec_project_file="$project_root/openspec/project.md"

assert_contains "$agents_file" "We operate in a cycle: **OpenSpec (What) -> Beads (How) -> Code (Implementation)**."
assert_contains "$agents_file" 'This repository is a generated 1С-project created from `1c-runner-agnostic-template`.'
assert_contains "$agents_file" 'Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) for the generated-project-first onboarding path.'
assert_contains "$agents_file" 'Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.'
assert_contains "$agents_file" 'Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.'
assert_contains "$agents_file" 'Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.'
assert_contains "$agents_file" 'Use [docs/exec-plans/README.md](docs/exec-plans/README.md) for long-running or multi-session work.'
assert_contains "$agents_file" 'Do not move to production code for new or major changes without explicit approval. Canonical signal: `Go!`.'
assert_contains "$agents_file" 'Use `bd` as the source of truth for code-change tracking.'
assert_contains "$agents_file" 'Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.'
assert_contains "$agents_file" '1. `mcp__claude-context__search_code`, if available in the current environment'
assert_contains "$agents_file" 'A session with code changes is not complete until `git push` succeeds.'
assert_count "$agents_file" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->" "1"
assert_next_line "$agents_file" "<!-- OPENSPEC:END -->" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"

assert_contains "$readme_file" "<!-- RUNNER_AGNOSTIC_PROJECT:START -->"
assert_contains "$readme_file" "generated 1С-проект"
assert_contains "$readme_file" "[automation/context/project-map.md](automation/context/project-map.md)"
assert_contains "$readme_file" "[docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md)"
assert_contains "$readme_file" "[docs/template-maintenance.md](docs/template-maintenance.md)"
assert_contains "$project_map_file" "Ownership Model"
assert_contains "$project_map_file" "generated-derived"
assert_contains "$openspec_project_file" "generated 1С-проект"
assert_contains "$metadata_index_file" "\"inventoryRole\": \"generated-derived\""
assert_contains "$source_tree_file" "# Generated Project Tree"
