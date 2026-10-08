#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_rejected() {
  local schema_version="$1"
  local profile_path="$tmpdir/legacy-v$schema_version.json"
  local stderr_path="$tmpdir/legacy-v$schema_version.stderr"
  local status

  cat >"$profile_path" <<EOF
{
  "schemaVersion": $schema_version,
  "profileName": "legacy-v$schema_version",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "echo legacy"
  }
}
EOF

  set +e
  (
    cd "$SOURCE_ROOT"
    ./scripts/platform/create-ib.sh --profile "$profile_path" --run-root "$tmpdir/run-v$schema_version"
  ) >/dev/null 2>"$stderr_path"
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf 'schemaVersion=%s profile must be rejected\n' "$schema_version" >&2
    exit 1
  fi

  for expected in \
    "schemaVersion=$schema_version is no longer supported" \
    './scripts/template/migrate-runtime-profile-v3.sh' \
    'docs/migrations/runtime-profile-v3.md'; do
    if ! grep -Fq -- "$expected" "$stderr_path"; then
      printf 'expected rejection text not found for schemaVersion=%s: %s\n' "$schema_version" "$expected" >&2
      cat "$stderr_path" >&2
      exit 1
    fi
  done
}

assert_rejected 1
assert_rejected 2
