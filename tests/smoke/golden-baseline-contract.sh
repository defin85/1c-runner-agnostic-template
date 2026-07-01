#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
bindir="$tmpdir/bin"

mkdir -p "$bindir"

cat >"$bindir/pg_dump" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
out=""
for arg in "$@"; do
  case "$arg" in
    --file=*)
      out="${arg#--file=}"
      ;;
  esac
done
[ -n "$out" ] || { printf 'missing --file\n' >&2; exit 2; }
printf 'fake dump\n' >"$out"
EOF

cat >"$bindir/pg_restore" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'fake pg_restore %s\n' "$*"
EOF

cat >"$bindir/psql" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'fake psql %s\n' "$*"
EOF

chmod +x "$bindir/"*

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"

  if ! jq -e "$expr" "$file" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_root="$tmpdir/not-configured"
if "$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" 2>"$tmpdir/not-configured.err"; then
  printf 'golden-baseline must fail closed when no project runner is configured\n' >&2
  exit 1
fi
assert_jq "$run_root/summary.json" '.contour == "golden-baseline" and .status == "failed" and .exitCode == 2 and .classification == "not configured"' "not-configured"
assert_jq "$run_root/summary.json" '.command == "./tests/golden/run.sh"' "not-configured-default-command"

run_root="$tmpdir/passed"
"$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" --command "printf ok" >/dev/null
assert_jq "$run_root/summary.json" '.status == "passed" and .exitCode == 0 and .command == "printf ok"' "passed"

run_root="$tmpdir/failed"
if "$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" --command "exit 7"; then
  printf 'golden-baseline must propagate project runner failure\n' >&2
  exit 1
fi
assert_jq "$run_root/summary.json" '.status == "failed" and .exitCode == 7 and .classification == "failed"' "failed"

profile_path="$tmpdir/profile.json"
snapshot_path="$tmpdir/golden.dump"
cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "golden-fixture",
  "runnerAdapter": "direct-platform",
  "target": {"id": "golden_target"},
  "ibcmd": {
    "runtimeMode": "dbms-infobase",
    "dbmsInfobase": {
      "kind": "PostgreSQL",
      "server": "localhost",
      "name": "golden_target_db",
      "user": "postgres",
      "passwordEnv": "GOLDEN_FIXTURE_DB_PASSWORD"
    }
  },
  "infobase": {"mode": "server", "auth": {"mode": "os"}}
}
EOF

GOLDEN_FIXTURE_DB_PASSWORD=postgres PATH="$bindir:$PATH" \
  "$SOURCE_ROOT/tests/golden/create.sh" --profile "$profile_path" --snapshot "$snapshot_path" >/dev/null
[ -f "$snapshot_path" ] || { printf 'snapshot was not created\n' >&2; exit 1; }

run_root="$tmpdir/default-restore"
GOLDEN_FIXTURE_DB_PASSWORD=postgres PATH="$bindir:$PATH" \
  "$SOURCE_ROOT/scripts/test/run-golden-baseline.sh" --run-root "$run_root" --profile "$profile_path" --snapshot "$snapshot_path" >/dev/null
assert_jq "$run_root/summary.json" '.status == "passed" and .command == "./tests/golden/run.sh"' "default-restore"
