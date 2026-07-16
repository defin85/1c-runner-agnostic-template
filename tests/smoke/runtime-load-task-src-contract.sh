#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fixture_root="$tmpdir/repo"
fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"
run_work_item_root="$tmpdir/run-work-item"
run_work_item_root="$tmpdir/run-work-item"

mkdir -p "$fixture_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
mkdir -p \
  "$fixture_root/env" \
  "$fixture_root/src/cf/Catalogs" \
  "$fixture_root/src/cf/Forms" \
  "$fixture_root/src/cf/EventSubscriptions" \
  "$fixture_root/src/cf/CommonModules/рлф_Тест/Ext"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

chmod +x "$fake_designer" "$fake_ibcmd"

cat >"$fixture_root/env/local.json" <<EOF
{
  "schemaVersion": 2,
  "profileName": "load-task-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/load-task-fixture",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/server"
    },
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/file-ib/db"
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf"
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

printf '<items baseline />\n' >"$fixture_root/src/cf/Catalogs/Items.xml"
printf '<list baseline />\n' >"$fixture_root/src/cf/Forms/List.xml"
printf '<config baseline />\n' >"$fixture_root/src/cf/Configuration.xml"

(
  cd "$fixture_root"
  git init >/dev/null
  git config core.quotepath true
  git config user.name "Smoke Fixture"
  git config user.email "smoke@example.invalid"
  git add .
  git commit -m "fixture baseline" >/dev/null
)

printf '<config changed />\n' >"$fixture_root/src/cf/Configuration.xml"
printf '<subscription new />\n' >"$fixture_root/src/cf/EventSubscriptions/LoadTask.xml"
printf 'Процедура Тест() Экспорт\nКонецПроцедуры\n' >"$fixture_root/src/cf/CommonModules/рлф_Тест/Ext/Module.bsl"
(
  cd "$fixture_root"
  git add src/cf/Configuration.xml src/cf/EventSubscriptions/LoadTask.xml src/cf/CommonModules/рлф_Тест/Ext/Module.bsl
  git commit -m $'task commit one\n\nWork-Item: 93984' >/dev/null
)

printf '<items changed />\n' >"$fixture_root/src/cf/Catalogs/Items.xml"
(
  cd "$fixture_root"
  git add src/cf/Catalogs/Items.xml
  git commit -m $'task commit two\n\nWork-Item: 93985' >/dev/null
)

printf '<list unrelated />\n' >"$fixture_root/src/cf/Forms/List.xml"
(
  cd "$fixture_root"
  git add src/cf/Forms/List.xml
  git commit -m $'unrelated task\n\nWork-Item: 77777' >/dev/null
)

export ONEC_IBCMD_PASSWORD="load-task-secret"

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
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
  cd "$fixture_root"
  ./scripts/platform/load-task-src.sh --profile env/local.json --run-root "$run_work_item_root" --work-item 93984 >/dev/null
)

assert_jq "$run_work_item_root/summary.json" '.status == "success"' "work-item-status"
assert_jq "$run_work_item_root/summary.json" '.capability.id == "load-task-src"' "work-item-capability"
assert_jq "$run_work_item_root/summary.json" '.execution.source == "git-task-to-load-src"' "work-item-source"
assert_jq "$run_work_item_root/summary.json" '.selection.selector.mode == "work-item"' "work-item-selector-mode"
assert_jq "$run_work_item_root/summary.json" '.selection.selector.value == "93984"' "work-item-selector-value"
assert_jq "$run_work_item_root/summary.json" '.selection.selected_commits | length == 1' "work-item-selected-commit-count"
assert_jq "$run_work_item_root/summary.json" '(.selection.selected_files | sort) == ["CommonModules/рлф_Тест/Ext/Module.bsl", "Configuration.xml", "EventSubscriptions/LoadTask.xml"]' "work-item-selected-files"
assert_jq "$run_work_item_root/summary.json" '.selection.ignored_files == []' "work-item-ignored-empty"
assert_jq "$run_work_item_root/summary.json" '.selection.deleted_paths == []' "work-item-deleted-empty"
assert_jq "$run_work_item_root/summary.json" '.delegated.capability == "load-src"' "work-item-delegated-capability"
assert_jq "$run_work_item_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "work-item-delegated-run-root" \
  --args "$run_work_item_root/load-src"
assert_jq "$run_work_item_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "work-item-delegated-summary-json" \
  --args "$run_work_item_root/load-src/summary.json"
assert_jq "$run_work_item_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "work-item-delegated-stdout-log" \
  --args "$run_work_item_root/load-src/stdout.log"
assert_jq "$run_work_item_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "work-item-delegated-stderr-log" \
  --args "$run_work_item_root/load-src/stderr.log"
assert_jq "$run_work_item_root/load-src/summary.json" '.driver == "ibcmd"' "work-item-delegated-driver"
assert_jq "$run_work_item_root/load-src/summary.json" '.driver_context.partial_import == true' "work-item-partial-import"
assert_contains "$run_work_item_root/load-src/stdout.log" "--partial"
assert_contains "$run_work_item_root/load-src/stdout.log" "CommonModules/рлф_Тест/Ext/Module.bsl"
assert_contains "$run_work_item_root/load-src/stdout.log" "Configuration.xml"
assert_contains "$run_work_item_root/load-src/stdout.log" "EventSubscriptions/LoadTask.xml"

(
  cd "$fixture_root"
  ./scripts/platform/load-task-src.sh --profile env/local.json --run-root "$run_work_item_root" --work-item 93984 >/dev/null
)

assert_jq "$run_work_item_root/summary.json" '.status == "success"' "work-item-status"
assert_jq "$run_work_item_root/summary.json" '.selection.selector.mode == "work-item"' "work-item-selector-mode"
assert_jq "$run_work_item_root/summary.json" '.selection.selector.value == "93984"' "work-item-selector-value"
assert_jq "$run_work_item_root/summary.json" '.selection.selected_commits | length == 1' "work-item-selected-commit-count"
assert_jq "$run_work_item_root/summary.json" '(.selection.selected_files | sort) == ["CommonModules/рлф_Тест/Ext/Module.bsl", "Configuration.xml", "EventSubscriptions/LoadTask.xml"]' "work-item-selected-files"
assert_jq "$run_work_item_root/summary.json" '.selection.ignored_files == []' "work-item-ignored-empty"
assert_jq "$run_work_item_root/summary.json" '.delegated.capability == "load-src"' "work-item-delegated-capability"
assert_jq "$run_work_item_root/summary.json" '.delegated.run_root == $ARGS.positional[0]' "work-item-delegated-run-root" \
  --args "$run_work_item_root/load-src"
assert_jq "$run_work_item_root/summary.json" '.delegated.summary_json == $ARGS.positional[0]' "work-item-delegated-summary-json" \
  --args "$run_work_item_root/load-src/summary.json"
assert_jq "$run_work_item_root/summary.json" '.delegated.stdout_log == $ARGS.positional[0]' "work-item-delegated-stdout-log" \
  --args "$run_work_item_root/load-src/stdout.log"
assert_jq "$run_work_item_root/summary.json" '.delegated.stderr_log == $ARGS.positional[0]' "work-item-delegated-stderr-log" \
  --args "$run_work_item_root/load-src/stderr.log"
assert_contains "$run_work_item_root/load-src/stdout.log" "CommonModules/рлф_Тест/Ext/Module.bsl"
assert_contains "$run_work_item_root/load-src/stdout.log" "Configuration.xml"
assert_contains "$run_work_item_root/load-src/stdout.log" "EventSubscriptions/LoadTask.xml"
