#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

root="$(project_root)"
skills_dir="$root/.claude/skills"
status=0

if [ ! -d "$skills_dir" ]; then
  die "skills directory not found: $skills_dir"
fi

while IFS= read -r skill_file; do
  if ! grep -Eq '^Repo script: `\./scripts/.+`$' "$skill_file"; then
    printf 'missing repo script binding: %s\n' "$skill_file" >&2
    status=1
  fi

  if grep -Eq 'powershell\.exe -File|/opt/1cv8|1cv8 DESIGNER|rac ' "$skill_file"; then
    printf 'skill embeds runtime implementation details instead of repo script contract: %s\n' "$skill_file" >&2
    status=1
  fi
done < <(find "$skills_dir" -mindepth 2 -maxdepth 2 -name SKILL.md | sort)

if [ "$status" -eq 0 ]; then
  log "Skill bindings look consistent"
fi

exit "$status"
