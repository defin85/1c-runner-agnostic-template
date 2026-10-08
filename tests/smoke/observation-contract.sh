#!/usr/bin/env bash
set -euo pipefail

# Contract of the shared long-operation observation adapter on fixture processes:
# one terminal event, failed without the expected result, stop only with a threshold,
# bounded technological log restored byte for byte after an error and after a killed observer.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
RUN_PYTHON="$SOURCE_ROOT/scripts/python/run-python.sh"
TECHLOG="$SOURCE_ROOT/scripts/diag/technological-log.sh"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

export ONEC_OBSERVATION_INTERVAL_SECONDS=1
unset TECHLOG_CONFIG_PATH TECHLOG_ROOT TECHLOG_SERVER_ROOT TECHLOG_PRIVILEGED_COMMAND ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS

fail() {
  printf 'observation-contract: %s\n' "$1" >&2
  shift
  for file in "$@"; do
    [ -f "$file" ] && { printf -- '--- %s\n' "$file" >&2; cat "$file" >&2; }
  done
  exit 1
}

assert_jq() {
  local file="$1" expr="$2" label="$3"
  jq -e -s "$expr" "$file" >/dev/null || fail "$label: $expr" "$file"
}

observe() {
  local run_root="$1"
  shift
  set +e
  "$RUN_PYTHON" observe-command --capability fixture --target fixture --run-root "$run_root" "$@" \
    >"$run_root.out" 2>"$run_root.err"
  observed_exit=$?
  set -e
}

assert_one_terminal() {
  local run_root="$1" event="$2" reason="$3"
  local file="$run_root/observation.jsonl"
  [ -f "$file" ] || fail "observation.jsonl missing in $run_root" "$run_root.err"
  assert_jq "$file" '[.[] | select(.event == "started")] | length == 1' "one-started"
  assert_jq "$file" '[.[] | select(.event == "completed" or .event == "failed")] | length == 1' "one-terminal"
  jq -e -s --arg e "$event" '.[-1].event == $e' "$file" >/dev/null || fail "terminal event is not $event" "$file"
  jq -e -s --arg r "$reason" '.[-1].terminalReason == $r' "$file" >/dev/null || fail "terminal reason is not $reason" "$file"
  assert_jq "$file" 'all(.[]; .schemaVersion == 1)' "schema-v1"
  jq -e --arg e "$event" '.observation.terminalEvent == $e' "$run_root/summary.json" >/dev/null \
    || fail "summary.json has no terminal section" "$run_root/summary.json"
}

# 1. Success: heartbeats and exactly one completed event.
run="$tmpdir/success"
mkdir -p "$run"
observe "$run" -- bash -c 'sleep 2.5'
[ "$observed_exit" -eq 0 ] || fail "success exit=$observed_exit" "$run.err"
assert_one_terminal "$run" completed completed
assert_jq "$run/observation.jsonl" '[.[] | select(.event == "heartbeat")] | length >= 1' "heartbeat"
grep -q 'event=heartbeat' "$run.err" || fail "operator heartbeat line missing" "$run.err"

# 2. Zero exit without the expected result is failed.
run="$tmpdir/missing-result"
mkdir -p "$run"
observe "$run" --expected-result "$run/result.xml" -- bash -c 'exit 0'
[ "$observed_exit" -eq 70 ] || fail "missing-result exit=$observed_exit" "$run.err"
assert_one_terminal "$run" failed missing-result

# 3. Unchanged progress with a threshold stops the whole process group.
run="$tmpdir/stalled"
mkdir -p "$run"
observe "$run" --progress-file "$run/progress.txt" --stall-timeout 2 -- \
  bash -c 'printf "stage-1\n" >"$ONEC_OBSERVATION_PROGRESS_FILE"; sleep 60 & printf "%s\n" "$!" >"'"$run"'/child.pid"; wait'
[ "$observed_exit" -eq 125 ] || fail "stalled exit=$observed_exit" "$run.err"
assert_one_terminal "$run" failed stalled
jq -e -s '.[-1].lastProgress == "stage-1"' "$run/observation.jsonl" >/dev/null || fail "lastProgress" "$run/observation.jsonl"
child_pid="$(cat "$run/child.pid")"
for _ in $(seq 1 50); do
  kill -0 "$child_pid" 2>/dev/null || break
  sleep 0.1
done
if kill -0 "$child_pid" 2>/dev/null; then
  fail "child of the stalled process group is still alive"
fi

# 4. Without a threshold the same progress is only reported as stage age.
run="$tmpdir/no-threshold"
mkdir -p "$run"
observe "$run" --progress-file "$run/progress.txt" -- \
  bash -c 'printf "stage-1\n" >"$ONEC_OBSERVATION_PROGRESS_FILE"; sleep 3.5'
[ "$observed_exit" -eq 0 ] || fail "no-threshold exit=$observed_exit" "$run.err"
assert_one_terminal "$run" completed completed
assert_jq "$run/observation.jsonl" '[.[] | select(.event == "heartbeat" and (.stageAgeSeconds // -1) >= 1)] | length >= 1' "stage-age"
grep -q 'stage_age=' "$run.err" || fail "operator stage age missing" "$run.err"

# 5. Bounded technological log is restored byte for byte after a failed command and a failed launch.
config="$tmpdir/conf/logcfg.xml"
mkdir -p "$(dirname -- "$config")"
printf '<?xml version="1.0"?>\r\n<config xmlns="http://v8.1c.ru/v8/tech-log">\r\n</config>\r\n' >"$config"
cp "$config" "$tmpdir/logcfg.original"
export TECHLOG_CONFIG_PATH="$config"

run="$tmpdir/techlog-error"
mkdir -p "$run"
observe "$run" -- bash -c 'exit 9'
[ "$observed_exit" -eq 9 ] || fail "command error exit=$observed_exit" "$run.err"
cmp -s "$config" "$tmpdir/logcfg.original" || fail "logcfg.xml not restored after command error" "$config"
assert_one_terminal "$run" failed command-exit
jq -e -s '.[-1].technologicalLog.restored == true' "$run/observation.jsonl" >/dev/null \
  || fail "terminal event does not confirm restore" "$run/observation.jsonl"

run="$tmpdir/techlog-seen"
mkdir -p "$run"
observe "$run" -- bash -c 'cp "'"$config"'" "'"$run"'/seen.xml"'
grep -q 'temporary bounded technological log' "$run/seen.xml" || fail "temporary config was not active" "$run/seen.xml"
for forbidden in call scall sdbl dbmssql dbpostgrs system; do
  if grep -qi "value=\"$forbidden\"" "$run/seen.xml"; then
    fail "forbidden event $forbidden in temporary config" "$run/seen.xml"
  fi
done
cmp -s "$config" "$tmpdir/logcfg.original" || fail "logcfg.xml not restored after success" "$config"

run="$tmpdir/techlog-launch-failure"
mkdir -p "$run"
observe "$run" -- "$tmpdir/missing-binary"
[ "$observed_exit" -eq 127 ] || fail "launch failure exit=$observed_exit" "$run.err"
cmp -s "$config" "$tmpdir/logcfg.original" || fail "logcfg.xml not restored after launch failure" "$config"

# 6. A killed observer leaves a restore record; the diagnostic command restores the original.
run="$tmpdir/techlog-killed"
mkdir -p "$run"
"$RUN_PYTHON" observe-command --capability fixture --target fixture --run-root "$run" -- bash -c 'sleep 3' \
  >"$run.out" 2>"$run.err" &
observer_pid=$!
for _ in $(seq 1 100); do
  grep -q 'temporary bounded technological log' "$config" 2>/dev/null && break
  sleep 0.1
done
grep -q 'temporary bounded technological log' "$config" || fail "temporary config was not installed" "$run.err"
kill -KILL "$observer_pid"
wait "$observer_pid" 2>/dev/null || true
"$TECHLOG" restore --run-root "$run" >/dev/null
cmp -s "$config" "$tmpdir/logcfg.original" || fail "logcfg.xml not restored by technological-log restore" "$config"
"$TECHLOG" status | jq -e '.temporary == false' >/dev/null || fail "status still reports a temporary config"

printf 'observation-contract: ok\n'
