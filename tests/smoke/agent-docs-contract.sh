#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

copy_repo() {
  local target="$1"
  mkdir -p "$target"
  (
    cd "$SOURCE_ROOT"
    tar --exclude=.git -cf - .
  ) | (
    cd "$target"
    tar xf -
  )
}

assert_fails_with() {
  local root="$1"
  local expected="$2"
  local stderr_file="$tmpdir/stderr.log"

  if (
    cd "$root"
    ./scripts/qa/check-agent-docs.sh >/dev/null 2>"$stderr_file"
  ); then
    printf 'check-agent-docs.sh should fail in %s\n' "$root" >&2
    exit 1
  fi

  if ! grep -Fq -- "$expected" "$stderr_file"; then
    printf 'expected error not found: %s\n' "$expected" >&2
    cat "$stderr_file" >&2
    exit 1
  fi
}

healthy_root="$tmpdir/healthy"
copy_repo "$healthy_root"
(
  cd "$healthy_root"
  ./scripts/qa/check-agent-docs.sh >/dev/null
)

missing_link_root="$tmpdir/missing-link"
copy_repo "$missing_link_root"
sed -i 's#\[docs/agent/architecture.md\](docs/agent/architecture.md)#docs/agent/architecture.md#' \
  "$missing_link_root/AGENTS.md"
assert_fails_with "$missing_link_root" "missing required markdown link in AGENTS.md: docs/agent/architecture.md"

broken_link_root="$tmpdir/broken-link"
copy_repo "$broken_link_root"
sed -i 's#(../../openspec/project.md)#(../../openspec/missing-project.md)#' \
  "$broken_link_root/docs/agent/architecture.md"
assert_fails_with "$broken_link_root" "broken markdown link in docs/agent/architecture.md:"
