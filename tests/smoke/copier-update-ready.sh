#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

template_root="$tmpdir/template"
rendered_root="$tmpdir/rendered"
bindir="$tmpdir/bin"
command_log="$tmpdir/commands.log"

mkdir -p "$template_root" "$bindir"

copy_template_repo() {
  (
    cd "$SOURCE_ROOT"
    tar --exclude=.git -cf - .
  ) | (
    cd "$template_root"
    tar xf -
  )
}

init_git_repo() {
  local root="$1"
  local message="$2"

  git -C "$root" init -q
  git -C "$root" config user.name "Smoke Test"
  git -C "$root" config user.email "smoke@example.com"
  git -C "$root" add -A
  git -C "$root" commit -qm "$message"
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

assert_not_exists() {
  local path="$1"

  if [ -e "$path" ]; then
    printf 'path should not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_exists() {
  local path="$1"

  if [ ! -e "$path" ]; then
    printf 'path does not exist: %s\n' "$path" >&2
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
    printf 'actual log contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

copy_template_repo

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'openspec %s\n' "$*" >>"$COMMAND_LOG"

if [ "$#" -ne 3 ] || [ "$1" != "init" ] || [ "$2" != "--tools" ]; then
  printf 'unexpected openspec args: %s\n' "$*" >&2
  exit 1
fi

cat >AGENTS.md <<'EOT'
<!-- OPENSPEC:START -->
# OpenSpec Instructions
<!-- OPENSPEC:END -->
EOT
EOF

cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'bd %s\n' "$*" >>"$COMMAND_LOG"

if [ "$1" = "init" ]; then
  mkdir -p .beads
fi
EOF

chmod +x "$bindir/openspec" "$bindir/bd"

init_git_repo "$template_root" "template v0.1.0"
git -C "$template_root" tag v0.1.0

PATH="$bindir:$PATH" COMMAND_LOG="$command_log" copier copy --trust --defaults \
  -d project_name="Smoke Project" \
  -d project_slug="smoke-project" \
  "$template_root" \
  "$rendered_root" \
  >/dev/null

assert_exists "$rendered_root/.copier-answers.yml"
assert_not_exists "$rendered_root/{{ _copier_conf.answers_file }}"
assert_exists "$rendered_root/.codex/.gitkeep"
assert_exists "$rendered_root/.codex/config.toml"
assert_exists "$rendered_root/.claude/settings.json"
assert_exists "$rendered_root/.claude/skills/README.md"
assert_exists "$rendered_root/.claude/skills/1c-doctor/SKILL.md"
assert_exists "$rendered_root/.github/workflows/ci.yml"
assert_exists "$rendered_root/scripts/lib/capability.sh"
assert_exists "$rendered_root/scripts/platform/dump-src.sh"
assert_exists "$rendered_root/scripts/platform/diff-src.sh"
assert_exists "$rendered_root/scripts/diag/doctor.sh"
assert_exists "$rendered_root/tests/smoke/runtime-capability-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-doctor-contract.sh"
assert_not_exists "$rendered_root/PROJECT_RULES.md"
assert_not_exists "$rendered_root/openspec"
assert_not_exists "$rendered_root/CLAUDE.md"
assert_not_exists "$rendered_root/.claude/commands/openspec"
assert_exists "$rendered_root/scripts/template/update-template.sh"
assert_exists "$rendered_root/scripts/template/check-update.sh"
assert_contains "$rendered_root/Makefile" "template-update:"
assert_contains "$rendered_root/.gitignore" ".codex/*"
assert_contains "$rendered_root/.gitignore" "!.codex/.gitkeep"
assert_contains "$rendered_root/.gitignore" "!.codex/config.toml"
assert_contains "$rendered_root/.codex/config.toml" "mcp_servers.claude-context"
assert_contains "$rendered_root/.codex/config.toml" "mcp_servers.chrome-devtools"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: CI"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Runtime doctor"

assert_count "$command_log" "openspec init --tools none" "1"
assert_count "$command_log" "bd init --stealth -p smoke-project" "1"

git -C "$rendered_root" config user.name "Smoke Test"
git -C "$rendered_root" config user.email "smoke@example.com"
git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "generated v0.1.0"

cat >"$template_root/docs/template-update-note.txt" <<'EOF'
This file is added in template v0.2.0 to verify copier update.
EOF

python - <<PY
from pathlib import Path

path = Path("$template_root/scripts/bootstrap/agents-overlay.sh")
old = "6. Do not treat TODO/checklist/status files as proof of implementation.\\n\\n## Landing the Plane\\n"
new = "6. Do not treat TODO/checklist/status files as proof of implementation.\\n7. Refresh managed AGENTS overlays during template updates.\\n\\n## Landing the Plane\\n"
text = path.read_text()
if old not in text:
    raise SystemExit("overlay marker not found")
path.write_text(text.replace(old, new, 1))
PY

git -C "$template_root" add -A
git -C "$template_root" commit -qm "template v0.2.0"
git -C "$template_root" tag v0.2.0

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" ./scripts/template/update-template.sh >/dev/null
)

assert_exists "$rendered_root/docs/template-update-note.txt"
assert_contains "$rendered_root/AGENTS.md" "Refresh managed AGENTS overlays during template updates."
assert_contains "$rendered_root/.gitignore" ".codex/*"
assert_exists "$rendered_root/.claude/settings.json"
assert_exists "$rendered_root/.claude/skills/1c-doctor/SKILL.md"
assert_exists "$rendered_root/.github/workflows/ci.yml"
assert_exists "$rendered_root/scripts/lib/capability.sh"
assert_exists "$rendered_root/scripts/platform/dump-src.sh"
assert_exists "$rendered_root/scripts/platform/diff-src.sh"
assert_exists "$rendered_root/scripts/diag/doctor.sh"
assert_not_exists "$rendered_root/PROJECT_RULES.md"
assert_not_exists "$rendered_root/openspec"
assert_not_exists "$rendered_root/CLAUDE.md"
assert_not_exists "$rendered_root/.claude/commands/openspec"
assert_count "$command_log" "openspec init --tools none" "1"
assert_count "$command_log" "bd init --stealth -p smoke-project" "1"
