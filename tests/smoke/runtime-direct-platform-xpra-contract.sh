#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bindir="$tmpdir/bin"
path_success="$tmpdir/path-success"
path_missing_xpra="$tmpdir/path-missing-xpra"
profile_path="$tmpdir/profile.json"
doctor_run_root="$tmpdir/doctor-run"
bdd_run_root="$tmpdir/bdd-run"
runtime_missing_xpra_run_root="$tmpdir/runtime-missing-xpra-run"
doctor_missing_xpra_run_root="$tmpdir/doctor-missing-xpra-run"
fake_ready_file="$tmpdir/xpra-ready-display"
invocation_log="$tmpdir/invocations.log"
fake_binary="$bindir/1cv8"
fake_client="$bindir/1cv8c"
fake_ibcmd="$bindir/ibcmd"
fake_xpra="$bindir/xpra"
fake_xvfb="$bindir/Xvfb"
fake_xdpyinfo="$bindir/xdpyinfo"
fake_openbox="$bindir/openbox"

mkdir -p "$bindir"
: >"$invocation_log"

cat >"$fake_binary" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ -n "${ONEC_INVOCATION_LOG:-}" ]; then
  printf '%s\n' "$(basename "$0")" >>"$ONEC_INVOCATION_LOG"
fi

printf 'fake-%s\n' "$(basename "$0")"
printf 'display=%s\n' "${DISPLAY:-}"
printf 'xauthority=%s\n' "${XAUTHORITY:-}"
for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cp "$fake_binary" "$fake_client"

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'fake-ibcmd\n'
for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cat >"$fake_xpra" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'fake-xpra\n'
printf 'xpra-xauthority=%s\n' "${XAUTHORITY:-}"
for arg in "$@"; do
  printf 'xpra-arg=%s\n' "$arg"
done

case "${1:-}" in
  start-desktop)
    printf '%s\n' "${2:-}" >"${ONEC_FAKE_XPRA_READY_FILE:?}"
    ;;
  stop)
    : >"${ONEC_FAKE_XPRA_READY_FILE:?}"
    ;;
esac
EOF

cat >"$fake_xdpyinfo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

display="${DISPLAY:-}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    -display)
      display="${2:-}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

[ -f "${ONEC_FAKE_XPRA_READY_FILE:?}" ] || exit 1
[ "$(cat "$ONEC_FAKE_XPRA_READY_FILE")" = "$display" ]
EOF

cat >"$fake_xvfb" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

cat >"$fake_openbox" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$fake_binary" "$fake_client" "$fake_ibcmd" "$fake_xpra" "$fake_xvfb" "$fake_xdpyinfo" "$fake_openbox"

mirror_commands() {
  local target_dir="$1"
  local command_name=""

  mkdir -p "$target_dir"
  for command_name in awk bash basename cat date dirname env flock git grep jq kill locale mkdir mktemp ps realpath rg sed seq sleep tee tail tr; do
    ln -sf "$(command -v "$command_name")" "$target_dir/$command_name"
  done
}

mirror_commands "$path_success"
mirror_commands "$path_missing_xpra"
ln -sf "$fake_xpra" "$path_success/xpra"
ln -sf "$fake_xvfb" "$path_success/Xvfb"
ln -sf "$fake_xdpyinfo" "$path_success/xdpyinfo"
ln -sf "$fake_openbox" "$path_success/openbox"
ln -sf "$fake_xvfb" "$path_missing_xpra/Xvfb"
ln -sf "$fake_xdpyinfo" "$path_missing_xpra/xdpyinfo"
ln -sf "$fake_openbox" "$path_missing_xpra/openbox"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "xpra-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_binary",
    "ibcmdPath": "$fake_ibcmd",
    "xpra": {
      "enabled": true,
      "startChild": "openbox",
      "xvfbArgs": ["Xvfb", "-screen", "0", "1440x900x24", "-nolisten", "tcp", "-noreset", "-auth", "\$XAUTHORITY"]
    },
    "xvfb": {
      "enabled": true,
      "serverArgs": ["-screen", "0", "1440x900x24", "-noreset"]
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/ibcmd-data"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/ibcmd-db"
    },
    "auth": {
      "user": null,
      "passwordEnv": null
    }
  },
  "infobase": {
    "mode": "file",
    "filePath": "/tmp/xpra-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "bdd": {
      "command": ["$fake_client", "ENTERPRISE", "/F", "/tmp/xpra-fixture"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_matches() {
  local file="$1"
  local expected_regex="$2"

  if ! grep -Eq -- "$expected_regex" "$file"; then
    printf 'expected regex not found: %s\n' "$expected_regex" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"
  shift 3

  if ! jq -e "$expr" "$file" "$@" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

(
  cd "$SOURCE_ROOT"
  PATH="$path_success" ONEC_FAKE_XPRA_READY_FILE="$fake_ready_file" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_run_root" >/dev/null
)

assert_jq "$doctor_run_root/summary.json" '.status == "success"' "doctor-status"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.wrapper == "xpra"' "doctor-wrapper"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.xpra.enabled == true' "doctor-xpra-enabled"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.xpra.start_child == "openbox"' "doctor-start-child"
assert_jq "$doctor_run_root/summary.json" '.adapter_context.xpra.xvfb_args == ["Xvfb","-screen","0","1440x900x24","-nolisten","tcp","-noreset","-auth","$XAUTHORITY"]' "doctor-xvfb-args"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xpra" and .status == "present")] | length == 1' "doctor-required-xpra"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "Xvfb" and .status == "present")] | length == 1' "doctor-required-xvfb"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xdpyinfo" and .status == "present")] | length == 1' "doctor-required-xdpyinfo"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "openbox" and .status == "present")] | length == 1' "doctor-required-openbox"
assert_jq "$doctor_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xvfb-run" or .name == "xauth")] | length == 0' "doctor-no-xvfb-run-required"

(
  cd "$SOURCE_ROOT"
  PATH="$path_success" XAUTHORITY="$tmpdir/stale.Xauthority" ONEC_FAKE_XPRA_READY_FILE="$fake_ready_file" ONEC_INVOCATION_LOG="$invocation_log" ./scripts/test/run-bdd.sh --profile "$profile_path" --run-root "$bdd_run_root" >/dev/null
)

assert_jq "$bdd_run_root/summary.json" '.status == "success"' "bdd-status"
assert_jq "$bdd_run_root/summary.json" '.execution.executor == "adapter-wrapper"' "bdd-executor"
assert_jq "$bdd_run_root/summary.json" '.adapter_context.wrapper == "xpra"' "bdd-wrapper"
assert_contains "$bdd_run_root/stderr.log" "fake-xpra"
assert_contains "$bdd_run_root/stderr.log" "xpra-arg=start-desktop"
assert_contains "$SOURCE_ROOT/scripts/adapters/direct-platform.sh" "flock -x 9"
assert_contains "$SOURCE_ROOT/scripts/adapters/direct-platform.sh" "ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN"
assert_contains "$SOURCE_ROOT/scripts/adapters/direct-platform.sh" "process-cleanup-baseline.txt"
assert_contains "$bdd_run_root/stderr.log" "xpra-xauthority=$bdd_run_root/home/.Xauthority"
assert_contains "$bdd_run_root/stderr.log" "xpra-arg=--xvfb=Xvfb -screen 0 1440x900x24 -nolisten tcp -noreset -auth $bdd_run_root/home/.Xauthority"
assert_contains "$bdd_run_root/stdout.log" "fake-1cv8c"
assert_matches "$bdd_run_root/stdout.log" '^display=:[0-9]+$'
assert_contains "$bdd_run_root/stdout.log" "xauthority=$bdd_run_root/home/.Xauthority"
assert_contains "$invocation_log" "1cv8c"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xpra" ONEC_FAKE_XPRA_READY_FILE="$fake_ready_file" ./scripts/test/run-bdd.sh --profile "$profile_path" --run-root "$runtime_missing_xpra_run_root" >/dev/null
)
status_missing_xpra=$?
set -e

if [ "$status_missing_xpra" -eq 0 ]; then
  printf 'expected run-bdd to fail when xpra is missing\n' >&2
  exit 1
fi

assert_jq "$runtime_missing_xpra_run_root/summary.json" '.status == "failed"' "runtime-missing-xpra-status"
assert_contains "$runtime_missing_xpra_run_root/stderr.log" "command not found: xpra"

set +e
(
  cd "$SOURCE_ROOT"
  PATH="$path_missing_xpra" ./scripts/diag/doctor.sh --profile "$profile_path" --run-root "$doctor_missing_xpra_run_root" >/dev/null
)
status_doctor_missing_xpra=$?
set -e

if [ "$status_doctor_missing_xpra" -eq 0 ]; then
  printf 'expected doctor to fail when xpra is missing\n' >&2
  exit 1
fi

assert_jq "$doctor_missing_xpra_run_root/summary.json" '.status == "failed"' "doctor-missing-xpra-status"
assert_jq "$doctor_missing_xpra_run_root/summary.json" '[.checks.required_tools[] | select(.name == "xpra" and .status == "missing")] | length == 1' "doctor-missing-xpra-tool"
assert_jq "$doctor_missing_xpra_run_root/summary.json" '[.checks.required_capabilities[] | select(.name == "run-bdd" and .reason == "missing xpra for direct-platform xpra wrapper")] | length == 1' "doctor-missing-xpra-bdd"
