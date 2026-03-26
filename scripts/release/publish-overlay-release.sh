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
  publish-overlay-release.sh --tag vX.Y.Z

Publishes an overlay release tag from the source template repository.
The workflow fails closed unless:
  - the repository is the template source repo;
  - the git worktree is clean;
  - local main matches origin/main;
  - baseline verification passes;
  - the target tag does not already exist.
EOF
}

release_tag=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --tag)
      [ "$#" -ge 2 ] || die "--tag requires a value"
      release_tag="$2"
      shift 2
      ;;
    --tag=*)
      release_tag="${1#*=}"
      shift
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[ -n "$release_tag" ] || die "--tag is required"

require_command git

root="$(project_root)"
cd "$root"

require_source_template_repo "$root"
require_git_repo "$root"
require_origin_remote "$root"
ensure_overlay_release_tag "$release_tag"
ensure_clean_git_worktree "$root"
install_source_hooks "$root"
ensure_head_matches_origin_main "$root"
ensure_release_tag_absent "$root" "$release_tag"

log "Run baseline verification before release publish"
"$root/scripts/qa/agent-verify.sh"

git -C "$root" tag -a "$release_tag" -m "Template overlay release $release_tag" >/dev/null
trap 'git -C "$root" tag -d "$release_tag" >/dev/null 2>&1 || true' ERR

log "Publish overlay release tag"
env "$source_release_push_guard_env"=1 \
  git -C "$root" push origin "refs/tags/$release_tag:refs/tags/$release_tag" >/dev/null

trap - ERR

printf 'Template overlay release published\n'
printf 'Tag: %s\n' "$release_tag"
printf 'Commit: %s\n' "$(git -C "$root" rev-parse HEAD)"
