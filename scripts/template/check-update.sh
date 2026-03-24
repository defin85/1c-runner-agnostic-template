#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=./lib-overlay.sh
source "$SCRIPT_DIR/lib-overlay.sh"

usage() {
  cat <<'EOF'
Usage:
  check-update.sh [--vcs-ref REF]

Options:
  -h, --help     Show this help
  -r, --vcs-ref  Check a specific overlay release ref instead of the latest tag
EOF
}

requested_ref=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -r|--vcs-ref)
      [ "$#" -ge 2 ] || die "--vcs-ref requires a value"
      requested_ref="$2"
      shift 2
      ;;
    --vcs-ref=*)
      requested_ref="${1#*=}"
      shift
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

require_command git

root="$(project_root)"
cd "$root"

source_path="$(template_source_path "$root")"
current_version="$(current_overlay_version "$root")"
target_ref="$(resolve_target_overlay_ref "$source_path" "$requested_ref")"

log "Check template overlay updates"
printf 'Current overlay version: %s\n' "$current_version"
printf 'Available overlay release: %s\n' "$target_ref"

if [ "$current_version" = "$target_ref" ]; then
  printf 'Project is up-to-date.\n'
else
  printf 'Overlay update available.\n'
fi
