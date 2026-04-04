#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

manifest="$SOURCE_ROOT/automation/vendor/cc-1c-skills/imported-skills.json"
vendor_readme="$SOURCE_ROOT/automation/vendor/cc-1c-skills/README.md"
dispatcher="$SOURCE_ROOT/scripts/skills/run-imported-skill.sh"
dispatcher_ps1="$SOURCE_ROOT/scripts/skills/run-imported-skill.ps1"

assert_exists() {
  local path="$1"
  if [ ! -e "$path" ]; then
    printf 'missing expected path: %s\n' "$path" >&2
    exit 1
  fi
}

assert_contains() {
  local path="$1"
  local expected="$2"
  if ! grep -Fq -- "$expected" "$path"; then
    printf 'expected text not found in %s: %s\n' "$path" "$expected" >&2
    exit 1
  fi
}

assert_exists "$manifest"
assert_exists "$vendor_readme"
assert_exists "$dispatcher"
assert_exists "$dispatcher_ps1"

assert_contains "$vendor_readme" "git@github.com:Nikolay-Shirokov/cc-1c-skills.git"
assert_contains "$vendor_readme" "scripts/skills/run-imported-skill.sh"

python - "$SOURCE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "automation/vendor/cc-1c-skills/imported-skills.json").read_text(encoding="utf-8"))
skills = manifest.get("skills", [])
if len(skills) != 67:
    raise SystemExit(f"expected 67 imported skills, got {len(skills)}")

required_runtime = {
    "cf-edit": "python",
    "web-test": "node",
    "form-patterns": "reference",
    "db-create": "native-alias",
}

for entry in skills:
    name = entry["name"]
    agents = root / ".agents" / "skills" / name / "SKILL.md"
    claude = root / ".claude" / "skills" / name / "SKILL.md"
    vendor_dir = root / "automation/vendor/cc-1c-skills" / entry["vendor_dir"]
    if not agents.is_file():
        raise SystemExit(f"missing Codex skill: {agents}")
    if not claude.is_file():
        raise SystemExit(f"missing Claude skill: {claude}")
    if not vendor_dir.is_dir():
        raise SystemExit(f"missing vendor dir: {vendor_dir}")
    repo_script_line = f"Repo script: `./scripts/skills/run-imported-skill.sh {name}`"
    if repo_script_line not in agents.read_text(encoding="utf-8"):
        raise SystemExit(f"missing repo script binding in {agents}")
    if repo_script_line not in claude.read_text(encoding="utf-8"):
        raise SystemExit(f"missing repo script binding in {claude}")
    runtime = entry.get("runtime_kind")
    expected = required_runtime.get(name)
    if expected and runtime != expected:
        raise SystemExit(f"unexpected runtime for {name}: {runtime} != {expected}")
PY

reference_output="$(bash "$dispatcher" form-patterns)"
printf '%s' "$reference_output" | grep -F "Imported skill: form-patterns" >/dev/null
printf '%s' "$reference_output" | grep -F "Runtime kind: reference" >/dev/null
