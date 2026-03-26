#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

source_release_runbook_rel="docs/template-release.md"
source_release_command="./scripts/release/publish-overlay-release.sh --tag vX.Y.Z"
source_hooks_command="./scripts/release/install-source-hooks.sh"
source_release_push_guard_env="TEMPLATE_SOURCE_RELEASE_ALLOW_PUSH"

is_source_template_repo() {
  local root="$1"

  [ -f "$root/automation/context/template-source-project-map.md" ] && \
    [ -f "$root/openspec/specs/template-overlay-delivery/spec.md" ] && \
    [ -f "$root/openspec/specs/template-ci-contours/spec.md" ] && \
    [ -f "$root/openspec/specs/repository-agent-guidance/spec.md" ]
}

require_source_template_repo() {
  local root="$1"

  if ! is_source_template_repo "$root"; then
    die "source release workflow is available only in the template source repository"
  fi
}

require_git_repo() {
  local root="$1"

  if ! git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "source release workflow requires a git repository"
  fi
}

require_origin_remote() {
  local root="$1"

  if ! git -C "$root" remote get-url origin >/dev/null 2>&1; then
    die "origin remote is required for source template releases"
  fi
}

ensure_clean_git_worktree() {
  local root="$1"

  if [ -n "$(git -C "$root" status --porcelain)" ]; then
    die "git working tree is dirty; commit or stash changes before publishing a template release tag"
  fi
}

ensure_overlay_release_tag() {
  local tag="$1"

  if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    die "release tag must match v<major>.<minor>.<patch>"
  fi
}

ensure_head_matches_origin_main() {
  local root="$1"
  local head_oid=""
  local origin_main_oid=""
  local current_branch=""

  git -C "$root" fetch origin main --tags >/dev/null

  current_branch="$(git -C "$root" branch --show-current)"
  if [ "$current_branch" != "main" ]; then
    die "source release must be published from the local main branch"
  fi

  head_oid="$(git -C "$root" rev-parse HEAD)"
  origin_main_oid="$(git -C "$root" rev-parse refs/remotes/origin/main 2>/dev/null || true)"

  [ -n "$origin_main_oid" ] || die "origin/main is missing; push the verified main branch first"
  [ "$head_oid" = "$origin_main_oid" ] || die "HEAD must match origin/main before publishing a template release tag"
}

ensure_release_tag_absent() {
  local root="$1"
  local tag="$2"

  if git -C "$root" rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1; then
    die "release tag already exists locally: $tag"
  fi

  if git -C "$root" ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
    die "release tag already exists on origin: $tag"
  fi
}

install_source_hooks() {
  local root="$1"

  chmod +x "$root/.githooks/pre-push"
  git -C "$root" config core.hooksPath .githooks
}
