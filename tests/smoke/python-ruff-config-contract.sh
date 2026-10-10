#!/usr/bin/env bash
# Contract: ruff configuration is project-owned and extends the template base (design decision R18).
# - the seed ruff.toml only extends scripts/qa/ruff-base.toml, and python-lint.sh passes with it;
# - project extend-exclude and per-file-ignores work for project files, base excludes still apply;
# - python-lint.sh fails before ruff runs when ruff.toml drops the base or switches base rules off
#   for files from the template manifest;
# - a uv environment without ruff gives a fix command instead of uv's bare "Failed to spawn: ruff";
# - ruff.toml is seed-once: listed in the preserve contract and in both seed lists, not overlay-managed.
# Everything runs in a temporary copy, the working tree is never modified.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

fail() {
  printf 'python ruff config contract failed: %s\n' "$1" >&2
  exit 1
}

command -v uv >/dev/null 2>&1 || fail "uv is required to run this contract"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

repo="$tmpdir/repo"
mkdir -p "$repo"
(
  cd "$SOURCE_ROOT"
  git ls-files -z --cached --others --exclude-standard -- scripts | tar --null -T - -cf -
) | (cd "$repo" && tar xf -)
for file in pyproject.toml uv.lock requirements-dev.txt; do
  cp "$SOURCE_ROOT/$file" "$repo/$file"
done
mkdir -p "$repo/automation/context"
cp "$SOURCE_ROOT/automation/context/template-managed-paths.txt" "$repo/automation/context/"
# A generated project may already have added its own settings, so the contract uses the bare seed.
printf 'extend = "scripts/qa/ruff-base.toml"\n' >"$tmpdir/ruff.toml"
cp "$tmpdir/ruff.toml" "$repo/ruff.toml"

lint() {
  bash "$repo/scripts/qa/python-lint.sh"
}

expect_failure() {
  local label="$1"
  local needle="$2"
  local output
  if output="$(lint 2>&1)"; then
    printf '%s\n' "$output" >&2
    fail "$label was accepted"
  fi
  grep -F -- "$needle" <<<"$output" >/dev/null || {
    printf '%s\n' "$output" >&2
    fail "$label: expected '$needle' in the output"
  }
}

with_config() {
  cp "$tmpdir/ruff.toml" "$repo/ruff.toml"
  printf '%s\n' "$1" >>"$repo/ruff.toml"
}

# 1. The repository config extends the template base; the template seed holds nothing else.
grep -Fx 'extend = "scripts/qa/ruff-base.toml"' "$SOURCE_ROOT/ruff.toml" >/dev/null || fail "ruff.toml must extend the base"
if [ -f "$SOURCE_ROOT/automation/context/template-source-project-map.md" ] \
  && grep -Ev '^[[:space:]]*(#|$)|^extend = "scripts/qa/ruff-base.toml"$' "$SOURCE_ROOT/ruff.toml" >/dev/null; then
  fail "the template seed ruff.toml must hold only the extend line; shared settings belong to the base"
fi
for rule in '"E4"' '"F"' '"UP"' 'target-version = "py312"' 'line-length = 120'; do
  grep -F -- "$rule" "$repo/scripts/qa/ruff-base.toml" >/dev/null || fail "ruff base misses $rule"
done
lint >/dev/null || fail "python-lint.sh rejected the seed ruff.toml"

# 2. Project paths: an excluded project file is not checked, base excludes still apply.
mkdir -p "$repo/project_legacy" "$repo/automation/vendor/upstream"
printf 'import os\n' >"$repo/project_legacy/old.py"
printf 'import os\n' >"$repo/automation/vendor/upstream/tool.py"
expect_failure "unused import in a project file" "project_legacy/old.py:1:8"
with_config 'extend-exclude = ["project_legacy"]'
lint >/dev/null || fail "project extend-exclude did not exclude project_legacy"
if (cd "$repo" && uv run --locked ruff check --show-files . | grep -E 'project_legacy|automation/vendor' >/dev/null); then
  fail "ruff still lists excluded files"
fi
with_config "$(printf '[lint.per-file-ignores]\n"project_legacy/**" = ["F401"]')"
lint >/dev/null || fail "project per-file-ignores were not applied"
rm -rf "$repo/project_legacy"
cp "$tmpdir/ruff.toml" "$repo/ruff.toml"

# 3. The base may not be dropped or switched off for template-managed files.
printf 'line-length = 120\n' >"$repo/ruff.toml"
expect_failure "missing extend" 'must keep extend = "scripts/qa/ruff-base.toml"'
with_config "$(printf '[lint]\nselect = ["F"]')"
expect_failure "replaced select" "lint.select drops base rules"
with_config "$(printf '[lint]\nignore = ["F401"]')"
expect_failure "ignored base rule" "lint.ignore switches off base rules for every file: F401"
with_config 'extend-exclude = ["scripts/python"]'
expect_failure "excluded template files" "extend-exclude pattern 'scripts/python' excludes template files"
with_config "$(printf '[lint.per-file-ignores]\n"scripts/**" = ["F401"]')"
expect_failure "per-file-ignores on template files" "lint.per-file-ignores 'scripts/**' switches off base rules F401"
cp "$tmpdir/ruff.toml" "$repo/ruff.toml"

# 4. A uv environment without ruff names the fix command.
fakebin="$tmpdir/fakebin"
mkdir -p "$fakebin"
cat >"$fakebin/uv" <<'EOF'
#!/usr/bin/env bash
if [ "$*" = "run --locked ruff --version" ]; then
  echo 'error: Failed to spawn: `ruff`' >&2
  echo '  Caused by: No such file or directory (os error 2)' >&2
  exit 2
fi
exit 97
EOF
chmod +x "$fakebin/uv"
if output="$(PATH="$fakebin:$PATH" lint 2>&1)"; then
  fail "missing ruff was accepted"
fi
for needle in "ruff is not installed in the project uv environment" 'uv add --dev "ruff>=' "uv export --locked"; do
  grep -F -- "$needle" <<<"$output" >/dev/null || {
    printf '%s\n' "$output" >&2
    fail "missing ruff: expected '$needle' in the output"
  }
done

# 5. ruff.toml is seed-once and project-owned; the base is template-managed.
grep -Fx 'ruff.toml' "$SOURCE_ROOT/automation/context/template-update-preserve-paths.txt" >/dev/null \
  || fail "ruff.toml must be in template-update-preserve-paths.txt"
grep -E '^PROJECT_OWNED_PYTHON_SEED_PATHS=\(.*ruff\.toml' "$SOURCE_ROOT/scripts/template/lib-overlay.sh" >/dev/null \
  || fail "lib-overlay.sh must seed ruff.toml"
(
  cd "$SOURCE_ROOT"
  python3 - <<'PY'
from scripts.python.imported_skills import _is_overlay_managed
from scripts.python.project_extensions import PROJECT_OWNED_PYTHON_SEED_PATHS

assert "ruff.toml" in PROJECT_OWNED_PYTHON_SEED_PATHS, PROJECT_OWNED_PYTHON_SEED_PATHS
assert not _is_overlay_managed("ruff.toml")
assert _is_overlay_managed("scripts/qa/ruff-base.toml")
PY
)

echo "python ruff config contract passed"
