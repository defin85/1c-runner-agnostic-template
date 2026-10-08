#!/usr/bin/env bash
set -euo pipefail

# Contract of run-client on fixture tools: the password is shown only as ***,
# every session command acts only on the client and display of its own run-root,
# --wait --idle-timeout returns 125 with screenshots/idle-timeout.png, --timeout returns 124.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
RUN_CLIENT="$SOURCE_ROOT/scripts/platform/run-client.sh"

case "$(uname -s)" in
  Linux) ;;
  *)
    printf 'run-client-contract: skipped (Xpra session contract is Linux-only)\n'
    exit 0
    ;;
esac

tmpdir="$(mktemp -d)"
bindir="$tmpdir/bin"
ready_dir="$tmpdir/ready"
input_log="$tmpdir/xdotool.log"
profile="$tmpdir/profile.json"
secret="Fixture-Pa55-$RANDOM-value"
run_a="$tmpdir/run-a"
run_b="$tmpdir/run-b"

cleanup() {
  local root=""
  for root in "$run_a" "$run_b"; do
    if [ -f "$root/run-client.json" ]; then
      "$RUN_CLIENT" stop --run-root "$root" --timeout 5 >/dev/null 2>&1 || true
    fi
  done
  rm -rf "$tmpdir"
}
trap cleanup EXIT

mkdir -p "$bindir" "$ready_dir"

# A direct /bin/sh shebang keeps the process name 1cv8, as with the real platform binary.
cat >"$bindir/1cv8" <<'EOF'
#!/bin/sh
# Fixture client: prints its arguments, reports progress to the /C path, then idles until stopped.
progress=""
previous=""
for arg in "$@"; do
  printf 'arg=%s\n' "$arg"
  [ "$previous" = "/C" ] && progress="$arg"
  previous="$arg"
done
printf 'display=%s\n' "${DISPLAY:-}"
if [ -n "$progress" ] && [ "$progress" != "no-progress" ]; then
  printf 'opened\n' >"$progress"
fi
while :; do sleep 0.2; done
EOF

cat >"$bindir/xpra" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  start-desktop) : >"$ONEC_FAKE_XPRA_READY_DIR/${2#:}" ;;
  stop) rm -f -- "$ONEC_FAKE_XPRA_READY_DIR/${2#:}" ;;
esac
exit 0
EOF

cat >"$bindir/xdpyinfo" <<'EOF'
#!/usr/bin/env bash
[ -f "$ONEC_FAKE_XPRA_READY_DIR/${DISPLAY#:}" ]
EOF

cat >"$bindir/import" <<'EOF'
#!/usr/bin/env bash
[ -f "$ONEC_FAKE_XPRA_READY_DIR/${DISPLAY#:}" ] || exit 1
printf 'PNG %s\n' "$DISPLAY" >"${!#}"
EOF

cat >"$bindir/xdotool" <<'EOF'
#!/usr/bin/env bash
printf '%s %s\n' "$DISPLAY" "$*" >>"$ONEC_FAKE_INPUT_LOG"
EOF

for tool in Xvfb openbox; do
  printf '#!/usr/bin/env bash\nexit 0\n' >"$bindir/$tool"
done
for tool in xwininfo xprop; do
  printf '#!/usr/bin/env bash\nexit 1\n' >"$bindir/$tool"
done
chmod +x "$bindir"/*

cat >"$profile" <<EOF
{
  "schemaVersion": 3,
  "profileName": "run-client-fixture",
  "platform": {
    "binaryPath": "$bindir/1cv8",
    "xpra": {"enabled": true, "startChild": "openbox", "xvfbArgs": ["Xvfb", "-screen", "0", "1024x768x24", "-auth", "\$XAUTHORITY"]}
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/infobase",
    "auth": {"mode": "user-password", "user": "Operator", "passwordEnv": "RUN_CLIENT_FIXTURE_PASSWORD"}
  },
  "capabilities": {}
}
EOF

export PATH="$bindir:$PATH"
export RUN_CLIENT_FIXTURE_PASSWORD="$secret"
export ONEC_FAKE_XPRA_READY_DIR="$ready_dir"
export ONEC_FAKE_INPUT_LOG="$input_log"
export ONEC_OBSERVATION_INTERVAL_SECONDS=1
export ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MIN=940
export ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MAX=960
unset TECHLOG_CONFIG_PATH

fail() {
  printf 'run-client-contract: %s\n' "$1" >&2
  shift
  for file in "$@"; do
    [ -f "$file" ] && { printf -- '--- %s\n' "$file" >&2; cat "$file" >&2; }
  done
  exit 1
}

assert_no_secret() {
  local hits=""
  hits="$(grep -rlF -- "$secret" "$@" 2>/dev/null || true)"
  [ -z "$hits" ] || fail "password found in: $hits"
}

# 1. Dry-run shows the password only as ***.
"$RUN_CLIENT" start --profile "$profile" --run-root "$tmpdir/dry" --dry-run >"$tmpdir/dry.json"
jq -e '.command | index("/P") as $i | .[$i + 1] == "***"' "$tmpdir/dry.json" >/dev/null || fail "dry-run mask" "$tmpdir/dry.json"
assert_no_secret "$tmpdir/dry.json"

# 2. Two background clients, each in an own Xpra session of its run-root.
"$RUN_CLIENT" start --profile "$profile" --run-root "$run_a" --ready-timeout 30 >"$tmpdir/start-a.json" \
  || fail "start a" "$tmpdir/start-a.json" "$run_a/session.log"
"$RUN_CLIENT" start --profile "$profile" --run-root "$run_b" --ready-timeout 30 >"$tmpdir/start-b.json" \
  || fail "start b" "$tmpdir/start-b.json" "$run_b/session.log"
display_a="$(jq -r '.display' "$tmpdir/start-a.json")"
display_b="$(jq -r '.display' "$tmpdir/start-b.json")"
[ -n "$display_a" ] && [ "$display_a" != "null" ] || fail "no display for run-root a" "$tmpdir/start-a.json"
[ "$display_a" != "$display_b" ] || fail "run-roots share display $display_a"
pid_b="$(jq -r '.client_pid' "$tmpdir/start-b.json")"

"$RUN_CLIENT" status --run-root "$run_a" | jq -e '.client_alive == true' >/dev/null || fail "status a"
"$RUN_CLIENT" screenshot --run-root "$run_a" --out "$tmpdir/shot-a.png" >/dev/null || fail "screenshot a"
grep -qx "PNG $display_a" "$tmpdir/shot-a.png" || fail "screenshot taken from another display" "$tmpdir/shot-a.png"
"$RUN_CLIENT" key --run-root "$run_a" Escape >/dev/null || fail "key a"
"$RUN_CLIENT" click --run-root "$run_a" 10 20 >/dev/null || fail "click a"
if grep -v "^$display_a " "$input_log" | grep -q .; then
  fail "input reached another display" "$input_log"
fi

# 3. Stop acts only on its own run-root.
"$RUN_CLIENT" stop --run-root "$run_a" --timeout 15 | jq -e '.status == "stopped"' >/dev/null || fail "stop a"
kill -0 "$pid_b" 2>/dev/null || fail "client of run-root b was stopped by run-root a"
"$RUN_CLIENT" status --run-root "$run_b" | jq -e '.client_alive == true' >/dev/null || fail "status b after stop a"
if "$RUN_CLIENT" screenshot --run-root "$run_a" >/dev/null 2>&1; then
  fail "screenshot of a stopped run-root succeeded"
fi
for _ in $(seq 1 50); do
  jq -e '.observation.terminalEvent != null' "$run_a/summary.json" >/dev/null 2>&1 && break
  sleep 0.2
done
jq -e '.observation.terminalReason == "operator-stop"' "$run_a/summary.json" >/dev/null \
  || fail "operator stop is not the terminal reason" "$run_a/summary.json" "$run_a/observation.jsonl"
"$RUN_CLIENT" stop --run-root "$run_b" --timeout 15 | jq -e '.status == "stopped"' >/dev/null || fail "stop b"
for _ in $(seq 1 50); do
  jq -e '.observation.terminalEvent != null' "$run_b/summary.json" >/dev/null 2>&1 && break
  sleep 0.2
done

# 4. --wait --idle-timeout: unchanged progress returns 125 with a screenshot.
run_idle="$tmpdir/run-idle"
set +e
"$RUN_CLIENT" start --profile "$profile" --run-root "$run_idle" --c "$tmpdir/idle-progress.txt" \
  --wait --idle-timeout 2 --progress-file "$tmpdir/idle-progress.txt" >"$tmpdir/idle.json" 2>"$tmpdir/idle.err"
idle_exit=$?
set -e
[ "$idle_exit" -eq 125 ] || fail "idle-timeout exit=$idle_exit" "$tmpdir/idle.json" "$tmpdir/idle.err"
jq -e '.status == "idle-timeout"' "$tmpdir/idle.json" >/dev/null || fail "idle status" "$tmpdir/idle.json"
[ -f "$run_idle/screenshots/idle-timeout.png" ] || fail "idle-timeout screenshot missing" "$tmpdir/idle.json"
jq -e '.observation.terminalReason == "stalled"' "$run_idle/summary.json" >/dev/null || fail "idle summary" "$run_idle/summary.json"

# 5. --wait --timeout without progress returns 124.
run_timeout="$tmpdir/run-timeout"
set +e
"$RUN_CLIENT" start --profile "$profile" --run-root "$run_timeout" --c no-progress \
  --wait --timeout 2 >"$tmpdir/timeout.json" 2>"$tmpdir/timeout.err"
timeout_exit=$?
set -e
[ "$timeout_exit" -eq 124 ] || fail "timeout exit=$timeout_exit" "$tmpdir/timeout.json" "$tmpdir/timeout.err"
[ -f "$run_timeout/screenshots/timeout.png" ] || fail "timeout screenshot missing" "$tmpdir/timeout.json"

# 6. No artifact of any run-root holds the password.
assert_no_secret "$run_a" "$run_b" "$run_idle" "$run_timeout" "$tmpdir"/*.json "$tmpdir"/*.err
grep -rqF -- '***' "$run_a/stdout.log" || fail "masked password not shown in stdout.log" "$run_a/stdout.log"

printf 'run-client-contract: ok\n'
