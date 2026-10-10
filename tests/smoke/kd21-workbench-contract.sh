#!/usr/bin/env bash
# Contract of scripts/migration/kd-rules-cycle on a fixture stage command (tests/fixtures/kd21/fake_stage.py):
# no 1C, no PostgreSQL. Checks:
# - without the materialized module the command fails with a hint to optional-module-init;
# - doctor refuses a workbase that is a reference base or is missing from expendableDatabases, and no base is reset;
# - `run build-rules` publishes the release with status rules-built without running any base command;
# - `all` gives workbench-run-passed with stage and top-level observation, source-before == source-after;
# - a second generation with --baseline-result gives workbench-ready; the same generation fails with `same generation`;
# - a baseline with other release hashes fails with `release hashes differ from baseline generation`;
# - a changed structure pin in the same run-root fails with `inputs changed`;
# - a second run of a running profile fails with `profile is already running`;
# - after a failed stage the later stages do not run and the run-root refuses further stages;
# - a stalled load is stopped by the observation adapter at runtimeStageTimeoutSeconds;
# - `run <node>` refuses while the node dependency is not ready and does not run the dependency.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
CYCLE="$ROOT/scripts/migration/kd-rules-cycle"
FIXTURE="$ROOT/tests/fixtures/kd21"

tmpdir="$(mktemp -d)"
background_pid=""
cleanup() {
  if [ -n "$background_pid" ]; then
    kill "$background_pid" 2>/dev/null || true
    wait "$background_pid" 2>/dev/null || true
  fi
  rm -rf "$tmpdir"
}
trap cleanup EXIT

export ONEC_OBSERVATION_INTERVAL_SECONDS=1
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BIN="${ONEC_PYTHON:-$(command -v python3 || command -v python)}"
log="$tmpdir/stages.log"
: >"$log"
mkdir -p "$tmpdir/env" "$tmpdir/snapshots" "$tmpdir/locks"
printf 'source reference snapshot\n' >"$tmpdir/snapshots/source_reference.dump"
printf 'target reference snapshot\n' >"$tmpdir/snapshots/target_reference.dump"
for name in source_copy target_copy; do
  printf '{"ibcmd": {"dbmsInfobase": {"name": "%s"}}}\n' "$name" >"$tmpdir/env/$name.json"
done

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

# write_profile <file> <load mode> [<source workbase database>] [<runtime timeout>] [<profile id>]
write_profile() {
  "$PYTHON_BIN" - "$tmpdir" "$1" "$2" "${3:-source_copy}" "${4:-60}" "${5:-fixture-kd21}" "$log" <<'PY'
import json, sys
tmp, path, mode, source_db, timeout, profile_id, log = sys.argv[1:]
stage = ["{python}", "tests/fixtures/kd21/fake_stage.py", "--log", log]
profile = {
    "schemaVersion": 1,
    "profileId": profile_id,
    "releasePublishRoot": f"{tmp}/publish-{profile_id}",
    "lockDirectory": f"{tmp}/locks",
    "limits": {"runtimeStageTimeoutSeconds": int(timeout), "minFreeBytes": 0, "maxReleaseBytes": 10485760},
    "references": [
        {"role": "source", "database": "source_reference", "snapshot": f"{tmp}/snapshots/source_reference.dump"},
        {"role": "target", "database": "target_reference", "snapshot": f"{tmp}/snapshots/target_reference.dump"},
    ],
    "workbases": [
        {"role": "source", "database": source_db, "runtimeProfile": f"{tmp}/env/source_copy.json", "target": "source-copy"},
        {"role": "target", "database": "target_copy", "runtimeProfile": f"{tmp}/env/target_copy.json", "target": "target-copy"},
    ],
    "expendableDatabases": ["source_copy", "target_copy", "source_reference"] if source_db == "source_reference"
    else ["source_copy", "target_copy"],
    "commands": {"reset": stage + ["--mode", "ok"], "load": stage + ["--mode", mode, "--seconds", "4"]},
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(profile, stream, ensure_ascii=False, indent=2)
PY
}

json_field() {
  "$PYTHON_BIN" -c 'import json,sys; v=json.load(open(sys.argv[1],encoding="utf-8"))
for key in sys.argv[2].split("."): v=v[key]
print(v)' "$1" "$2"
}

# run_cycle <name> <args...>: stores stdout/stderr in $tmpdir/<name>.out/.err and the exit code in $rc.
run_cycle() {
  local name="$1"
  shift
  rc=0
  "$CYCLE" "$@" >"$tmpdir/$name.out" 2>"$tmpdir/$name.err" || rc=$?
}

expect_failure() {
  local name="$1" text="$2"
  [ "$rc" -ne 0 ] || fail "$name: expected a failure"
  grep -Fq -- "$text" "$tmpdir/$name.err" || { cat "$tmpdir/$name.err" >&2; fail "$name: missing message: $text"; }
}

expect_success() {
  local name="$1"
  [ "$rc" -eq 0 ] || { cat "$tmpdir/$name.err" >&2; fail "$name: exit code $rc"; }
}

scenario="$FIXTURE/scenario/scenario.json"
ok_profile="$tmpdir/ok.json"
write_profile "$ok_profile" ok

# 1. Module not materialized: clear error, no run-root created.
run_cycle missing --profile "$tmpdir/absent/local.json" --scenario "$scenario" --run-root "$tmpdir/runs/missing" doctor
expect_failure missing "optional-module-init MODULE=kd21-migration"
[ ! -e "$tmpdir/runs/missing" ] || fail "missing profile created a run-root"

# 2. Target equals the reference base: doctor fails, nothing is reset.
write_profile "$tmpdir/clash.json" ok source_reference
run_cycle clash --profile "$tmpdir/clash.json" --scenario "$scenario" --run-root "$tmpdir/runs/clash" all
expect_failure clash "is the reference database of role source"
[ "$(json_field "$tmpdir/runs/clash/result.json" failedStage)" = doctor ] || fail "clash: failedStage is not doctor"
[ ! -s "$log" ] || fail "clash: a base command ran"
"$PYTHON_BIN" - "$tmpdir/clash.json" <<'PY'
import json, sys
profile = json.load(open(sys.argv[1], encoding="utf-8"))
profile["expendableDatabases"] = ["target_copy"]
profile["workbases"][0]["database"] = "source_copy"
json.dump(profile, open(sys.argv[1], "w", encoding="utf-8"))
PY
run_cycle unlisted --profile "$tmpdir/clash.json" --scenario "$scenario" --run-root "$tmpdir/runs/unlisted" doctor
expect_failure unlisted "is not listed in profile expendableDatabases"

# 3. Rules release without bases.
run_cycle rules --profile "$ok_profile" --scenario "$scenario" --run-root "$tmpdir/runs/rules" run build-rules
expect_success rules
[ "$(json_field "$tmpdir/runs/rules/result.json" status)" = rules-built ] || fail "rules: status is not rules-built"
published="$(json_field "$tmpdir/runs/rules/result.json" publishedRelease)"
[ "$published" = "$tmpdir/publish-fixture-kd21" ] || fail "rules: release published elsewhere: $published"
[ "$(json_field "$tmpdir/runs/rules/result.json" manifestSha256)" = "$(json_field "$tmpdir/runs/rules/result.json" release.manifestSha256)" ] \
  || fail "rules: manifest SHA-256 differs"
for file in manifest.json source/ExchangeRules.xml source/RegistrationRules.xml target/ExchangeRules.xml \
  target/CorrespondentExchangeRules.xml target/RegistrationRules.xml source/ExchangeRules.zip \
  source/RegistrationRules.zip target/Rules.zip; do
  [ -f "$published/$file" ] || fail "rules: missing published $file"
done
[ ! -s "$log" ] || fail "rules: build-rules ran a base command"
[ ! -e "$tmpdir/runs/rules/source-before.json" ] || fail "rules: build-rules read the reference bases"

# 4. Full run: workbench-run-passed with observation.
run_cycle first --profile "$ok_profile" --scenario "$scenario" --run-root "$tmpdir/runs/first" all
expect_success first
first_result="$tmpdir/runs/first/result.json"
[ "$(json_field "$first_result" status)" = workbench-run-passed ] || fail "first: status"
for line in "reset source" "reset target" "load source" "load target"; do
  grep -Fxq "$line" "$log" || fail "first: stage command did not run: $line"
done
cmp -s "$tmpdir/runs/first/source-before.json" "$tmpdir/runs/first/source-after.json" || fail "first: reference fingerprints differ"
grep -q '"event": *"completed"' "$tmpdir/runs/first/observation.jsonl" || fail "first: top-level observation has no completed event"
grep -q '"event": *"completed"' "$tmpdir/runs/first/stages/load/target/observation.jsonl" || fail "first: load observation"
grep -Fq "stage:verify" "$tmpdir/runs/first/progress.txt" || fail "first: progress.txt does not name the last stage"
[ "$(json_field "$tmpdir/runs/first/state.json" schemaVersion)" = 2 ] || fail "first: state.json is not schema 2"

# 5. Second generation: workbench-ready; the same generation again: `same generation`.
run_cycle second --profile "$ok_profile" --scenario "$scenario" --run-root "$tmpdir/runs/second" --baseline-result "$first_result" all
expect_success second
[ "$(json_field "$tmpdir/runs/second/result.json" status)" = workbench-ready ] || fail "second: status"
cp "$tmpdir/runs/second/result.json" "$tmpdir/second-result.json"
run_cycle same --profile "$ok_profile" --scenario "$scenario" --run-root "$tmpdir/runs/second" --baseline-result "$tmpdir/second-result.json" verify
expect_failure same "same generation"
[ "$(json_field "$tmpdir/runs/second/result.json" status)" = failed ] || fail "same: status is not failed"

# 6. Baseline with other release hashes.
cp -R "$tmpdir/runs/first/release" "$tmpdir/tampered-release"
"$PYTHON_BIN" - "$first_result" "$tmpdir/tampered-release" "$tmpdir/tampered-result.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1], encoding="utf-8"))
manifest_path = sys.argv[2] + "/manifest.json"
manifest = json.load(open(manifest_path, encoding="utf-8"))
manifest["files"]["source/ExchangeRules.xml"] = "0" * 64
json.dump(manifest, open(manifest_path, "w", encoding="utf-8"))
result["release"]["path"] = sys.argv[2]
json.dump(result, open(sys.argv[3], "w", encoding="utf-8"))
PY
run_cycle differ --profile "$ok_profile" --scenario "$scenario" --run-root "$tmpdir/runs/differ" --baseline-result "$tmpdir/tampered-result.json" all
expect_failure differ "release hashes differ from baseline generation"

# 7. Inputs changed in the same run-root.
cp -R "$FIXTURE/scenario" "$tmpdir/scenario-copy"
run_cycle inputs-a --profile "$ok_profile" --scenario "$tmpdir/scenario-copy" --run-root "$tmpdir/runs/inputs" doctor
expect_success inputs-a
"$PYTHON_BIN" - "$tmpdir/scenario-copy/scenario.json" <<'PY'
import json, sys
scenario = json.load(open(sys.argv[1], encoding="utf-8"))
scenario["inputs"]["sourceStructureSha256"] = "1" * 64
json.dump(scenario, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PY
run_cycle inputs-b --profile "$ok_profile" --scenario "$tmpdir/scenario-copy" --run-root "$tmpdir/runs/inputs" doctor
expect_failure inputs-b "inputs changed; use a new --run-root and reset"

# 8. Profile lock.
slow_profile="$tmpdir/slow.json"
write_profile "$slow_profile" slow source_copy 60 fixture-kd21-slow
"$CYCLE" --profile "$slow_profile" --scenario "$scenario" --run-root "$tmpdir/runs/slow" all \
  >"$tmpdir/slow.out" 2>"$tmpdir/slow.err" &
background_pid=$!
for _ in $(seq 1 100); do
  [ -f "$tmpdir/locks/fixture-kd21-slow.lock" ] && break
  sleep 0.1
done
[ -f "$tmpdir/locks/fixture-kd21-slow.lock" ] || fail "lock: the first run did not take the profile lock"
run_cycle locked --profile "$slow_profile" --scenario "$scenario" --run-root "$tmpdir/runs/locked" doctor
expect_failure locked "profile is already running"
wait "$background_pid" || fail "lock: the first run failed: $(cat "$tmpdir/slow.err")"
background_pid=""

# 9. Stop after a failed stage.
: >"$log"
write_profile "$tmpdir/fail.json" fail
run_cycle failed --profile "$tmpdir/fail.json" --scenario "$scenario" --run-root "$tmpdir/runs/failed" all
expect_failure failed "load source failed"
[ "$(json_field "$tmpdir/runs/failed/result.json" status)" = failed ] || fail "failed: status"
[ "$(json_field "$tmpdir/runs/failed/result.json" failedStage)" = load ] || fail "failed: failedStage"
[ "$(json_field "$tmpdir/runs/failed/result.json" stages.verify)" = pending ] || fail "failed: verify ran"
if grep -Fq "load target" "$log"; then fail "failed: load continued after the failure"; fi
run_cycle failed-again --profile "$tmpdir/fail.json" --scenario "$scenario" --run-root "$tmpdir/runs/failed" verify
expect_failure failed-again "run-root failed at load"

# 10. Stalled load stopped by the observation adapter.
write_profile "$tmpdir/stall.json" stall source_copy 2
run_cycle stall --profile "$tmpdir/stall.json" --scenario "$scenario" --run-root "$tmpdir/runs/stall" all
expect_failure stall "load source failed: stalled"
grep -q '"event": *"failed"' "$tmpdir/runs/stall/stages/load/source/observation.jsonl" || fail "stall: no terminal failed event"
[ "$(json_field "$tmpdir/runs/stall/result.json" status)" = failed ] || fail "stall: status"

# 11. Node with a dependency that is not ready.
: >"$log"
"$PYTHON_BIN" - "$FIXTURE/scenario/scenario.json" "$tmpdir/scenario-node" "$log" <<'PY'
import json, shutil, sys
from pathlib import Path
source, target, log = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
shutil.copytree(source.parent, target)
scenario = json.loads(source.read_text(encoding="utf-8"))
scenario["nodes"] = [{
    "name": "apply-extension", "dependencies": ["load"], "retry": "idempotent-retry",
    "command": ["{python}", "tests/fixtures/kd21/fake_stage.py", "--log", log],
}]
(target / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
PY
run_cycle node --profile "$ok_profile" --scenario "$tmpdir/scenario-node" --run-root "$tmpdir/runs/node" run apply-extension
expect_failure node "dependency not ready for apply-extension: load"
[ ! -s "$log" ] || fail "node: a dependency ran automatically"

printf 'kd21-workbench-contract: ok\n'
