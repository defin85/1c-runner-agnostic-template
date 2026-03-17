#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

profile_path="$tmpdir/legacy-profile.json"
stderr_path="$tmpdir/stderr.log"

cat >"$profile_path" <<'EOF'
{
  "schemaVersion": 1,
  "profileName": "legacy",
  "runnerAdapter": "direct-platform",
  "shellEnv": {
    "CREATE_IB_CMD": "echo legacy"
  }
}
EOF

set +e
(
  cd "$SOURCE_ROOT"
  ./scripts/platform/create-ib.sh --profile "$profile_path"
) >/dev/null 2>"$stderr_path"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  printf 'legacy profile must be rejected\n' >&2
  exit 1
fi

grep -Fq -- 'schemaVersion=1 is no longer supported' "$stderr_path"
grep -Fq -- './scripts/template/migrate-runtime-profile-v2.sh' "$stderr_path"
grep -Fq -- 'docs/migrations/runtime-profile-v2.md' "$stderr_path"
