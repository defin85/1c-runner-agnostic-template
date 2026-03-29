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
  update-template.sh [--vcs-ref REF] [--pretend]

Options:
  -h, --help     Show this help
  -r, --vcs-ref  Apply a specific overlay release ref instead of the latest tag
      --pretend  Print actions without changing the repository
EOF
}

require_clean_git_worktree() {
  local root="$1"

  if ! git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "copier update requires a git repository"
  fi

  if [ -n "$(git -C "$root" status --porcelain)" ]; then
    die "git working tree is dirty; commit or stash changes before overlay update"
  fi
}

requested_ref=""
pretend=0

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
    --pretend)
      pretend=1
      shift
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

require_command git
require_command install

root="$(project_root)"
require_clean_git_worktree "$root"
cd "$root"

source_path="$(template_source_path "$root")"
current_version="$(current_overlay_version "$root")"
target_ref="$(resolve_target_overlay_ref "$source_path" "$requested_ref")"
project_name="$(project_answer_value "$root" "project_name")"
project_slug="$(project_answer_value "$root" "project_slug")"
project_description="$(project_answer_value "$root" "project_description")"
init_beads="$(project_answer_value_or_default "$root" "init_beads" "yes")"

log "Apply template overlay release"
printf 'Current overlay version: %s\n' "$current_version"
printf 'Target overlay release: %s\n' "$target_ref"

if [ "$current_version" = "$target_ref" ]; then
  log "Overlay is already up-to-date"
  exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

release_root="$tmpdir/release"
mkdir -p "$release_root"

materialize_overlay_source "$source_path" "$target_ref" "$release_root"

if [ "$pretend" -eq 1 ]; then
  DRY_RUN=1 sync_overlay_manifests \
    "$release_root" \
    "$root" \
    "$(overlay_manifest_file "$root")" \
    "$(overlay_manifest_file "$release_root")" \
    "$(overlay_preserve_manifest_file "$release_root")"
  printf 'would refresh generated overlay surfaces\n'
  exit 0
fi

sync_overlay_manifests \
  "$release_root" \
  "$root" \
  "$(overlay_manifest_file "$root")" \
  "$(overlay_manifest_file "$release_root")" \
  "$(overlay_preserve_manifest_file "$release_root")"

write_overlay_version "$root" "$target_ref"

bash "$root/scripts/bootstrap/overlay-post-apply.sh" \
  "$release_root" \
  "$project_name" \
  "$project_slug" \
  "$project_description" \
  "$init_beads"
