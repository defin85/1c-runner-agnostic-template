#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

PROFILE_INPUT="${ONEC_PROFILE_PATH:-}"
RUN_ROOT_INPUT="${ONEC_CAPABILITY_RUN_ROOT:-}"
ADD_ROOT_OVERRIDE="${ONEC_XUNIT_ADD_ROOT:-}"
CONFIG_PATH_OVERRIDE="${ONEC_XUNIT_CONFIG_PATH:-}"
TARGET_REL_OVERRIDE="${ONEC_XUNIT_TARGET_REL:-}"
HARNESS_SOURCE_DIR_OVERRIDE="${ONEC_XUNIT_HARNESS_SOURCE_DIR:-}"
TIMEOUT_OVERRIDE="${ONEC_XUNIT_TIMEOUT_SECONDS:-}"

TIMEOUT_SECONDS=900
TESTCLIENT_PORT=""
MANAGER_DISPLAY=""
TESTCLIENT_DISPLAY=""
TIMED_OUT=false
STATUS_VALUE=""
MANAGER_EXIT_CODE=0
TESTCLIENT_EXIT_CODE=0
FINAL_EXIT_CODE=0
CLASSIFICATION=""

declare -a CLEANUP_PIDS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-xunit-direct-platform.sh [options]

Options:
  --profile <file>           Runtime profile JSON.
  --run-root <dir>           Capability run root.
  --add-root <path>          ADD/xdd assets root.
  --config-path <path>       smoke.quickstart.json source.
  --target-rel <path>        Relative EPF target inside copied ADD root.
  --harness-source-dir <p>   Source tree root for project-owned EPF harness.
  --timeout-seconds <n>      Total timeout for the xUnit contour.
  -h, --help                 Show this help.
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

array_length() {
  local array_name="$1"
  local item=""
  local count=0
  declare -n array_ref="$array_name"

  for item in "${array_ref[@]}"; do
    count=$((count + 1))
  done

  printf '%s\n' "$count"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || fail "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || fail "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --add-root)
        [ "$#" -ge 2 ] || fail "--add-root requires a value"
        ADD_ROOT_OVERRIDE="$2"
        shift 2
        ;;
      --config-path)
        [ "$#" -ge 2 ] || fail "--config-path requires a value"
        CONFIG_PATH_OVERRIDE="$2"
        shift 2
        ;;
      --target-rel)
        [ "$#" -ge 2 ] || fail "--target-rel requires a value"
        TARGET_REL_OVERRIDE="$2"
        shift 2
        ;;
      --harness-source-dir)
        [ "$#" -ge 2 ] || fail "--harness-source-dir requires a value"
        HARNESS_SOURCE_DIR_OVERRIDE="$2"
        shift 2
        ;;
      --timeout-seconds)
        [ "$#" -ge 2 ] || fail "--timeout-seconds requires a value"
        TIMEOUT_OVERRIDE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

resolve_profile_input() {
  local resolved=""

  if [ -n "$PROFILE_INPUT" ]; then
    resolved="$PROFILE_INPUT"
  else
    resolved="$(resolve_runtime_profile_path "" "$PROJECT_ROOT")"
  fi

  [ -n "$resolved" ] || fail "runtime profile is required"
  printf '%s\n' "$(canonical_path "$resolved")"
}

resolve_run_root_input() {
  local resolved=""

  if [ -n "$RUN_ROOT_INPUT" ]; then
    resolved="$(canonical_path "$RUN_ROOT_INPUT")"
    mkdir -p "$resolved"
    printf '%s\n' "$resolved"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/1c-xunit-direct.XXXXXX"
}

resolve_project_path() {
  local value="$1"

  case "$value" in
    /*)
      printf '%s\n' "$value"
      ;;
    *)
      printf '%s\n' "$(canonical_path "$PROJECT_ROOT/$value")"
      ;;
  esac
}

require_path_from_profile_or_override() {
  local override="$1"
  local expr="$2"
  local label="$3"
  local value=""

  if [ -n "$override" ]; then
    value="$override"
  else
    value="$(profile_string "$expr // empty")"
  fi

  [ -n "$value" ] || fail "runtime profile is missing $label in $RUNTIME_PROFILE_PATH"
  printf '%s\n' "$(resolve_project_path "$value")"
}

resolve_path_from_profile_or_default_or_override() {
  local override="$1"
  local expr="$2"
  local default_value="$3"
  local value=""

  if [ -n "$override" ]; then
    value="$override"
  else
    value="$(profile_string "$expr // empty")"
  fi

  if [ -z "$value" ]; then
    value="$default_value"
  fi

  printf '%s\n' "$(resolve_project_path "$value")"
}

resolve_string_from_profile_or_default_or_override() {
  local override="$1"
  local expr="$2"
  local default_value="$3"
  local value=""

  if [ -n "$override" ]; then
    value="$override"
  else
    value="$(profile_string "$expr // empty")"
  fi

  if [ -z "$value" ]; then
    value="$default_value"
  fi

  printf '%s\n' "$value"
}

resolve_optional_path_from_profile_or_override() {
  local override="$1"
  local expr="$2"
  local value=""

  if [ -n "$override" ]; then
    value="$override"
  else
    value="$(profile_string "$expr // empty")"
  fi

  if [ -z "$value" ]; then
    printf '\n'
    return 0
  fi

  printf '%s\n' "$(resolve_project_path "$value")"
}

platform_client_binary_path() {
  local binary_path=""
  local candidate=""

  binary_path="$(platform_binary_path)"
  candidate="$(dirname -- "$binary_path")/1cv8c"
  if [ -x "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  if [ -x "$binary_path" ] && [ "$(basename -- "$binary_path")" = "1cv8c" ]; then
    printf '%s\n' "$binary_path"
    return 0
  fi

  fail "platform client binary not found рядом с platform.binaryPath: $candidate"
}

pick_unused_tcp_port() {
  local min_port="$1"
  local max_port="$2"
  local candidate=""
  local attempt=0

  for attempt in $(seq 1 200); do
    candidate="$((min_port + RANDOM % (max_port - min_port + 1)))"
    if ! ss -ltn "( sport = :$candidate )" | awk 'NR > 1 { found=1 } END { exit(found ? 0 : 1) }'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  fail "failed to pick a free TCP port in range ${min_port}-${max_port}"
}

pick_unused_display() {
  local min_display="$1"
  local max_display="$2"
  local candidate=""
  local port=""
  local attempt=0

  for attempt in $(seq 1 200); do
    candidate="$((min_display + RANDOM % (max_display - min_display + 1)))"
    port="$((6000 + candidate))"
    if ! ss -ltn "( sport = :$port )" | awk 'NR > 1 { found=1 } END { exit(found ? 0 : 1) }'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  fail "failed to pick a free X display in range ${min_display}-${max_display}"
}

wait_for_display() {
  local label="$1"
  local display_number="$2"
  local pid="$3"
  local display_value="127.0.0.1:${display_number}"
  local attempt=0

  for attempt in $(seq 1 50); do
    if ! kill -0 "$pid" 2>/dev/null; then
      fail "$label Xvfb exited before becoming ready"
    fi

    if xdpyinfo -display "$display_value" >/dev/null 2>&1; then
      return 0
    fi

    sleep 0.2
  done

  fail "$label Xvfb did not become ready on DISPLAY=$display_value"
}

wait_for_listen_port() {
  local label="$1"
  local port="$2"
  local pid="$3"
  local attempt=0

  for attempt in $(seq 1 100); do
    if ! kill -0 "$pid" 2>/dev/null; then
      fail "$label exited before opening port $port"
    fi

    if ss -ltn "( sport = :$port )" | awk 'NR > 1 { found=1 } END { exit(found ? 0 : 1) }'; then
      return 0
    fi

    sleep 0.2
  done

  fail "$label did not open TCP port $port"
}

stop_pid_if_running() {
  local pid="$1"

  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi

  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
}

cleanup() {
  local pid=""

  for pid in "${CLEANUP_PIDS[@]}"; do
    stop_pid_if_running "$pid"
  done
}

strip_bom_and_newlines() {
  local file_path="$1"
  local value=""

  value="$(tr -d '\r\n' < "$file_path")"
  value="${value#$'\xEF\xBB\xBF'}"
  printf '%s' "$value"
}

is_nonempty_file() {
  local file_path="$1"

  [ -s "$file_path" ]
}

runtime_artifacts_ready() {
  is_nonempty_file "$STATUS_FILE" \
    && is_nonempty_file "$JUNIT_XML" \
    && is_nonempty_file "$ALLURE_XML" \
    && is_nonempty_file "$TEXT_LOG"
}

normalize_allure_report() {
  local -a candidates=()

  if is_nonempty_file "$ALLURE_XML"; then
    return 0
  fi

  mapfile -t candidates < <(find "$REPORTS_DIR" -maxdepth 1 -type f -name '*allure-testsuite.xml' -size +0c | sort)
  if [ "$(array_length candidates)" -eq 1 ]; then
    cp "${candidates[0]}" "$ALLURE_XML"
  fi
}

write_command_file() {
  local file_path="$1"
  shift
  local -a env_items=()
  local -a cmd_items=()
  local item=""
  local seen_separator=false

  for item in "$@"; do
    if [ "$seen_separator" = false ]; then
      if [ "$item" = "--" ]; then
        seen_separator=true
      else
        env_items+=("$item")
      fi
    else
      cmd_items+=("$item")
    fi
  done

  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -euo pipefail\n'
    printf 'cd %q\n' "$PROJECT_ROOT"
    printf 'env '
    printf '%q ' "${env_items[@]}"
    printf '%q ' "${cmd_items[@]}"
    printf '\n'
  } > "$file_path"

  chmod +x "$file_path"
}

build_exit_code() {
  if [ "$TIMED_OUT" = true ]; then
    CLASSIFICATION="timeout"
    FINAL_EXIT_CODE=124
    return 0
  fi

  if is_nonempty_file "$STATUS_FILE"; then
    STATUS_VALUE="$(strip_bom_and_newlines "$STATUS_FILE")"
    if ! [[ "$STATUS_VALUE" =~ ^[0-9]+$ ]]; then
      CLASSIFICATION="invalid_status_value"
      FINAL_EXIT_CODE=2
      return 0
    fi

    if [ "$STATUS_VALUE" = "0" ] && runtime_artifacts_ready; then
      CLASSIFICATION="success"
      FINAL_EXIT_CODE=0
      return 0
    fi

    if [ "$STATUS_VALUE" = "0" ]; then
      CLASSIFICATION="missing_result_artifacts"
      FINAL_EXIT_CODE=2
      return 0
    fi

    CLASSIFICATION="status_${STATUS_VALUE}"
    if [ "$STATUS_VALUE" -le 255 ]; then
      FINAL_EXIT_CODE="$STATUS_VALUE"
    else
      FINAL_EXIT_CODE=1
    fi
    return 0
  fi

  if [ "$MANAGER_EXIT_CODE" -ne 0 ] || [ "$TESTCLIENT_EXIT_CODE" -ne 0 ]; then
    CLASSIFICATION="process_error"
    if [ "$MANAGER_EXIT_CODE" -ne 0 ] && [ "$MANAGER_EXIT_CODE" -ne 143 ]; then
      FINAL_EXIT_CODE="$MANAGER_EXIT_CODE"
    elif [ "$TESTCLIENT_EXIT_CODE" -ne 0 ] && [ "$TESTCLIENT_EXIT_CODE" -ne 143 ]; then
      FINAL_EXIT_CODE="$TESTCLIENT_EXIT_CODE"
    else
      FINAL_EXIT_CODE=1
    fi
    return 0
  fi

  CLASSIFICATION="missing_status_file"
  FINAL_EXIT_CODE=2
}

write_summary() {
  jq -n \
    --arg profile_path "$RUNTIME_PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg add_root "$ADD_ROOT" \
    --arg config_path "$CONFIG_PATH" \
    --arg config_runtime "$XUNIT_CONFIG_RUNTIME" \
    --arg harness_source_dir "${HARNESS_SOURCE_DIR:-}" \
    --arg harness_output_epf "${HARNESS_OUTPUT_EPF:-}" \
    --arg harness_build_log "${HARNESS_BUILD_LOG:-}" \
    --arg xdd_target_rel "$XDD_RUN_TARGET_REL" \
    --arg xdd_target "$XDD_RUN_TARGET" \
    --arg status_file "$STATUS_FILE" \
    --arg junit_xml "$JUNIT_XML" \
    --arg allure_xml "$ALLURE_XML" \
    --arg text_log "$TEXT_LOG" \
    --arg manager_stdout "$MANAGER_STDOUT" \
    --arg testclient_stdout "$TESTCLIENT_STDOUT" \
    --arg manager_out "$MANAGER_OUT" \
    --arg testclient_out "$TESTCLIENT_OUT" \
    --arg classification "$CLASSIFICATION" \
    --arg status_value "$STATUS_VALUE" \
    --arg testclient_port "$TESTCLIENT_PORT" \
    --arg manager_display "127.0.0.1:${MANAGER_DISPLAY}" \
    --arg testclient_display "127.0.0.1:${TESTCLIENT_DISPLAY}" \
    --argjson timeout_seconds "$TIMEOUT_SECONDS" \
    --argjson timed_out "$TIMED_OUT" \
    --argjson manager_exit_code "$MANAGER_EXIT_CODE" \
    --argjson testclient_exit_code "$TESTCLIENT_EXIT_CODE" \
    --argjson exit_code "$FINAL_EXIT_CODE" \
    '{
      profile_path: $profile_path,
      run_root: $run_root,
      assets: {
        add_root: $add_root,
        config_path: $config_path,
        config_runtime: $config_runtime,
        harness_source_dir: (if $harness_source_dir == "" then null else $harness_source_dir end),
        harness_output_epf: (if $harness_output_epf == "" then null else $harness_output_epf end),
        harness_build_log: (if $harness_build_log == "" then null else $harness_build_log end),
        xdd_target_rel: $xdd_target_rel,
        xdd_target: $xdd_target
      },
      runtime: {
        timeout_seconds: $timeout_seconds,
        timed_out: $timed_out,
        testclient_port: $testclient_port,
        manager_display: $manager_display,
        testclient_display: $testclient_display
      },
      result: {
        classification: $classification,
        status_value: (if $status_value == "" then null else $status_value end),
        exit_code: $exit_code,
        manager_exit_code: $manager_exit_code,
        testclient_exit_code: $testclient_exit_code
      },
      artifacts: {
        status_file: $status_file,
        junit_xml: $junit_xml,
        allure_xml: $allure_xml,
        text_log: $text_log,
        manager_stdout: $manager_stdout,
        testclient_stdout: $testclient_stdout,
        manager_out: $manager_out,
        testclient_out: $testclient_out
      }
    }' > "$RUN_ROOT/xunit-summary.json"
}

parse_args "$@"
trap cleanup EXIT

require_command jq
require_command ss
require_command Xvfb
require_command xdpyinfo

PROFILE_PATH="$(resolve_profile_input)"
RUN_ROOT="$(resolve_run_root_input)"
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded

[ "${RUNTIME_PROFILE_RUNNER_ADAPTER:-}" = "direct-platform" ] || fail "runnerAdapter=direct-platform is required"

ADD_ROOT="$(require_path_from_profile_or_override "$ADD_ROOT_OVERRIDE" '.capabilities.xunit.addRoot' 'capabilities.xunit.addRoot')"
CONFIG_PATH="$(resolve_path_from_profile_or_default_or_override "$CONFIG_PATH_OVERRIDE" '.capabilities.xunit.configPath' 'tests/xunit/smoke.quickstart.json')"
XDD_RUN_TARGET_REL="$(resolve_string_from_profile_or_default_or_override "$TARGET_REL_OVERRIDE" '.capabilities.xunit.xddRunTargetRel' 'tests/smoke/Tests_SmokeCommonModules.epf')"
HARNESS_SOURCE_DIR="$(resolve_path_from_profile_or_default_or_override "$HARNESS_SOURCE_DIR_OVERRIDE" '.capabilities.xunit.harnessSourceDir' 'src/epf/TemplateXUnitHarness')"
TIMEOUT_SECONDS="$(resolve_string_from_profile_or_default_or_override "$TIMEOUT_OVERRIDE" '.capabilities.xunit.timeoutSeconds' "$TIMEOUT_SECONDS")"

[ -d "$ADD_ROOT" ] || fail "ADD root not found: $ADD_ROOT"
[ -f "$CONFIG_PATH" ] || fail "xUnit config not found: $CONFIG_PATH"
[ -f "$ADD_ROOT/xddTestRunner.epf" ] || fail "xddTestRunner.epf not found under $ADD_ROOT"

if [ -n "$HARNESS_SOURCE_DIR" ]; then
  [ -d "$HARNESS_SOURCE_DIR" ] || fail "harness source dir not found: $HARNESS_SOURCE_DIR"
fi

CLIENT_BINARY="$(platform_client_binary_path)"
[ -x "$CLIENT_BINARY" ] || fail "client binary is not executable: $CLIENT_BINARY"

XUNIT_DIR="$RUN_ROOT/xunit"
XUNIT_ADD_ROOT="$XUNIT_DIR/add"
REPORTS_DIR="$XUNIT_DIR/reports"
WORKSPACE_DIR="$XUNIT_DIR/workspace"
XUNIT_CONFIG_RUNTIME="$XUNIT_DIR/smoke.quickstart.json"
XDD_RUN_TARGET="$XUNIT_ADD_ROOT/$XDD_RUN_TARGET_REL"
TEXT_LOG="$WORKSPACE_DIR/build/xunit/log.txt"
STATUS_FILE="$RUN_ROOT/status.txt"
MANAGER_OUT="$RUN_ROOT/manager.out.log"
TESTCLIENT_OUT="$RUN_ROOT/testclient.out.log"
MANAGER_STDOUT="$RUN_ROOT/manager.shell.stdout.log"
TESTCLIENT_STDOUT="$RUN_ROOT/testclient.shell.stdout.log"
MANAGER_XVFB_LOG="$RUN_ROOT/xvfb-manager.log"
TESTCLIENT_XVFB_LOG="$RUN_ROOT/xvfb-testclient.log"
TESTCLIENT_HOME="$RUN_ROOT/home-testclient"
TESTCLIENT_XDG="$RUN_ROOT/xdg-testclient"
JUNIT_XML="$REPORTS_DIR/junit.xml"
ALLURE_XML="$REPORTS_DIR/allure.xml"

mkdir -p "$XUNIT_ADD_ROOT" "$REPORTS_DIR" "$WORKSPACE_DIR" "$TESTCLIENT_HOME" "$TESTCLIENT_XDG"
cp -a "$ADD_ROOT"/. "$XUNIT_ADD_ROOT"/
jq \
  '
    .["Отладка"] = true
    | .["ДелатьЛогВыполненияСценариевВТекстовыйФайл"] = true
    | .["smoke"]["ОткрываемФормыНаКлиентеТестирования"] = false
  ' "$CONFIG_PATH" > "$XUNIT_CONFIG_RUNTIME"

if [ -n "$HARNESS_SOURCE_DIR" ]; then
  HARNESS_OUTPUT_EPF="$RUN_ROOT/project-owned-xunit-harness.epf"
  HARNESS_BUILD_LOG="$RUN_ROOT/project-owned-xunit-harness.out.log"
  "$PROJECT_ROOT/scripts/test/build-xunit-epf.sh" \
    --profile "$RUNTIME_PROFILE_PATH" \
    --source-root "$HARNESS_SOURCE_DIR" \
    --output-epf "$HARNESS_OUTPUT_EPF" \
    --log-out "$HARNESS_BUILD_LOG" >/dev/null
  XDD_RUN_TARGET="$HARNESS_OUTPUT_EPF"
  XDD_RUN_TARGET_REL=""
else
  XDD_RUN_TARGET="$XUNIT_ADD_ROOT/$XDD_RUN_TARGET_REL"
  [ -f "$XDD_RUN_TARGET" ] || fail "xdd target not found in copied ADD root: $XDD_RUN_TARGET"
fi

TESTCLIENT_PORT="$(pick_unused_tcp_port 47000 47999)"
MANAGER_DISPLAY="$(pick_unused_display 140 189)"
TESTCLIENT_DISPLAY="$(pick_unused_display 190 239)"
[ "$MANAGER_DISPLAY" != "$TESTCLIENT_DISPLAY" ] || fail "manager and testclient displays must differ"

declare -a XVFB_SERVER_ARGS=()
declare -a XVFB_EXTRA_ARGS=("-listen" "tcp" "-nolisten" "unix" "-ac")
declare -a LD_PRELOAD_LIBRARIES=()
declare -a BASE_CMD=()
declare -a TESTCLIENT_CMD=()
declare -a MANAGER_CMD=()
declare -a MANAGER_ENV=()
declare -a TESTCLIENT_ENV=()

load_direct_platform_xvfb_server_args XVFB_SERVER_ARGS
if [ "$(array_length XVFB_SERVER_ARGS)" -eq 0 ]; then
  XVFB_SERVER_ARGS=("-screen" "0" "1440x900x24" "-noreset")
fi

BASE_CMD=("$CLIENT_BINARY" "ENTERPRISE")
append_connection_args BASE_CMD
append_auth_args BASE_CMD
BASE_CMD+=("/Lru" "/VLru" "/DisableStartupMessages" "/DisableStartupDialogs")

if direct_platform_ld_preload_enabled; then
  load_direct_platform_ld_preload_libraries LD_PRELOAD_LIBRARIES
  TESTCLIENT_ENV+=("LD_PRELOAD=$(join_named_array_with_colons LD_PRELOAD_LIBRARIES)")
  MANAGER_ENV+=("LD_PRELOAD=$(join_named_array_with_colons LD_PRELOAD_LIBRARIES)")
fi

MANAGER_PAYLOAD="ОтключитьЛогикуНачалаРаботыСистемы; xddRun ЗагрузчикФайла $XDD_RUN_TARGET; xddTestClient ::$TESTCLIENT_PORT; xddTestClientAdditional /iTaxi; xddReport ГенераторОтчетаJUnitXML $JUNIT_XML;xddReport ГенераторОтчетаAllureXML $ALLURE_XML; xddConfig $XUNIT_CONFIG_RUNTIME; xddExitCodePath ГенерацияКодаВозврата $STATUS_FILE; workspaceRoot $WORKSPACE_DIR; xddShutdown"

TESTCLIENT_CMD=(
  "${BASE_CMD[@]}"
  "/CОтключитьЛогикуНачалаРаботыСистемы"
  "/TestClient"
  "-TPort$TESTCLIENT_PORT"
  "/iTaxi"
  "/out$TESTCLIENT_OUT"
)

MANAGER_CMD=(
  "${BASE_CMD[@]}"
  "/C$MANAGER_PAYLOAD"
  "/out$MANAGER_OUT"
  "/TESTMANAGER"
  "/Execute$XUNIT_ADD_ROOT/xddTestRunner.epf"
)

MANAGER_ENV+=(
  "DISPLAY=127.0.0.1:$MANAGER_DISPLAY"
  "WEBKIT_DISABLE_COMPOSITING_MODE=1"
  "GDK_DEBUG=nogl"
  "vblank_mode=0"
)

TESTCLIENT_ENV+=(
  "DISPLAY=127.0.0.1:$TESTCLIENT_DISPLAY"
  "HOME=$TESTCLIENT_HOME"
  "XDG_CONFIG_HOME=$TESTCLIENT_XDG"
  "WEBKIT_DISABLE_COMPOSITING_MODE=1"
  "GDK_DEBUG=nogl"
  "vblank_mode=0"
)

write_command_file "$RUN_ROOT/testclient-command.sh" "${TESTCLIENT_ENV[@]}" -- "${TESTCLIENT_CMD[@]}"
write_command_file "$RUN_ROOT/manager-command.sh" "${MANAGER_ENV[@]}" -- "${MANAGER_CMD[@]}"

Xvfb ":$TESTCLIENT_DISPLAY" "${XVFB_SERVER_ARGS[@]}" "${XVFB_EXTRA_ARGS[@]}" >"$TESTCLIENT_XVFB_LOG" 2>&1 &
TESTCLIENT_XVFB_PID="$!"
CLEANUP_PIDS+=("$TESTCLIENT_XVFB_PID")
wait_for_display "testclient" "$TESTCLIENT_DISPLAY" "$TESTCLIENT_XVFB_PID"

Xvfb ":$MANAGER_DISPLAY" "${XVFB_SERVER_ARGS[@]}" "${XVFB_EXTRA_ARGS[@]}" >"$MANAGER_XVFB_LOG" 2>&1 &
MANAGER_XVFB_PID="$!"
CLEANUP_PIDS+=("$MANAGER_XVFB_PID")
wait_for_display "manager" "$MANAGER_DISPLAY" "$MANAGER_XVFB_PID"

( exec bash "$RUN_ROOT/testclient-command.sh" ) >"$TESTCLIENT_STDOUT" 2>&1 &
TESTCLIENT_PID="$!"
CLEANUP_PIDS+=("$TESTCLIENT_PID")
wait_for_listen_port "testclient" "$TESTCLIENT_PORT" "$TESTCLIENT_PID"

( exec bash "$RUN_ROOT/manager-command.sh" ) >"$MANAGER_STDOUT" 2>&1 &
MANAGER_PID="$!"
CLEANUP_PIDS+=("$MANAGER_PID")

DEADLINE="$((SECONDS + TIMEOUT_SECONDS))"
while true; do
  if runtime_artifacts_ready; then
    break
  fi

  if ! kill -0 "$MANAGER_PID" 2>/dev/null && ! kill -0 "$TESTCLIENT_PID" 2>/dev/null; then
    break
  fi

  if [ "$SECONDS" -ge "$DEADLINE" ]; then
    TIMED_OUT=true
    break
  fi

  sleep 2
done

stop_pid_if_running "$MANAGER_PID"
stop_pid_if_running "$TESTCLIENT_PID"

set +e
wait "$MANAGER_PID"
MANAGER_EXIT_CODE=$?
wait "$TESTCLIENT_PID"
TESTCLIENT_EXIT_CODE=$?
set -e

normalize_allure_report
build_exit_code
write_summary

printf 'xunit-run-root=%s\n' "$RUN_ROOT"
printf 'xunit-classification=%s\n' "$CLASSIFICATION"
printf 'xunit-exit-code=%s\n' "$FINAL_EXIT_CODE"

exit "$FINAL_EXIT_CODE"
