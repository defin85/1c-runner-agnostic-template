#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./lib-source-release.sh
source "$SCRIPT_DIR/lib-source-release.sh"

usage() {
  cat <<'EOF'
Usage:
  install-source-hooks.sh

Installs the repo-owned source release guardrails by setting:
  git config core.hooksPath .githooks
EOF
}

if [ "$#" -gt 0 ]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
fi

require_command git

root="$(project_root)"
cd "$root"

require_source_template_repo "$root"
require_git_repo "$root"

install_source_hooks "$root"

printf 'Installed source release hooks via .githooks\n'
printf 'core.hooksPath=%s\n' "$(git -C "$root" config --get core.hooksPath)"
printf 'Canonical release command: %s\n' "$source_release_command"
