#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

copy_repo() {
  local target="$1"
  local manifest=""
  mkdir -p "$target"

  if git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    (
      cd "$SOURCE_ROOT"
      manifest="$(mktemp)"
      while IFS= read -r -d '' relpath; do
        [ -e "$relpath" ] || continue
        printf '%s\0' "$relpath" >>"$manifest"
      done < <(git ls-files -z --cached --others --exclude-standard)
      tar --null -T "$manifest" -cf -
      rm -f "$manifest"
    ) | (
      cd "$target"
      tar xf -
    )
  else
    (
      cd "$SOURCE_ROOT"
      tar --exclude=.git -cf - .
    ) | (
      cd "$target"
      tar xf -
    )
  fi
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

repo_root="$tmpdir/repo"
remote_root="$tmpdir/remote.git"
blocked_stderr="$tmpdir/blocked.err"
release_stdout="$tmpdir/release.out"
release_tag="v9.9.9"

copy_repo "$repo_root"

git -C "$repo_root" init -q
git -C "$repo_root" branch -M main
git -C "$repo_root" config user.name "Smoke Test"
git -C "$repo_root" config user.email "smoke@example.com"
git -C "$repo_root" add -A
(
  cd "$repo_root"
  ./scripts/llm/export-context.sh --write >/dev/null
)
git -C "$repo_root" add -A
git -C "$repo_root" commit -qm "source snapshot"

git init --bare -q "$remote_root"
git -C "$repo_root" remote add origin "$remote_root"
git -C "$repo_root" push -u origin main >/dev/null

(
  cd "$repo_root"
  ./scripts/release/install-source-hooks.sh >/dev/null
)

if [ "$(git -C "$repo_root" config --get core.hooksPath)" != ".githooks" ]; then
  printf 'core.hooksPath must point to .githooks\n' >&2
  exit 1
fi

git -C "$repo_root" tag -a "$release_tag" -m "manual tag" >/dev/null
if (
  cd "$repo_root"
  git push origin "refs/tags/$release_tag:refs/tags/$release_tag" >/dev/null 2>"$blocked_stderr"
); then
  printf 'manual overlay tag push should be blocked by pre-push hook\n' >&2
  exit 1
fi

assert_contains "$blocked_stderr" "must be pushed via"

if git --git-dir="$remote_root" rev-parse "refs/tags/$release_tag" >/dev/null 2>&1; then
  printf 'blocked tag must not appear on remote\n' >&2
  exit 1
fi

git -C "$repo_root" tag -d "$release_tag" >/dev/null

(
  cd "$repo_root"
  ./scripts/release/publish-overlay-release.sh --tag "$release_tag" >"$release_stdout"
)

assert_contains "$release_stdout" "Template overlay release published"
assert_contains "$release_stdout" "$release_tag"

remote_commit="$(git --git-dir="$remote_root" rev-parse "refs/tags/$release_tag^{}")"
local_head="$(git -C "$repo_root" rev-parse HEAD)"

if [ "$remote_commit" != "$local_head" ]; then
  printf 'release tag must point to current HEAD\n' >&2
  printf 'remote: %s\nlocal: %s\n' "$remote_commit" "$local_head" >&2
  exit 1
fi
