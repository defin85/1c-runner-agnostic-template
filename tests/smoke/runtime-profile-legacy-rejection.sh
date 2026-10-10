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

# The shell loader used by warm BDD/YAxUnit contours and golden DB helpers accepts the same
# schemaVersion=3 profiles as the Python runtime and rejects legacy ones with the same guidance.
shell_load() {
  (
    # shellcheck source=../../scripts/lib/runtime-profile.sh
    source "$SOURCE_ROOT/scripts/lib/runtime-profile.sh"
    load_runtime_profile "$1"
    printf '%s\n' "$RUNTIME_PROFILE_RUNNER_ADAPTER"
  )
}

for schema_version in 1 2; do
  if shell_load "$tmpdir/legacy-v$schema_version.json" >/dev/null 2>"$tmpdir/shell-v$schema_version.stderr"; then
    printf 'shell loader must reject schemaVersion=%s\n' "$schema_version" >&2
    exit 1
  fi
  grep -Fq -- "schemaVersion=$schema_version is no longer supported" "$tmpdir/shell-v$schema_version.stderr" || {
    cat "$tmpdir/shell-v$schema_version.stderr" >&2
    exit 1
  }
  grep -Fq -- "./scripts/template/migrate-runtime-profile-v3.sh" "$tmpdir/shell-v$schema_version.stderr" || {
    cat "$tmpdir/shell-v$schema_version.stderr" >&2
    exit 1
  }
done

[ "$(shell_load "$SOURCE_ROOT/env/local.example.json")" = "direct-platform" ] || {
  printf 'shell loader must load env/local.example.json as direct-platform\n' >&2
  exit 1
}
[ "$(shell_load "$SOURCE_ROOT/env/windows-executor.example.json")" = "remote-windows" ] || {
  printf 'shell loader must derive remote-windows from transport.kind\n' >&2
  exit 1
}

jq '.capabilities.bdd = {"command": ["bash", "-lc", "true"]}' "$SOURCE_ROOT/env/local.example.json" >"$tmpdir/v3-command.json"
jq '. + {"runnerAdapter": "direct-platform"}' "$SOURCE_ROOT/env/local.example.json" >"$tmpdir/v3-adapter.json"
for case_name in command adapter; do
  if shell_load "$tmpdir/v3-$case_name.json" >/dev/null 2>"$tmpdir/v3-$case_name.stderr"; then
    printf 'shell loader must reject schemaVersion=3 profile with %s\n' "$case_name" >&2
    exit 1
  fi
done
grep -Fq -- "does not support profile-defined command orchestration: capabilities.bdd.command" "$tmpdir/v3-command.stderr"
grep -Fq -- "must not define runnerAdapter" "$tmpdir/v3-adapter.stderr"
