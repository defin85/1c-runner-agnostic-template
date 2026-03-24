#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
status=0

check_skills_dir() {
  local skills_dir="$1"
  local label="$2"

  if [ ! -d "$skills_dir" ]; then
    die "skills directory not found: $skills_dir"
  fi

  if [ ! -f "$skills_dir/README.md" ]; then
    printf 'missing skills README: %s/README.md\n' "$skills_dir" >&2
    status=1
  fi

  while IFS= read -r skill_file; do
    if ! grep -Eq '^Repo script: `\./scripts/.+`$' "$skill_file"; then
      printf 'missing repo script binding (%s): %s\n' "$label" "$skill_file" >&2
      status=1
    fi

    if grep -Eq 'powershell\.exe -File|/opt/1cv8|1cv8 DESIGNER|rac ' "$skill_file"; then
      printf 'skill embeds runtime implementation details instead of repo script contract (%s): %s\n' "$label" "$skill_file" >&2
      status=1
    fi
  done < <(find "$skills_dir" -mindepth 2 -maxdepth 2 -name SKILL.md | sort)
}

check_skills_dir "$root/.agents/skills" "codex"
check_skills_dir "$root/.claude/skills" "claude"

if [ "$status" -eq 0 ]; then
  log "Skill bindings look consistent"
fi

exit "$status"
