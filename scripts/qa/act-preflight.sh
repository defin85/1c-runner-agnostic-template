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
)

if [ "$dryrun" -eq 1 ]; then
  cmd+=(--dryrun)
fi

"${cmd[@]}"
