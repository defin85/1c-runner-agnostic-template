#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

usage() {
  cat <<'EOF'
Usage:
  act-preflight.sh [--help]
  act-preflight.sh [--dryrun] [--job static|fixture] [--event pull_request|push]

Runs the locally reproducible Linux GitHub Actions contour for this repository via act.
Default behavior runs the `fixture` job, which also executes `static` through its `needs`.
A successful default run on a clean worktree records the commit tree in the git dir
(`act-preflight-passed`); the pre-push hook then skips the rerun for that tree, so the long
check does not run while git holds the remote connection open.

Environment overrides:
  ACT_PREFLIGHT_IMAGE   Override the act image (default: catthehacker/ubuntu:full-latest)
  ACT_PREFLIGHT_LABEL   Override the runner label (default: ubuntu-latest)
  ACT_PREFLIGHT_PULL    Set to true to allow docker pulls (default: false)
EOF
}

job_id="fixture"
event_name="pull_request"
dryrun=0
runner_label="${ACT_PREFLIGHT_LABEL:-ubuntu-latest}"
image="${ACT_PREFLIGHT_IMAGE:-catthehacker/ubuntu:full-latest}"
pull_images="${ACT_PREFLIGHT_PULL:-false}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -n|--dryrun)
      dryrun=1
      shift
      ;;
    -j|--job)
      [ "$#" -ge 2 ] || die "--job requires a value"
      job_id="$2"
      shift 2
      ;;
    --job=*)
      job_id="${1#*=}"
      shift
      ;;
    -e|--event)
      [ "$#" -ge 2 ] || die "--event requires a value"
      event_name="$2"
      shift 2
      ;;
    --event=*)
      event_name="${1#*=}"
      shift
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

case "$job_id" in
  static|fixture) ;;
  *)
    die "--job must be static or fixture"
    ;;
esac

case "$event_name" in
  pull_request|push)
    ;;
  *)
    die "--event must be pull_request or push"
    ;;
esac

require_command act
require_command docker

root="$(project_root)"
cd "$root"

log "Run local GitHub Actions preflight via act"
printf 'Workflow: %s\n' ".github/workflows/ci.yml"
printf 'Event: %s\n' "$event_name"
printf 'Job: %s\n' "$job_id"
printf 'Matrix: os=%s\n' "$runner_label"
printf 'Image: %s\n' "$image"
printf 'Pull images: %s\n' "$pull_images"

# In a git worktree .git is a file pointing to the main repository's git dir on the host.
# Mount that dir at the same path, otherwise git fails inside the container and
# generated-context checks fall back to a filesystem walk with untracked files.
git_common_dir=""
if [ -f .git ]; then
  git_common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
  printf 'Git worktree: mount %s read-only\n' "$git_common_dir"
fi
printf '%s\n' \
  'Note: this local preflight intentionally covers only the Linux static/fixture contour.' \
  'Windows matrix jobs and self-hosted runtime jobs stay outside the local act path.'

cmd=(
  act
  "$event_name"
  -W .github/workflows/ci.yml
  -j "$job_id"
  --matrix "os:$runner_label"
  -P "$runner_label=$image"
  "--pull=$pull_images"
  # Remove containers and volumes of a failed run; successful runs are removed by act itself.
  --rm
)

if [ -n "$git_common_dir" ]; then
  cmd+=(--container-options "-v $git_common_dir:$git_common_dir:ro")
fi

if [ "$dryrun" -eq 1 ]; then
  cmd+=(--dryrun)
fi

# act runs on the working directory, so only a clean worktree proves the committed tree.
record_pass=0
if [ "$dryrun" -eq 0 ] && [ "$job_id" = "fixture" ] && [ "$event_name" = "pull_request" ] \
  && [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  record_pass=1
fi
stamp_file="$(git rev-parse --git-path act-preflight-passed 2>/dev/null || true)"
[ -z "$stamp_file" ] || rm -f "$stamp_file"

"${cmd[@]}"

if [ "$record_pass" -eq 1 ] && [ -n "$stamp_file" ]; then
  tree="$(git rev-parse 'HEAD^{tree}')"
  printf '%s\n' "$tree" >"$stamp_file"
  printf 'Recorded preflight pass for tree %s\n' "$tree"
fi
