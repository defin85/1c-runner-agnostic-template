#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$PROJECT_ROOT/scripts/lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$PROJECT_ROOT/scripts/lib/runtime-profile.sh"
# shellcheck source=../lib/capability.sh
source "$PROJECT_ROOT/scripts/lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$PROJECT_ROOT/scripts/lib/onec.sh"
# shellcheck source=../lib/onec-port-lease.sh
source "$PROJECT_ROOT/scripts/lib/onec-port-lease.sh"
# shellcheck source=../lib/vanessa-bdd.sh
source "$PROJECT_ROOT/scripts/lib/vanessa-bdd.sh"

CONTOUR_ID="bdd-warm-service"
COMMAND="${1:-}"
PROFILE_INPUT=""
TARGET_INPUT=""
RUN_ROOT_INPUT=""
TIMEOUT_SECONDS=180

PROFILE_PATH=""
REQUESTED_PROFILE_PATH=""
REQUESTED_TARGET_INPUT=""
RUN_ROOT=""
SESSION_ROOT=""
SESSION_ENV_PATH=""
SERVICE_STATE_PATH=""
MANAGER_STDOUT_LOG=""
MANAGER_STDERR_LOG=""
MANAGER_OUT_LOG=""
MANAGER_COMMAND_TXT=""
MANAGER_PID=""
TEST_CLIENT_STDOUT_LOG=""
TEST_CLIENT_STDERR_LOG=""
TEST_CLIENT_OUT_LOG=""
TEST_CLIENT_COMMAND_TXT=""
TEST_CLIENT_PID=""
TEST_CLIENT_PORT=""
TEST_CLIENT_PORT_LEASE_ID=""
SERVICE_CONFIG_PATH=""
READY_FILE=""
REQUEST_FILE=""
RESPONSE_FILE=""
ERROR_FILE=""
BUILD_STATUS_PATH=""
VANESSA_ONLINE_PATH=""
RUN_COMPLETE_PATH=""
STARTED_AT=""
CURRENT_LINK=""
HAS_ACTIVE_SESSION=0
MISSING_INPUTS=()

usage() {
  cat <<'EOF'
Usage:
  ./scripts/test/run-bdd-warm-service.sh up --profile <file> [--target <id>] --run-root <dir>
  ./scripts/test/run-bdd-warm-service.sh status --profile <file> [--target <id>] --run-root <dir>
  ./scripts/test/run-bdd-warm-service.sh down --profile <file> [--target <id>] --run-root <dir>
EOF
}

state_root() {
  local slug=""

  slug="$(basename "$PROJECT_ROOT")"
  if [ -n "${XDG_STATE_HOME:-}" ]; then
    printf '%s/%s/bdd-warm-service\n' "$(canonical_path "$XDG_STATE_HOME")" "$slug"
    return 0
  fi

  printf '%s/.local/state/%s/bdd-warm-service\n' "$(canonical_path "$HOME")" "$slug"
}

sessions_dir() {
  printf '%s/sessions\n' "$(state_root)"
}

current_link() {
  printf '%s/current-%s\n' "$(state_root)" "$TARGET_INPUT"
}

process_alive() {
  local pid="${1:-}"

  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

read_service_token() {
  local file="$1"
  local value=""

  [ -f "$file" ] || return 0
  value="$(head -n 1 "$file" | tr -d '\r')"
  value="${value#$'\xef\xbb\xbf'}"
  printf '%s' "$value"
}

tcp_port_listening() {
  local port="$1"

  command -v ss >/dev/null 2>&1 || return 1
  ss -ltn "sport = :$port" 2>/dev/null | awk 'NR > 1 { found = 1 } END { exit(found ? 0 : 1) }'
}

parse_args() {
  [ -n "$COMMAND" ] || {
    usage
    exit 2
  }
  shift || true

  case "$COMMAND" in
    up|status|down)
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unsupported bdd-warm-service command: $COMMAND"
      ;;
  esac

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || die "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --target)
        [ "$#" -ge 2 ] || die "--target requires a value"
        TARGET_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || die "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --timeout|--timeout-seconds)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        TIMEOUT_SECONDS="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
}

prepare_run_root() {
  if [ -n "$RUN_ROOT_INPUT" ]; then
    RUN_ROOT="$(canonical_path "$RUN_ROOT_INPUT")"
    ensure_dir "$RUN_ROOT"
    return 0
  fi

  RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/bdd-warm-service.XXXXXX")"
}

load_profile() {
  PROFILE_PATH="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$PROFILE_PATH" ] || die "runtime profile is required; pass --profile <file> or create env/local.json"
  PROFILE_PATH="$(canonical_path "$PROFILE_PATH")"
  load_runtime_profile "$PROFILE_PATH"
  require_runtime_profile_loaded

  if [ -z "$TARGET_INPUT" ]; then
    TARGET_INPUT="$(profile_string '.target.id // empty')"
  fi
  [ -n "$TARGET_INPUT" ] || die "bdd-warm-service requires --target <id> or target.id in profile"

  REQUESTED_PROFILE_PATH="$PROFILE_PATH"
  REQUESTED_TARGET_INPUT="$TARGET_INPUT"
}

validate_inputs() {
  local single_path=""
  local warmup_feature_path=""

  MISSING_INPUTS=()
  vanessa_bdd_validate_target_binding "$PROJECT_ROOT" MISSING_INPUTS

  single_path="$(profile_string '.capabilities.bddWarmService.vanessaSinglePath // empty')"
  [ -n "$single_path" ] && [ -f "$single_path" ] || MISSING_INPUTS+=("capabilities.bddWarmService.vanessaSinglePath")

  warmup_feature_path="$(profile_string '.capabilities.bddWarmService.warmupFeaturePath // empty')"
  [ -n "$warmup_feature_path" ] && [ -f "$warmup_feature_path" ] || MISSING_INPUTS+=("capabilities.bddWarmService.warmupFeaturePath")
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

  die "platform client binary not found next to platform.binaryPath: $candidate"
}

write_redacted_command_file() {
  local command_path="$1"
  local arg=""
  local redact_next=0

  : >"$command_path"
  shift
  for arg in "$@"; do
    if [ "$redact_next" = "1" ]; then
      printf '%q ' "__REDACTED_SECRET__" >>"$command_path"
      redact_next=0
      continue
    fi
    case "$arg" in
      /P)
        printf '%q ' "$arg" >>"$command_path"
        redact_next=1
        ;;
      *)
        printf '%q ' "$arg" >>"$command_path"
        ;;
    esac
  done
  printf '\n' >>"$command_path"
}

write_session_env() {
  cat >"$SESSION_ENV_PATH" <<EOF
SESSION_ROOT=$(printf '%q' "$SESSION_ROOT")
SERVICE_STATE_PATH=$(printf '%q' "$SERVICE_STATE_PATH")
MANAGER_STDOUT_LOG=$(printf '%q' "$MANAGER_STDOUT_LOG")
MANAGER_STDERR_LOG=$(printf '%q' "$MANAGER_STDERR_LOG")
MANAGER_OUT_LOG=$(printf '%q' "$MANAGER_OUT_LOG")
MANAGER_COMMAND_TXT=$(printf '%q' "$MANAGER_COMMAND_TXT")
MANAGER_PID=$(printf '%q' "${MANAGER_PID:-}")
TEST_CLIENT_STDOUT_LOG=$(printf '%q' "$TEST_CLIENT_STDOUT_LOG")
TEST_CLIENT_STDERR_LOG=$(printf '%q' "$TEST_CLIENT_STDERR_LOG")
TEST_CLIENT_OUT_LOG=$(printf '%q' "$TEST_CLIENT_OUT_LOG")
TEST_CLIENT_COMMAND_TXT=$(printf '%q' "$TEST_CLIENT_COMMAND_TXT")
TEST_CLIENT_PID=$(printf '%q' "${TEST_CLIENT_PID:-}")
TEST_CLIENT_PORT=$(printf '%q' "${TEST_CLIENT_PORT:-}")
TEST_CLIENT_PORT_LEASE_ID=$(printf '%q' "${TEST_CLIENT_PORT_LEASE_ID:-}")
SERVICE_CONFIG_PATH=$(printf '%q' "${SERVICE_CONFIG_PATH:-}")
READY_FILE=$(printf '%q' "${READY_FILE:-}")
REQUEST_FILE=$(printf '%q' "${REQUEST_FILE:-}")
RESPONSE_FILE=$(printf '%q' "${RESPONSE_FILE:-}")
ERROR_FILE=$(printf '%q' "${ERROR_FILE:-}")
BUILD_STATUS_PATH=$(printf '%q' "${BUILD_STATUS_PATH:-}")
VANESSA_ONLINE_PATH=$(printf '%q' "${VANESSA_ONLINE_PATH:-}")
RUN_COMPLETE_PATH=$(printf '%q' "${RUN_COMPLETE_PATH:-}")
PROFILE_PATH=$(printf '%q' "$PROFILE_PATH")
TARGET_INPUT=$(printf '%q' "$TARGET_INPUT")
STARTED_AT=$(printf '%q' "$STARTED_AT")
EOF
}

load_current_session() {
  CURRENT_LINK="$(current_link)"
  HAS_ACTIVE_SESSION=0

  if [ ! -L "$CURRENT_LINK" ]; then
    return 0
  fi

  SESSION_ROOT="$(canonical_path "$CURRENT_LINK")"
  SESSION_ENV_PATH="$SESSION_ROOT/session.env"
  [ -f "$SESSION_ENV_PATH" ] || return 0
  # shellcheck disable=SC1090
  source "$SESSION_ENV_PATH"
  HAS_ACTIVE_SESSION=1
}

service_state() {
  if [ "$HAS_ACTIVE_SESSION" != "1" ]; then
    printf 'stopped\n'
    return 0
  fi

  if process_alive "$MANAGER_PID" \
    && process_alive "$TEST_CLIENT_PID" \
    && [ "$(read_service_token "${READY_FILE:-}")" = "READY" ] \
    && tcp_port_listening "${TEST_CLIENT_PORT:-0}"; then
    printf 'ready\n'
    return 0
  fi

  printf 'failed\n'
}

write_service_state() {
  local state="$1"
  local note="${2:-}"

  jq -n \
    --arg state "$state" \
    --arg note "$note" \
    --arg updated_at "$(timestamp_utc)" \
    --arg session_root "$SESSION_ROOT" \
    --arg profile_path "$PROFILE_PATH" \
    --arg target "$TARGET_INPUT" \
    --arg manager_pid "${MANAGER_PID:-}" \
    --arg manager_stdout "$MANAGER_STDOUT_LOG" \
    --arg manager_stderr "$MANAGER_STDERR_LOG" \
    --arg manager_out "$MANAGER_OUT_LOG" \
    --arg manager_command "$MANAGER_COMMAND_TXT" \
    --arg test_client_pid "${TEST_CLIENT_PID:-}" \
    --arg test_client_port "${TEST_CLIENT_PORT:-}" \
    --arg service_config_path "${SERVICE_CONFIG_PATH:-}" \
    --arg ready_file "${READY_FILE:-}" \
    --arg request_file "${REQUEST_FILE:-}" \
    --arg response_file "${RESPONSE_FILE:-}" \
    --arg error_file "${ERROR_FILE:-}" \
    --arg build_status_path "${BUILD_STATUS_PATH:-}" \
    --arg vanessa_online_path "${VANESSA_ONLINE_PATH:-}" \
    --arg run_complete_path "${RUN_COMPLETE_PATH:-}" \
    --arg test_client_stdout "$TEST_CLIENT_STDOUT_LOG" \
    --arg test_client_stderr "$TEST_CLIENT_STDERR_LOG" \
    --arg test_client_out "$TEST_CLIENT_OUT_LOG" \
    --arg test_client_command "$TEST_CLIENT_COMMAND_TXT" \
    '{
      contour_id: "bdd-warm-service",
      state: $state,
      note: (if $note == "" then null else $note end),
      updated_at: $updated_at,
      session_root: $session_root,
      profile_path: $profile_path,
      runtime_profile: {target: $target},
      service_files: {
        config: (if $service_config_path == "" then null else $service_config_path end),
        ready: (if $ready_file == "" then null else $ready_file end),
        request: (if $request_file == "" then null else $request_file end),
        response: (if $response_file == "" then null else $response_file end),
        error: (if $error_file == "" then null else $error_file end),
        build_status: (if $build_status_path == "" then null else $build_status_path end),
        vanessa_online: (if $vanessa_online_path == "" then null else $vanessa_online_path end),
        run_complete: (if $run_complete_path == "" then null else $run_complete_path end)
      },
      roles: {
        manager: {
          pid: (if $manager_pid == "" then null else ($manager_pid | tonumber) end),
          artifacts: {stdout_log: $manager_stdout, stderr_log: $manager_stderr, out_log: $manager_out, command_txt: $manager_command}
        },
        test_client: {
          pid: (if $test_client_pid == "" then null else ($test_client_pid | tonumber) end),
          port: (if $test_client_port == "" then null else ($test_client_port | tonumber) end),
          artifacts: {stdout_log: $test_client_stdout, stderr_log: $test_client_stderr, out_log: $test_client_out, command_txt: $test_client_command}
        }
      }
    }' >"$SERVICE_STATE_PATH"
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local message="$3"
  local state=""
  local missing_json="[]"

  state="$(service_state)"
  missing_json="$(printf '%s\n' "${MISSING_INPUTS[@]}" | jq -R 'select(length > 0)' | jq -s '.')"
  jq -n \
    --arg status "$status" \
    --arg command "$COMMAND" \
    --arg message "$message" \
    --arg profile_path "$PROFILE_PATH" \
    --arg target "$TARGET_INPUT" \
    --arg run_root "$RUN_ROOT" \
    --arg state "$state" \
    --arg session_root "${SESSION_ROOT:-}" \
    --arg state_json "${SERVICE_STATE_PATH:-}" \
    --arg manager_stdout "${MANAGER_STDOUT_LOG:-}" \
    --arg manager_stderr "${MANAGER_STDERR_LOG:-}" \
    --arg manager_out "${MANAGER_OUT_LOG:-}" \
    --arg manager_command "${MANAGER_COMMAND_TXT:-}" \
    --arg test_client_stdout "${TEST_CLIENT_STDOUT_LOG:-}" \
    --arg test_client_stderr "${TEST_CLIENT_STDERR_LOG:-}" \
    --arg test_client_out "${TEST_CLIENT_OUT_LOG:-}" \
    --arg test_client_command "${TEST_CLIENT_COMMAND_TXT:-}" \
    --argjson exit_code "$exit_code" \
    --argjson missing_inputs "$missing_json" \
    '{
      status: $status,
      contour: {id: "bdd-warm-service", command: $command},
      message: (if $message == "" then null else $message end),
      exit_code: $exit_code,
      missing_inputs: $missing_inputs,
      profile_path: $profile_path,
      runtime_profile: {target: $target},
      run_root: $run_root,
      service: {
        state: $state,
        session_root: (if $session_root == "" then null else $session_root end),
        state_json: (if $state_json == "" then null else $state_json end)
      },
      artifacts: {
        manager_stdout_log: (if $manager_stdout == "" then null else $manager_stdout end),
        manager_stderr_log: (if $manager_stderr == "" then null else $manager_stderr end),
        manager_out_log: (if $manager_out == "" then null else $manager_out end),
        manager_command_txt: (if $manager_command == "" then null else $manager_command end),
        test_client_stdout_log: (if $test_client_stdout == "" then null else $test_client_stdout end),
        test_client_stderr_log: (if $test_client_stderr == "" then null else $test_client_stderr end),
        test_client_out_log: (if $test_client_out == "" then null else $test_client_out end),
        test_client_command_txt: (if $test_client_command == "" then null else $test_client_command end)
      }
    }' >"$RUN_ROOT/summary.json"
}

prepare_session_layout() {
  local session_id=""

  STARTED_AT="$(timestamp_utc)"
  session_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  SESSION_ROOT="$(sessions_dir)/$TARGET_INPUT/$session_id"
  SESSION_ENV_PATH="$SESSION_ROOT/session.env"
  SERVICE_STATE_PATH="$SESSION_ROOT/service-state.json"
  SERVICE_CONFIG_PATH="$SESSION_ROOT/bdd-warm-service.conf"
  READY_FILE="$SESSION_ROOT/ready.txt"
  REQUEST_FILE="$SESSION_ROOT/request.txt"
  RESPONSE_FILE="$SESSION_ROOT/response.txt"
  ERROR_FILE="$SESSION_ROOT/error.txt"
  BUILD_STATUS_PATH="$SESSION_ROOT/build-status.txt"
  VANESSA_ONLINE_PATH="$SESSION_ROOT/vanessa-online.log"
  RUN_COMPLETE_PATH="$SESSION_ROOT/run-complete.txt"
  MANAGER_STDOUT_LOG="$SESSION_ROOT/manager.stdout.log"
  MANAGER_STDERR_LOG="$SESSION_ROOT/manager.stderr.log"
  MANAGER_OUT_LOG="$SESSION_ROOT/manager.1c.out"
  MANAGER_COMMAND_TXT="$SESSION_ROOT/manager.command.txt"
  TEST_CLIENT_STDOUT_LOG="$SESSION_ROOT/test-client.stdout.log"
  TEST_CLIENT_STDERR_LOG="$SESSION_ROOT/test-client.stderr.log"
  TEST_CLIENT_OUT_LOG="$SESSION_ROOT/test-client.1c.out"
  TEST_CLIENT_COMMAND_TXT="$SESSION_ROOT/test-client.command.txt"

  ensure_dir "$SESSION_ROOT"
  ensure_dir "$(state_root)"
  : >"$MANAGER_STDOUT_LOG"
  : >"$MANAGER_STDERR_LOG"
  : >"$MANAGER_OUT_LOG"
  : >"$TEST_CLIENT_STDOUT_LOG"
  : >"$TEST_CLIENT_STDERR_LOG"
  : >"$TEST_CLIENT_OUT_LOG"
}

build_client_command() {
  local array_name="$1"
  local -n out_ref="$array_name"

  out_ref=("$(platform_client_binary_path)" "ENTERPRISE")
  append_connection_args out_ref
  append_auth_args out_ref
  out_ref+=("/Lru" "/VLru" "/DisableStartupMessages" "/DisableStartupDialogs")
}

build_connection_string_for_vanessa() {
  local mode=""
  local server=""
  local ref=""
  local file_path=""

  mode="$(infobase_mode)"
  case "$mode" in
    file)
      file_path="$(require_profile_string '.infobase.filePath // empty' 'infobase.filePath')"
      printf 'File="%s";\n' "$file_path"
      ;;
    client-server)
      server="$(require_profile_string '.infobase.server // empty' 'infobase.server')"
      ref="$(require_profile_string '.infobase.ref // empty' 'infobase.ref')"
      printf 'Srvr="%s";Ref="%s";\n' "$server" "$ref"
      ;;
    *)
      die "unsupported infobase.mode=$mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

build_connection_string_for_vanessa_launch_json() {
  build_connection_string_for_vanessa | sed 's/;/\\;/g'
}

build_test_client_extra_args_for_vanessa() {
  local configured_extra_args=""

  configured_extra_args="$(profile_string '.capabilities.bddWarmService.testClientExtraArgs // "/iTaxi"')"
  printf '%s\n' "$configured_extra_args"
}

build_vanessa_test_clients_launch_json() {
  local connection_string=""
  local extra_args=""

  connection_string="$(build_connection_string_for_vanessa_launch_json)"
  extra_args="$(build_test_client_extra_args_for_vanessa)"
  jq -cn \
    --arg connection_string "$connection_string" \
    --arg port "$TEST_CLIENT_PORT" \
    --arg extra_args "$extra_args" \
    '[{
      "Имя": "Этот клиент",
      "Синоним": "",
      "ПутьКИнфобазе": $connection_string,
      "ПортЗапускаТестКлиента": ($port | tonumber),
      "ДопПараметры": $extra_args,
      "ТипКлиента": "Тонкий",
      "ИмяКомпьютера": "localhost"
    }]'
}

acquire_test_client_port() {
  local range_value="${ONEC_BDD_TESTCLIENT_PORT_RANGE:-48200-48299}"
  local lease_json=""

  lease_json="$(onec_port_lease_acquire bdd-warm-service testclient "$range_value" 1 "$$")"
  TEST_CLIENT_PORT_LEASE_ID="$(onec_port_lease_id_from_json <<<"$lease_json")"
  TEST_CLIENT_PORT="$(onec_port_lease_port_from_json <<<"$lease_json")"
}

write_service_config() {
  local single_path=""
  local warmup_feature_path=""
  local feature_runtime_path=""
  local library_paths=""
  local test_client_extra_args=""

  single_path="$(require_profile_string '.capabilities.bddWarmService.vanessaSinglePath // empty' 'capabilities.bddWarmService.vanessaSinglePath')"
  single_path="$(resolve_project_tree_path "$single_path")"
  [ -f "$single_path" ] || die "Vanessa Automation Single file is not found: $single_path"

  warmup_feature_path="$(require_profile_string '.capabilities.bddWarmService.warmupFeaturePath // empty' 'capabilities.bddWarmService.warmupFeaturePath')"
  warmup_feature_path="$(resolve_project_tree_path "$warmup_feature_path")"
  [ -f "$warmup_feature_path" ] || die "BDD warmup feature file is not found: $warmup_feature_path"

  feature_runtime_path="$SESSION_ROOT/runtime.feature"
  cp "$warmup_feature_path" "$feature_runtime_path"

  library_paths="$(profile_jq_raw '.capabilities.bddWarmService.libraryPaths // [] | if type == "array" then join(":") else "" end')"
  test_client_extra_args="$(profile_string '.capabilities.bddWarmService.testClientExtraArgs // "/iTaxi"')"

  cat >"$SERVICE_CONFIG_PATH" <<EOF
SinglePath=$single_path
WarmupFeaturePath=$warmup_feature_path
FeatureRuntimePath=$feature_runtime_path
BuildStatusPath=$BUILD_STATUS_PATH
VanessaOnlinePath=$VANESSA_ONLINE_PATH
RunCompletePath=$RUN_COMPLETE_PATH
ScreensDir=$SESSION_ROOT/screens
WorkspaceRoot=$PROJECT_ROOT
LibraryPaths=$library_paths
ReadyFile=$READY_FILE
RequestFile=$REQUEST_FILE
ResponseFile=$RESPONSE_FILE
ErrorFile=$ERROR_FILE
TestClientConnectionString=$(build_connection_string_for_vanessa)
TestClientPort=$TEST_CLIENT_PORT
TestClientExtraArgs=$test_client_extra_args
EOF
  ensure_dir "$SESSION_ROOT/screens"
  : >"$READY_FILE"
  : >"$REQUEST_FILE"
  : >"$RESPONSE_FILE"
  : >"$ERROR_FILE"
  : >"$BUILD_STATUS_PATH"
  : >"$VANESSA_ONLINE_PATH"
  : >"$RUN_COMPLETE_PATH"
}

start_role() {
  local role="$1"
  local stdout_log="$2"
  local stderr_log="$3"
  local out_log="$4"
  local command_txt="$5"
  local pid_name="$6"
  local adapter=""
  local launch_parameter_name=""
  local -a command=()
  local -a adapter_env=()
  local -a runtime_env=()

  adapter="${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}"
  [ "$adapter" = "direct-platform" ] || die "BDD warm service requires runnerAdapter=direct-platform"
  direct_platform_xpra_enabled || die "BDD warm service requires platform.xpra.enabled=true"

  build_client_command command
  case "$role" in
    manager)
      launch_parameter_name="$(profile_string '.capabilities.bddWarmService.launchParameterName // "VanessaBddWarmServiceConfig"')"
      command+=("/C" "$launch_parameter_name=$SERVICE_CONFIG_PATH;ДанныеКлиентовТестирования=$(build_vanessa_test_clients_launch_json)" "/TESTMANAGER" "/out$out_log")
      ;;
    test-client)
      command+=("/CОтключитьЛогикуНачалаРаботыСистемы" "/TestClient" "-TPort$TEST_CLIENT_PORT" "$(build_test_client_extra_args_for_vanessa)" "/out$out_log")
      ;;
    *)
      die "unsupported bdd-warm-service role: $role"
      ;;
  esac
  write_redacted_command_file "$command_txt" "${command[@]}"
  prepare_adapter_wrapper_env "$adapter" adapter_env
  runtime_env=(
    "ONEC_TARGET_ID=$TARGET_INPUT"
    "ONEC_CAPABILITY_ID=bdd-warm-service"
    "ONEC_CAPABILITY_LABEL=BDD warm service"
    "ONEC_CAPABILITY_RUN_ROOT=$SESSION_ROOT/$role"
    "ONEC_DIRECT_PLATFORM_XPRA_SESSION_NAME=BDD $role $TARGET_INPUT"
    "HOME=$SESSION_ROOT/$role/home"
    "XDG_CONFIG_HOME=$SESSION_ROOT/$role/xdg-config"
    "XDG_CACHE_HOME=$SESSION_ROOT/$role/xdg-cache"
    "NO_AT_BRIDGE=${NO_AT_BRIDGE:-1}"
  )
  ensure_dir "$SESSION_ROOT/$role/home"
  ensure_dir "$SESSION_ROOT/$role/xdg-config"
  ensure_dir "$SESSION_ROOT/$role/xdg-cache"

  if command -v setsid >/dev/null 2>&1; then
    setsid env "${runtime_env[@]}" "${adapter_env[@]}" "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${command[@]}" \
      >"$stdout_log" \
      2>"$stderr_log" \
      < /dev/null &
  else
    nohup env "${runtime_env[@]}" "${adapter_env[@]}" "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${command[@]}" \
      >"$stdout_log" \
      2>"$stderr_log" \
      < /dev/null &
  fi
  printf -v "$pid_name" '%s' "$!"
}

wait_for_log_ready() {
  local pid="$1"
  local stderr_log="$2"
  local deadline="$((SECONDS + TIMEOUT_SECONDS))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! process_alive "$pid"; then
      return 1
    fi
    if grep -F "direct-platform xpra display=" "$stderr_log" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 2
}

wait_for_test_client_ready() {
  local pid="$1"
  local _stderr_log="$2"
  local port="$3"
  local deadline="$((SECONDS + TIMEOUT_SECONDS))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! process_alive "$pid"; then
      return 1
    fi
    if tcp_port_listening "$port"; then
      return 0
    fi
    sleep 1
  done

  return 2
}

wait_for_service_startup_sanity() {
  local deadline="$((SECONDS + ${ONEC_BDD_WARM_SERVICE_SANITY_SECONDS:-5}))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ -s "$ERROR_FILE" ]; then
      return 1
    fi
    if [ "$(read_service_token "$READY_FILE")" = "READY" ]; then
      return 0
    fi
    if ! process_alive "$MANAGER_PID" || ! process_alive "$TEST_CLIENT_PID"; then
      return 2
    fi
    sleep 1
  done

  return 2
}

stop_role() {
  local pid="$1"
  local stderr_log="$2"
  local role="${3:-}"
  local display_value=""
  local baseline_file=""
  local stale_pid=""
  local comm=""
  local -a stale_pids=()

  if [ -f "$stderr_log" ]; then
    display_value="$(sed -n 's/.*direct-platform xpra display=\([^ ]*\).*/\1/p' "$stderr_log" | tail -n 1)"
  fi
  if [ -n "$display_value" ]; then
    xpra stop "$display_value" >/dev/null 2>&1 || true
  fi

  if process_alive "$pid"; then
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    sleep 2
  fi
  if process_alive "$pid"; then
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi

  if [ -n "$role" ]; then
    baseline_file="$SESSION_ROOT/$role/xpra/process-cleanup-baseline.txt"
  fi
  if [ -f "$baseline_file" ]; then
    while IFS= read -r stale_pid; do
      [ -n "$stale_pid" ] || continue
      grep -Fxq "$stale_pid" "$baseline_file" && continue
      comm="$(cat "/proc/$stale_pid/comm" 2>/dev/null || true)"
      case "$comm" in
        dbus-daemon|gvfsd)
          stale_pids+=("$stale_pid")
          ;;
      esac
    done < <(
      ps -u "$USER" -o pid=,comm=,cmd= \
        | awk '($2 == "dbus-daemon" && /--session/ && /--print-address/) || ($2 == "gvfsd" && $0 ~ /\/usr\/libexec\/gvfsd$/) {print $1}'
    )
  fi
  [ "${#stale_pids[@]}" -eq 0 ] || kill -TERM "${stale_pids[@]}" 2>/dev/null || true
  sleep 0.5
  [ "${#stale_pids[@]}" -eq 0 ] || kill -KILL "${stale_pids[@]}" 2>/dev/null || true
}

stop_service() {
  stop_role "${TEST_CLIENT_PID:-}" "${TEST_CLIENT_STDERR_LOG:-/dev/null}" "test-client"
  stop_role "${MANAGER_PID:-}" "${MANAGER_STDERR_LOG:-/dev/null}" "manager"
  onec_port_lease_release_by_id "${TEST_CLIENT_PORT_LEASE_ID:-}" || true
  TEST_CLIENT_PORT_LEASE_ID=""
}

command_up() {
  load_current_session
  if [ "$(service_state)" = "ready" ]; then
    if [ "$PROFILE_PATH" != "$REQUESTED_PROFILE_PATH" ] || [ "$TARGET_INPUT" != "$REQUESTED_TARGET_INPUT" ]; then
      die "another BDD warm service is already ready for target=$TARGET_INPUT; stop it before starting target=$REQUESTED_TARGET_INPUT"
    fi
    write_summary "success" 0 "BDD warm service is already ready"
    return 0
  fi

  validate_inputs
  if [ "${#MISSING_INPUTS[@]}" -gt 0 ]; then
    write_summary "failed" 2 "Vanessa BDD warm-service is not configured"
    return 2
  fi

  PROFILE_PATH="$REQUESTED_PROFILE_PATH"
  TARGET_INPUT="$REQUESTED_TARGET_INPUT"

  prepare_session_layout
  acquire_test_client_port
  write_service_config
  start_role "manager" "$MANAGER_STDOUT_LOG" "$MANAGER_STDERR_LOG" "$MANAGER_OUT_LOG" "$MANAGER_COMMAND_TXT" MANAGER_PID
  if ! wait_for_log_ready "$MANAGER_PID" "$MANAGER_STDERR_LOG"; then
    stop_service
    write_session_env
    ln -sfn "$SESSION_ROOT" "$(current_link)"
    HAS_ACTIVE_SESSION=1
    write_service_state "failed" "BDD manager did not reach xpra readiness"
    write_summary "failed" 65 "BDD warm service did not become ready"
    return 65
  fi

  start_role "test-client" "$TEST_CLIENT_STDOUT_LOG" "$TEST_CLIENT_STDERR_LOG" "$TEST_CLIENT_OUT_LOG" "$TEST_CLIENT_COMMAND_TXT" TEST_CLIENT_PID
  write_session_env
  ln -sfn "$SESSION_ROOT" "$(current_link)"
  HAS_ACTIVE_SESSION=1

  if wait_for_test_client_ready "$TEST_CLIENT_PID" "$TEST_CLIENT_STDERR_LOG" "$TEST_CLIENT_PORT" && wait_for_service_startup_sanity; then
    write_service_state "ready" "BDD manager and test client started"
    write_summary "success" 0 "BDD warm service is ready"
    return 0
  fi

  stop_service
  write_service_state "failed" "BDD manager or test client did not reach startup readiness"
  write_summary "failed" 65 "BDD warm service did not become ready"
  return 65
}

command_status() {
  load_current_session
  write_summary "success" 0 "BDD warm service status written"
}

command_down() {
  load_current_session
  if [ "$HAS_ACTIVE_SESSION" = "1" ]; then
    stop_service
    write_service_state "stopped" "stopped by command"
    rm -f "$(current_link)"
    HAS_ACTIVE_SESSION=0
  fi
  write_summary "success" 0 "BDD warm service stopped"
}

parse_args "$@"
require_command jq
prepare_run_root
load_profile

case "$COMMAND" in
  up)
    command_up
    ;;
  status)
    command_status
    ;;
  down)
    command_down
    ;;
esac
