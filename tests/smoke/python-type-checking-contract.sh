#!/usr/bin/env bash
# Contract: Python quality contours fail closed.
# - type-check.sh reports a new type error with file and line and exits non-zero;
# - a basedpyright baseline file, a project config that drops the template base ("extends"),
#   weakens the mode or a rule, an unclassified Python root, a stale requirements-dev.txt export
#   or a tool pin below the template minimum make type-check.sh fail before basedpyright runs;
# - basedpyright honours "extends";
# - python-lint.sh reports an unused import (F401) with file and line;
# - a missing uv is a hard error, there is no fallback to globally installed tools;
# - make/make.ps1/agent-verify expose the contours.
# Everything runs in a temporary copy, the working tree is never modified.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${ONEC_PYTHON:-python3}"

fail() {
  printf 'python type checking contract failed: %s\n' "$1" >&2
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
for file in pyproject.toml uv.lock requirements-dev.txt ruff.toml; do
  cp "$SOURCE_ROOT/$file" "$repo/$file"
done
mkdir -p "$repo/fixture"
"$PYTHON_BIN" - "$SOURCE_ROOT/pyrightconfig.json" "$repo/pyrightconfig.json" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
# Same mandatory settings, smaller scope: the template code itself is checked by make verify-types.
config["include"] = ["scripts", "fixture"]
Path(sys.argv[2]).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
cp "$repo/pyrightconfig.json" "$tmpdir/pyrightconfig.json"
cp "$repo/requirements-dev.txt" "$tmpdir/requirements-dev.txt"

expect_failure() {
  local label="$1"
  local needle="$2"
  shift 2
  local output
  if output="$("$@" 2>&1)"; then
    printf '%s\n' "$output" >&2
    fail "$label was accepted"
  fi
  grep -F -- "$needle" <<<"$output" >/dev/null || {
    printf '%s\n' "$output" >&2
    fail "$label: expected '$needle' in the output"
  }
}

# 1. A type error in the fixture is reported with file, line and rule.
printf 'value: str = 1\n' >"$repo/fixture/type_error.py"
if type_output="$(bash "$repo/scripts/qa/type-check.sh" 2>&1)"; then
  printf '%s\n' "$type_output" >&2
  fail "type error was accepted"
fi
for needle in "fixture/type_error.py:1:" "reportAssignmentType"; do
  grep -F -- "$needle" <<<"$type_output" >/dev/null || {
    printf '%s\n' "$type_output" >&2
    fail "type error: expected '$needle' in the output"
  }
done
rm "$repo/fixture/type_error.py"

# 2. Baseline files are forbidden in both the explicit and the basedpyright default location.
printf '{"files": {}}\n' >"$repo/basedpyright-baseline.json"
expect_failure "baseline file" "baseline files are not allowed" bash "$repo/scripts/qa/type-check.sh"
rm "$repo/basedpyright-baseline.json"
mkdir -p "$repo/.basedpyright"
printf '{"files": {}}\n' >"$repo/.basedpyright/baseline.json"
expect_failure "default baseline file" ".basedpyright/baseline.json" bash "$repo/scripts/qa/type-check.sh"
rm -rf "$repo/.basedpyright"

# 3. The project-owned pyrightconfig.json may add roots but may not weaken the template base:
#    the base must stay in "extends", the mode stays at least standard, rules are not disabled or
#    downgraded, and baselineFile/ignore are rejected.
edit_config() {
  "$PYTHON_BIN" - "$repo/pyrightconfig.json" "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
exec(sys.argv[2], {"config": config})
path.write_text(json.dumps(config), encoding="utf-8")
PY
}
check_config_rejected() {
  local label="$1" edit="$2" needle="$3"
  edit_config "$edit"
  expect_failure "$label" "$needle" bash "$repo/scripts/qa/type-check.sh"
  cp "$tmpdir/pyrightconfig.json" "$repo/pyrightconfig.json"
}
check_config_rejected "removed extends" 'del config["extends"]' 'must keep "extends": "scripts/qa/pyright-base.json"'
check_config_rejected "foreign extends" 'config["extends"] = "other.json"' 'must keep "extends"'
check_config_rejected "weakened mode" 'config["typeCheckingMode"] = "basic"' "weaker than standard"
check_config_rejected "disabled rule" 'config["reportAssignmentType"] = "none"' "disables basedpyright rules: reportAssignmentType"
check_config_rejected "downgraded rule" 'config["reportAssignmentType"] = "warning"' "disables basedpyright rules: reportAssignmentType"
check_config_rejected "configured baseline" 'config["baselineFile"] = "baseline.json"' "must not configure: baselineFile"
check_config_rejected "ignored paths" 'config["ignore"] = ["fixture"]' "must not configure: ignore"
cp "$repo/scripts/qa/pyright-base.json" "$tmpdir/pyright-base.json"
printf '{"typeCheckingMode": "basic"}\n' >"$repo/scripts/qa/pyright-base.json"
expect_failure "weakened base" "weaker than standard" bash "$repo/scripts/qa/type-check.sh"
cp "$tmpdir/pyright-base.json" "$repo/scripts/qa/pyright-base.json"

# basedpyright itself honours "extends": a rule switched off only in the base file silences the
# error, and the same project config without "extends" reports it (default mode is stricter).
native="$tmpdir/native"
mkdir -p "$native/qa"
printf 'value: str = 1\n' >"$native/sample.py"
printf '{"typeCheckingMode": "standard", "reportAssignmentType": "none"}\n' >"$native/qa/base.json"
printf '{"extends": "qa/base.json", "include": ["sample.py"]}\n' >"$native/pyrightconfig.json"
(cd "$repo" && uv run --locked --project "$repo" basedpyright --project "$native/pyrightconfig.json" >/dev/null) \
  || fail "basedpyright ignored a rule configured in the extended base file"
printf '{"include": ["sample.py"]}\n' >"$native/pyrightconfig.json"
if (cd "$repo" && uv run --locked --project "$repo" basedpyright --project "$native/pyrightconfig.json" >/dev/null); then
  fail "basedpyright accepted the type error without the base file"
fi

# 4. Python outside the include roots would escape the type check.
mkdir -p "$repo/unclassified"
printf 'value = 1\n' >"$repo/unclassified/example.py"
expect_failure "unclassified Python root" "unclassified/example.py" bash "$repo/scripts/qa/type-check.sh"
rm -rf "$repo/unclassified"

# 5. requirements-dev.txt must match the uv.lock export, keep the template minimum tool versions
#    and name the fix command.
printf 'six==1.0.0\n' >>"$repo/requirements-dev.txt"
expect_failure "stale requirements export" "uv export --locked" bash "$repo/scripts/qa/type-check.sh"
cp "$tmpdir/requirements-dev.txt" "$repo/requirements-dev.txt"
sed -i 's/^basedpyright==.*/basedpyright==1.30.0/' "$repo/requirements-dev.txt"
expect_failure "pin below minimum" "basedpyright 1.30.0 is below the template minimum 1.39.9" \
  bash "$repo/scripts/qa/type-check.sh"
expect_failure "pin fix hint" 'uv add --dev "basedpyright>=1.39.9"' bash "$repo/scripts/qa/type-check.sh"
sed -i '/^ruff==/d' "$repo/requirements-dev.txt"
expect_failure "missing pin" "ruff is not pinned" bash "$repo/scripts/qa/type-check.sh"
cp "$tmpdir/requirements-dev.txt" "$repo/requirements-dev.txt"

# 6. Lint reports an unused import with file, line and rule.
printf 'import os\n' >"$repo/fixture/lint_error.py"
expect_failure "unused import location" "fixture/lint_error.py:1:8" bash "$repo/scripts/qa/python-lint.sh"
expect_failure "unused import rule" "F401" bash "$repo/scripts/qa/python-lint.sh"
rm "$repo/fixture/lint_error.py"

# 7. Without uv every contour fails with an install hint instead of falling back to global tools.
(
  cd "$repo"
  "$PYTHON_BIN" - <<'PY'
import contextlib
import io
from unittest.mock import patch

from scripts.python import type_checking

for run in (type_checking.run_type_check, type_checking.run_python_lint, type_checking.run_python_tests_fast):
    stderr = io.StringIO()
    with patch("scripts.python.type_checking.shutil.which", return_value=None), contextlib.redirect_stderr(stderr):
        status = run()
    assert status == 1, (run.__name__, status)
    assert "uv is not installed" in stderr.getvalue(), stderr.getvalue()
PY
)

# 8. The internal module refuses direct execution.
expect_failure "direct module execution" "internal module" "$PYTHON_BIN" "$repo/scripts/python/type_checking.py"

# 9. Entry points stay wired.
grep -F 'scripts/qa/python-lint.sh' "$SOURCE_ROOT/Makefile" >/dev/null || fail "make verify-python-lint is not wired"
grep -F 'scripts/qa/type-check.sh' "$SOURCE_ROOT/Makefile" >/dev/null || fail "make verify-types is not wired"
grep -F '"verify-python-lint"' "$SOURCE_ROOT/make.ps1" >/dev/null || fail "./make.ps1 verify-python-lint is not wired"
grep -F '"verify-types"' "$SOURCE_ROOT/make.ps1" >/dev/null || fail "./make.ps1 verify-types is not wired"
for step in python-lint.sh type-check.sh python-tests.sh tests/smoke/python-type-checking-contract.sh; do
  grep -F "$step" "$SOURCE_ROOT/scripts/qa/agent-verify.sh" >/dev/null || fail "agent-verify.sh misses $step"
done
for step in run_python_lint run_type_check run_python_tests_fast; do
  grep -F "$step," "$SOURCE_ROOT/scripts/python/qa.py" >/dev/null || fail "qa.agent_verify misses $step"
done
if ls "$SOURCE_ROOT"/basedpyright-baseline* >/dev/null 2>&1; then
  fail "the template must not ship a basedpyright baseline"
fi

echo "python type checking contract passed"
