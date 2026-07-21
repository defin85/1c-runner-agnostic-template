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
# shellcheck source=../lib/yaxunit.sh
source "$PROJECT_ROOT/scripts/lib/yaxunit.sh"

DEFAULT_TIMEOUT_SECONDS=300
FAILURE_EXIT_CODE=65
RUN_FAILURE_EXIT_CODE=66
CONTROLLER_SCRIPT="${ONEC_YAXUNIT_WARM_RPC_CONTROLLER:-$PROJECT_ROOT/tooling/yaxunit/warm_rpc_controller.py}"

COMMAND="${1:-}"
[ -n "$COMMAND" ] || {
  printf 'usage: %s <up|run|status|down> [options]\n' "$0" >&2
  exit 1
}
shift || true

PROFILE_INPUT=""
RUN_ROOT_INPUT=""
TARGET_INPUT=""
TIMEOUT_SECONDS="$DEFAULT_TIMEOUT_SECONDS"
RPC_HOST="${ONEC_YAXUNIT_WARM_RPC_HOST:-127.0.0.1}"
RPC_PORT_INPUT="${ONEC_YAXUNIT_WARM_RPC_PORT:-}"
MODULE_FILE_INPUT=""
MODULE_NAME=""
METHODS=()
RUN_CLIENT=0
RUN_ORDINARY_CLIENT=0
RUN_SERVER=0

PROFILE_PATH=""
REQUESTED_PROFILE_PATH=""
SESSION_TARGET_ID=""
RUN_ROOT=""
STARTED_AT=""
SESSION_ROOT=""
SESSION_ENV_PATH=""
SERVICE_STATE_PATH=""
CONTROL_DIR=""
COMMAND_DIR=""
READY_FILE=""
SHUTDOWN_FILE=""
EVENTS_JSONL=""
HISTORY_ROOT=""
RUNTIME_HOME=""
RUNTIME_XDG_CONFIG=""
RUNTIME_XDG_CACHE=""
WARM_CONFIG_PATH=""
ENTERPRISE_OUT=""
CLIENT_STDOUT_LOG=""
CLIENT_STDERR_LOG=""
CONTROLLER_STDOUT_LOG=""
CONTROLLER_STDERR_LOG=""
CLIENT_COMMAND_TXT=""
RPC_PORT=""
RPC_KEY=""
CONTROLLER_PID=""
CLIENT_PID=""
SYNC_EVIDENCE_PATH=""
SYNC_EVIDENCE_PREPARED_AT=""
SYNC_CONTRACT_HASH=""
SYNC_REQUIRED=0
SYNC_FAILURE_REASON=""
HAS_ACTIVE_SESSION=0
CURRENT_LINK=""
ADAPTER=""
CLIENT_BINARY=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/test/run-yaxunit-warm-service.sh up --profile <file> --target <id> --run-root <dir> [--timeout <seconds>] [--port <port>]
  ./scripts/test/run-yaxunit-warm-service.sh run --profile <file> --target <id> --run-root <dir> --module-file <path> --module-name <name> --method <name> [--client] [--server] [--ordinary-client] [--timeout <seconds>]
  ./scripts/test/run-yaxunit-warm-service.sh status --profile <file> --target <id> --run-root <dir>
  ./scripts/test/run-yaxunit-warm-service.sh down --profile <file> --target <id> --run-root <dir> [--timeout <seconds>]
EOF
}

append_unique() {
  local array_name="$1"
  local value="$2"
  local existing=""
  local -n array_ref="$array_name"

  for existing in "${array_ref[@]}"; do
    if [ "$existing" = "$value" ]; then
      return 0
    fi
  done
  array_ref+=("$value")
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || die "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || die "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --target)
        [ "$#" -ge 2 ] || die "--target requires a value"
        TARGET_INPUT="$2"
        shift 2
        ;;
      --timeout|--timeout-seconds)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        TIMEOUT_SECONDS="$2"
        shift 2
        ;;
      --host)
        [ "$#" -ge 2 ] || die "--host requires a value"
        RPC_HOST="$2"
        shift 2
        ;;
      --port|--rpc-port)
        [ "$#" -ge 2 ] || die "$1 requires a value"
        RPC_PORT_INPUT="$2"
        shift 2
        ;;
      --module-file)
        [ "$#" -ge 2 ] || die "--module-file requires a value"
        MODULE_FILE_INPUT="$2"
        shift 2
        ;;
      --module-name)
        [ "$#" -ge 2 ] || die "--module-name requires a value"
        MODULE_NAME="$2"
        shift 2
        ;;
      --method)
        [ "$#" -ge 2 ] || die "--method requires a value"
        METHODS+=("$2")
        shift 2
        ;;
      --client)
        RUN_CLIENT=1
        shift
        ;;
      --ordinary-client)
        RUN_ORDINARY_CLIENT=1
        shift
        ;;
      --server)
        RUN_SERVER=1
        shift
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

  RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/yaxunit-warm-rpc.XXXXXX")"
}

resolve_profile_path() {
  local root=""

  root="$(project_root)"
  PROFILE_PATH="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$root")"
  [ -n "$PROFILE_PATH" ] || die "runtime profile is required; pass --profile <file> or create env/local.json"
  PROFILE_PATH="$(canonical_path "$PROFILE_PATH")"
  REQUESTED_PROFILE_PATH="$PROFILE_PATH"
  load_runtime_profile "$PROFILE_PATH"
  require_runtime_profile_loaded
  target_require_requested "$PROJECT_ROOT" "$TARGET_INPUT"
  SESSION_TARGET_ID="$(target_profile_id)"
}

process_alive() {
  local pid="${1:-}"

  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

list_child_processes() {
  local parent_pid="$1"

  ps -o pid= --ppid "$parent_pid" 2>/dev/null | sed 's/^[[:space:]]*//'
}

signal_process_tree() {
  local signal_name="$1"
  local pid="$2"
  local child_pid=""

  while IFS= read -r child_pid; do
    [ -n "$child_pid" ] || continue
    signal_process_tree "$signal_name" "$child_pid"
  done < <(list_child_processes "$pid")

  kill "-$signal_name" "$pid" 2>/dev/null || true
}

wait_for_process_exit_with_grace() {
  local pid="$1"
  local grace_seconds="$2"
  local elapsed=0

  while process_alive "$pid"; do
    if [ "$elapsed" -ge "$grace_seconds" ]; then
      return 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 0
}

stop_started_processes() {
  if process_alive "${CLIENT_PID:-}"; then
    signal_process_tree TERM "$CLIENT_PID"
    wait_for_process_exit_with_grace "$CLIENT_PID" 5 || signal_process_tree KILL "$CLIENT_PID"
  fi
  if process_alive "${CONTROLLER_PID:-}"; then
    signal_process_tree TERM "$CONTROLLER_PID"
    wait_for_process_exit_with_grace "$CONTROLLER_PID" 5 || signal_process_tree KILL "$CONTROLLER_PID"
  fi
}

pick_unused_tcp_port() {
  local start_port="$1"
  local end_port="$2"

  python3 - "$start_port" "$end_port" <<'PY'
import socket
import sys

start, end = int(sys.argv[1]), int(sys.argv[2])
for port in range(start, end + 1):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        sys.exit(0)
sys.exit(1)
PY
}

generate_rpc_key() {
  python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
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

write_session_env() {
  local tmp_path="$SESSION_ENV_PATH.tmp.$$"

  cat >"$tmp_path" <<EOF
SESSION_ROOT=$(printf '%q' "$SESSION_ROOT")
PROFILE_PATH=$(printf '%q' "$PROFILE_PATH")
SERVICE_STATE_PATH=$(printf '%q' "$SERVICE_STATE_PATH")
CONTROL_DIR=$(printf '%q' "$CONTROL_DIR")
COMMAND_DIR=$(printf '%q' "$COMMAND_DIR")
READY_FILE=$(printf '%q' "$READY_FILE")
SHUTDOWN_FILE=$(printf '%q' "$SHUTDOWN_FILE")
EVENTS_JSONL=$(printf '%q' "$EVENTS_JSONL")
HISTORY_ROOT=$(printf '%q' "$HISTORY_ROOT")
RUNTIME_HOME=$(printf '%q' "$RUNTIME_HOME")
RUNTIME_XDG_CONFIG=$(printf '%q' "$RUNTIME_XDG_CONFIG")
RUNTIME_XDG_CACHE=$(printf '%q' "$RUNTIME_XDG_CACHE")
WARM_CONFIG_PATH=$(printf '%q' "$WARM_CONFIG_PATH")
ENTERPRISE_OUT=$(printf '%q' "$ENTERPRISE_OUT")
CLIENT_STDOUT_LOG=$(printf '%q' "$CLIENT_STDOUT_LOG")
CLIENT_STDERR_LOG=$(printf '%q' "$CLIENT_STDERR_LOG")
CONTROLLER_STDOUT_LOG=$(printf '%q' "$CONTROLLER_STDOUT_LOG")
CONTROLLER_STDERR_LOG=$(printf '%q' "$CONTROLLER_STDERR_LOG")
CLIENT_COMMAND_TXT=$(printf '%q' "$CLIENT_COMMAND_TXT")
RPC_HOST=$(printf '%q' "$RPC_HOST")
RPC_PORT=$(printf '%q' "$RPC_PORT")
RPC_KEY=$(printf '%q' "$RPC_KEY")
CONTROLLER_PID=$(printf '%q' "${CONTROLLER_PID:-}")
CLIENT_PID=$(printf '%q' "${CLIENT_PID:-}")
SYNC_EVIDENCE_PATH=$(printf '%q' "$SYNC_EVIDENCE_PATH")
SYNC_EVIDENCE_PREPARED_AT=$(printf '%q' "$SYNC_EVIDENCE_PREPARED_AT")
SYNC_CONTRACT_HASH=$(printf '%q' "$SYNC_CONTRACT_HASH")
SESSION_TARGET_ID=$(printf '%q' "$SESSION_TARGET_ID")
STARTED_AT=$(printf '%q' "$STARTED_AT")
EOF
  mv "$tmp_path" "$SESSION_ENV_PATH"
}

load_current_session() {
  CURRENT_LINK="$(yaxunit_warm_rpc_current_link)"
  HAS_ACTIVE_SESSION=0

  if [ ! -L "$CURRENT_LINK" ]; then
    return 0
  fi

  SESSION_ROOT="$(canonical_path "$CURRENT_LINK")"
  SESSION_ENV_PATH="$SESSION_ROOT/session.env"
  if [ ! -f "$SESSION_ENV_PATH" ]; then
    return 0
  fi

  # shellcheck disable=SC1090
  source "$SESSION_ENV_PATH"
  HAS_ACTIVE_SESSION=1
}

current_service_state() {
  local state="stopped"

  if [ "$HAS_ACTIVE_SESSION" != "1" ]; then
    printf '%s\n' "$state"
    return 0
  fi

  if [ -f "$SERVICE_STATE_PATH" ]; then
    state="$(jq -r '.state // "stopped"' "$SERVICE_STATE_PATH")"
  fi

  if [ "$state" != "stopped" ]; then
    if ! process_alive "${CONTROLLER_PID:-}" || ! process_alive "${CLIENT_PID:-}"; then
      printf 'failed\n'
      return 0
    fi
  fi

  printf '%s\n' "$state"
}

clear_current_link_if_reusable() {
  local state=""

  load_current_session
  if [ "$HAS_ACTIVE_SESSION" != "1" ]; then
    return 0
  fi

  state="$(current_service_state)"
  if [ "$state" = "stopped" ] || [ "$state" = "failed" ]; then
    rm -f "$(yaxunit_warm_rpc_current_link)"
    HAS_ACTIVE_SESSION=0
  fi
}

update_service_state() {
  local state="$1"
  local note="${2:-}"

  jq -n \
    --arg contour_id "$YAXUNIT_WARM_RPC_CONTOUR_ID" \
    --arg state "$state" \
    --arg note "$note" \
    --arg updated_at "$(timestamp_utc)" \
    --arg session_root "$SESSION_ROOT" \
    --arg profile_path "$PROFILE_PATH" \
    --arg profile_target "$SESSION_TARGET_ID" \
    --arg ready_file "$READY_FILE" \
    --arg command_dir "$COMMAND_DIR" \
    --arg shutdown_file "$SHUTDOWN_FILE" \
    --arg warm_config_path "$WARM_CONFIG_PATH" \
    --arg history_root "$HISTORY_ROOT" \
    --arg events_jsonl "$EVENTS_JSONL" \
    --arg rpc_host "$RPC_HOST" \
    --arg rpc_port "$RPC_PORT" \
    --arg controller_pid "${CONTROLLER_PID:-}" \
    --arg client_pid "${CLIENT_PID:-}" \
    --arg sync_evidence_path "${SYNC_EVIDENCE_PATH:-}" \
    --arg sync_prepared_at "${SYNC_EVIDENCE_PREPARED_AT:-}" \
    --arg sync_contract_hash "${SYNC_CONTRACT_HASH:-}" \
    '{
      contour_id: $contour_id,
      state: $state,
      note: (if $note == "" then null else $note end),
      updated_at: $updated_at,
      session_root: $session_root,
      profile_path: $profile_path,
      history_root: $history_root,
      controller_pid: (if $controller_pid == "" then null else ($controller_pid | tonumber) end),
      client_pid: (if $client_pid == "" then null else ($client_pid | tonumber) end),
      rpc: {
        host: $rpc_host,
        port: ($rpc_port | tonumber),
        key: "__REDACTED_SECRET__"
      },
      sync: {
        evidence_path: (if $sync_evidence_path == "" then null else $sync_evidence_path end),
        prepared_at: (if $sync_prepared_at == "" then null else $sync_prepared_at end),
        contract_hash: (if $sync_contract_hash == "" then null else $sync_contract_hash end)
      },
      control_plane: {
        ready_file: $ready_file,
        command_dir: $command_dir,
        shutdown_file: $shutdown_file,
        warm_config_path: $warm_config_path,
        events_jsonl: $events_jsonl
      }
    }' >"$SERVICE_STATE_PATH"
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local classification="$3"
  local message="${4:-}"
  local run_history="${5:-}"
  local service_state=""
  local profile_target=""

  service_state="$(current_service_state)"
  profile_target="$(target_profile_id)"
  jq -n \
    --arg status "$status" \
    --arg command "$COMMAND" \
    --arg contour_id "$YAXUNIT_WARM_RPC_CONTOUR_ID" \
    --arg profile_path "$PROFILE_PATH" \
    --arg profile_target "$profile_target" \
    --arg run_root "$RUN_ROOT" \
    --arg started_at "$STARTED_AT" \
    --arg finished_at "$(timestamp_utc)" \
    --arg classification "$classification" \
    --arg message "$message" \
    --arg service_state "$service_state" \
    --arg session_root "${SESSION_ROOT:-}" \
    --arg run_history "$run_history" \
    --arg service_state_path "${SERVICE_STATE_PATH:-}" \
    --arg warm_config_path "${WARM_CONFIG_PATH:-}" \
    --arg events_jsonl "${EVENTS_JSONL:-}" \
    --arg sync_evidence_path "${SYNC_EVIDENCE_PATH:-}" \
    --argjson exit_code "$exit_code" \
    '{
      status: $status,
      classification: $classification,
      message: (if $message == "" then null else $message end),
      contour: {
        id: $contour_id,
        command: $command
      },
      profile_path: $profile_path,
      runtime_profile: {
        target: (if $profile_target == "" then null else $profile_target end)
      },
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      failure: (if $status == "failed" then {classification: $classification, message: $message} else null end),
      service: {
        state: $service_state,
        session_root: (if $session_root == "" then null else $session_root end),
        state_json: (if $service_state_path == "" then null else $service_state_path end),
        warm_config: (if $warm_config_path == "" then null else $warm_config_path end),
        events_jsonl: (if $events_jsonl == "" then null else $events_jsonl end)
      },
      sync: {
        evidence_path: (if $sync_evidence_path == "" then null else $sync_evidence_path end)
      },
      history_bundle: (if $run_history == "" then null else $run_history end)
    }' >"$RUN_ROOT/summary.json"
}

collect_warm_source_extensions() {
  WARM_SOURCE_EXTENSIONS=()
  if [ -d "$PROJECT_ROOT/src/cfe/YAxUnit" ]; then
    WARM_SOURCE_EXTENSIONS+=("YAxUnit")
  fi
  if [ -d "$PROJECT_ROOT/src/cfe/YAxUnitTests" ]; then
    WARM_SOURCE_EXTENSIONS+=("YAxUnitTests")
  fi
}

yaxunit_warm_sync_command_hint() {
  local command="./scripts/test/sync-yaxunit-runtime.sh --profile $PROFILE_PATH --run-root /tmp/yaxunit-sync-run"
  local extension_name=""

  if [ -n "$TARGET_INPUT" ]; then
    command+=" --target $TARGET_INPUT"
  fi
  for extension_name in "${WARM_SOURCE_EXTENSIONS[@]}"; do
    command+=" --extension $extension_name"
  done

  printf '%s\n' "$command"
}

prepare_sync_guard() {
  local required_extension=""
  local current_hash=""
  local evidence_hash=""
  local selected_extensions_json=""

  collect_warm_source_extensions
  SYNC_EVIDENCE_PATH="$(yaxunit_sync_evidence_path "$PROFILE_PATH")"
  SYNC_REQUIRED=0
  SYNC_FAILURE_REASON=""
  SYNC_EVIDENCE_PREPARED_AT=""
  SYNC_CONTRACT_HASH=""

  if [ "${#WARM_SOURCE_EXTENSIONS[@]}" -eq 0 ]; then
    return 0
  fi

  if [ ! -f "$SYNC_EVIDENCE_PATH" ]; then
    SYNC_REQUIRED=1
    SYNC_FAILURE_REASON="yaxunit-sync required; run $(yaxunit_warm_sync_command_hint)"
    return 0
  fi
  if [ "$(jq -r '.status // empty' "$SYNC_EVIDENCE_PATH")" != "success" ]; then
    SYNC_REQUIRED=1
    SYNC_FAILURE_REASON="yaxunit-sync required; sync evidence is not successful: $SYNC_EVIDENCE_PATH"
    return 0
  fi
  if [ "$(jq -r '.contour_id // empty' "$SYNC_EVIDENCE_PATH")" != "$YAXUNIT_CONTOUR_ID" ]; then
    SYNC_REQUIRED=1
    SYNC_FAILURE_REASON="yaxunit-sync required; sync evidence has unexpected contour_id: $SYNC_EVIDENCE_PATH"
    return 0
  fi

  for required_extension in "${WARM_SOURCE_EXTENSIONS[@]}"; do
    if ! jq -e --arg extension "$required_extension" '(.selected_source_extensions // []) | index($extension)' "$SYNC_EVIDENCE_PATH" >/dev/null; then
      SYNC_REQUIRED=1
      SYNC_FAILURE_REASON="yaxunit-sync required; sync evidence does not include required source extension: $required_extension"
      return 0
    fi
  done

  mapfile -t EVIDENCE_SOURCE_EXTENSIONS < <(jq -r '.selected_source_extensions[]?' "$SYNC_EVIDENCE_PATH")
  selected_extensions_json="$(json_array_from_lines "${EVIDENCE_SOURCE_EXTENSIONS[@]}")"
  if [ "$(jq -c '.selected_source_extensions // []' "$SYNC_EVIDENCE_PATH")" != "$(jq -c '.' <<<"$selected_extensions_json")" ]; then
    SYNC_REQUIRED=1
    SYNC_FAILURE_REASON="yaxunit-sync required; selected_source_extensions must be an array of strings: $SYNC_EVIDENCE_PATH"
    return 0
  fi

  current_hash="$(yaxunit_contract_hash "$PROJECT_ROOT" EVIDENCE_SOURCE_EXTENSIONS)"
  evidence_hash="$(jq -r '.contract_hash // empty' "$SYNC_EVIDENCE_PATH")"
  if [ "$evidence_hash" != "$current_hash" ]; then
    SYNC_REQUIRED=1
    SYNC_FAILURE_REASON="yaxunit-sync required; selected YAxUnit scope changed after sync. Run $(yaxunit_warm_sync_command_hint)"
    return 0
  fi

  SYNC_EVIDENCE_PREPARED_AT="$(jq -r '.prepared_at // empty' "$SYNC_EVIDENCE_PATH")"
  SYNC_CONTRACT_HASH="$evidence_hash"
}

write_warm_config() {
  jq -n \
    --arg project_root "$PROJECT_ROOT" \
    --arg workspace_path "$SESSION_ROOT" \
    --arg host "$RPC_HOST" \
    --arg key "$RPC_KEY" \
    --argjson port "$RPC_PORT" \
    '{
      "ВыполнятьМодульноеТестирование": true,
      projectPath: $project_root,
      workspacePath: $workspace_path,
      closeAfterTests: false,
      showReport: true,
      filter: {
        tests: ["__yaxunit_warm_rpc_keepalive__.__noop__"]
      },
      rpc: {
        enable: true,
        transport: "ws",
        host: $host,
        port: $port,
        key: $key
      },
      logging: {
        enable: true,
        console: false,
        file: ($workspace_path + "/yaxunit-warm-rpc.log")
      }
    }' >"$WARM_CONFIG_PATH"
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
      --password=*|--db-pwd=*)
        printf '%q ' "${arg%%=*}=__REDACTED_SECRET__" >>"$command_path"
        ;;
      *)
        printf '%q ' "$arg" >>"$command_path"
        ;;
    esac
  done
  printf '\n' >>"$command_path"
}

build_client_command() {
  local array_name="$1"
  local -n out_ref="$array_name"

  CLIENT_BINARY="$(platform_client_binary_path)"
  ADAPTER="${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}"
  [ "$ADAPTER" = "direct-platform" ] || die "YAxUnit warm RPC requires runnerAdapter=direct-platform"

  out_ref=("$CLIENT_BINARY" "ENTERPRISE")
  append_connection_args out_ref
  append_auth_args out_ref
  out_ref+=(
    "/Lru"
    "/VLru"
    "/DisableStartupMessages"
    "/DisableStartupDialogs"
    "/C"
    "RunUnitTests=$WARM_CONFIG_PATH"
    "/out$ENTERPRISE_OUT"
  )
}

prepare_session_layout() {
  local session_id=""

  STARTED_AT="$(timestamp_utc)"
  session_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  SESSION_ROOT="$(yaxunit_warm_rpc_sessions_dir)/$session_id"
  SESSION_ENV_PATH="$SESSION_ROOT/session.env"
  SERVICE_STATE_PATH="$SESSION_ROOT/service-state.json"
  CONTROL_DIR="$SESSION_ROOT/control"
  COMMAND_DIR="$CONTROL_DIR/commands"
  READY_FILE="$CONTROL_DIR/ready.txt"
  SHUTDOWN_FILE="$CONTROL_DIR/shutdown.txt"
  EVENTS_JSONL="$SESSION_ROOT/events.jsonl"
  HISTORY_ROOT="$SESSION_ROOT/history"
  RUNTIME_HOME="$SESSION_ROOT/runtime/home"
  RUNTIME_XDG_CONFIG="$SESSION_ROOT/runtime/xdg-config"
  RUNTIME_XDG_CACHE="$SESSION_ROOT/runtime/xdg-cache"
  WARM_CONFIG_PATH="$SESSION_ROOT/config/yaxunit-warm-rpc.json"
  ENTERPRISE_OUT="$SESSION_ROOT/artifacts/enterprise.out"
  CLIENT_STDOUT_LOG="$SESSION_ROOT/client.stdout.log"
  CLIENT_STDERR_LOG="$SESSION_ROOT/client.stderr.log"
  CONTROLLER_STDOUT_LOG="$SESSION_ROOT/controller.stdout.log"
  CONTROLLER_STDERR_LOG="$SESSION_ROOT/controller.stderr.log"
  CLIENT_COMMAND_TXT="$SESSION_ROOT/yaxunit-warm-rpc.command.txt"
  RPC_PORT="${RPC_PORT_INPUT:-$(pick_unused_tcp_port 49000 49999)}"
  RPC_KEY="$(generate_rpc_key)"

  ensure_dir "$SESSION_ROOT"
  ensure_dir "$CONTROL_DIR"
  ensure_dir "$COMMAND_DIR"
  ensure_dir "$HISTORY_ROOT"
  ensure_dir "$(dirname -- "$WARM_CONFIG_PATH")"
  ensure_dir "$(dirname -- "$ENTERPRISE_OUT")"
  ensure_dir "$RUNTIME_HOME"
  ensure_dir "$RUNTIME_XDG_CONFIG"
  ensure_dir "$RUNTIME_XDG_CACHE"
  : >"$READY_FILE"
  : >"$SHUTDOWN_FILE"
  : >"$EVENTS_JSONL"
  write_warm_config
  write_session_env
  ln -sfn "$SESSION_ROOT" "$(yaxunit_warm_rpc_current_link)"
  HAS_ACTIVE_SESSION=1
}

start_controller_process() {
  require_command python3

  if command -v setsid >/dev/null 2>&1; then
    setsid python3 "$CONTROLLER_SCRIPT" \
      --host "$RPC_HOST" \
      --port "$RPC_PORT" \
      --key "$RPC_KEY" \
      --ready-file "$READY_FILE" \
      --command-dir "$COMMAND_DIR" \
      --shutdown-file "$SHUTDOWN_FILE" \
      --events-jsonl "$EVENTS_JSONL" \
      >"$CONTROLLER_STDOUT_LOG" \
      2>"$CONTROLLER_STDERR_LOG" \
      < /dev/null &
  else
    nohup python3 "$CONTROLLER_SCRIPT" \
      --host "$RPC_HOST" \
      --port "$RPC_PORT" \
      --key "$RPC_KEY" \
      --ready-file "$READY_FILE" \
      --command-dir "$COMMAND_DIR" \
      --shutdown-file "$SHUTDOWN_FILE" \
      --events-jsonl "$EVENTS_JSONL" \
      >"$CONTROLLER_STDOUT_LOG" \
      2>"$CONTROLLER_STDERR_LOG" \
      < /dev/null &
  fi
  CONTROLLER_PID="$!"
}

wait_for_controller_listening() {
  local deadline="$((SECONDS + TIMEOUT_SECONDS))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! process_alive "$CONTROLLER_PID"; then
      return 1
    fi
    if [ -f "$EVENTS_JSONL" ] && grep -F '"event": "listening"' "$EVENTS_JSONL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 2
}

start_client_process() {
  local -a launch_command=()
  local -a adapter_env=()
  local -a runtime_env=()

  build_client_command launch_command
  write_redacted_command_file "$CLIENT_COMMAND_TXT" "${launch_command[@]}"
  prepare_adapter_wrapper_env "$ADAPTER" adapter_env
  runtime_env=(
    "ONEC_TARGET_ID=$TARGET_INPUT"
    "ONEC_CAPABILITY_RUN_ROOT=$SESSION_ROOT/runtime"
    "HOME=$RUNTIME_HOME"
    "XDG_CONFIG_HOME=$RUNTIME_XDG_CONFIG"
    "XDG_CACHE_HOME=$RUNTIME_XDG_CACHE"
    "NO_AT_BRIDGE=${NO_AT_BRIDGE:-1}"
  )

  if command -v setsid >/dev/null 2>&1; then
    setsid env "${runtime_env[@]}" "${adapter_env[@]}" "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${launch_command[@]}" \
      >"$CLIENT_STDOUT_LOG" \
      2>"$CLIENT_STDERR_LOG" \
      < /dev/null &
  else
    nohup env "${runtime_env[@]}" "${adapter_env[@]}" "$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${launch_command[@]}" \
      >"$CLIENT_STDOUT_LOG" \
      2>"$CLIENT_STDERR_LOG" \
      < /dev/null &
  fi
  CLIENT_PID="$!"
}

wait_for_up_ready() {
  local deadline="$((SECONDS + TIMEOUT_SECONDS))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! process_alive "$CONTROLLER_PID"; then
      return 1
    fi
    if ! process_alive "$CLIENT_PID"; then
      return 2
    fi
    if [ "$(tr -d '\r\n' <"$READY_FILE" 2>/dev/null || true)" = "READY" ]; then
      return 0
    fi
    sleep 1
  done

  return 3
}

resolve_module_file() {
  local value="$1"

  [ -n "$value" ] || die "run requires --module-file <path>"
  case "$value" in
    /*)
      canonical_path "$value"
      ;;
    *)
      canonical_path "$PROJECT_ROOT/$value"
      ;;
  esac
}

module_file_hash() {
  local path_value="$1"

  sha256sum "$path_value" | awk '{print $1}'
}

wait_for_controller_result() {
  local result_path="$1"
  local deadline="$((SECONDS + TIMEOUT_SECONDS))"

  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ -f "$result_path" ]; then
      return 0
    fi
    if ! process_alive "$CONTROLLER_PID"; then
      return 1
    fi
    if ! process_alive "$CLIENT_PID"; then
      return 2
    fi
    sleep 1
  done

  return 3
}

fail_run_input() {
  local message="$1"

  update_service_state "ready" "run input rejected"
  write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "protocol failed" "$message"
  exit "$RUN_FAILURE_EXIT_CODE"
}

normalize_report() {
  local result_path="$1"
  local normalized_report="$2"

  jq '
    .report as $report
    | def tests:
        [
          $report
          | ..
          | objects
          | select(has("Статус") or has("status") or has("Результат") or has("result"))
        ];
      def junit_testcase_count:
        [
          $report
          | ..
          | objects
          | .testcase?
          | if type == "array" then length else 0 end
        ] | add // 0;
      def junit_declared_count:
        [
          $report
          | ..
          | objects
          | .tests?
          | tonumber? // 0
        ] | add // 0;
      def junit_failure_count:
        [
          $report
          | ..
          | objects
          | ((.errors? | tonumber? // 0) + (.failures? | tonumber? // 0))
        ] | add // 0;
      def testcase_failure_count:
        [
          $report
          | ..
          | objects
          | select((.error? | type) == "array" and (.error | length) > 0 or ((.failure? | type) == "array" and (.failure | length) > 0))
        ] | length;
      def status_value:
        (.["Статус"] // .status // .["Результат"] // .result // "" | tostring);
      tests as $tests
      | ($tests | length) as $status_test_count
      | ($tests | map(status_value | ascii_downcase | test("fail|failed|error|ошиб|провал")) | map(select(.)) | length) as $status_failed_count
      | {
          raw_report: $report,
          test_count: ([$status_test_count, junit_testcase_count, junit_declared_count] | max),
          failed_count: ($status_failed_count + junit_failure_count + testcase_failure_count)
        }
  ' "$result_path" >"$normalized_report"
}

write_run_summary() {
  local run_root="$1"
  local status="$2"
  local exit_code="$3"
  local classification="$4"
  local message="$5"
  local module_file="$6"
  local module_name="$7"
  local module_hash="$8"
  local raw_request="$9"
  local raw_response="${10}"
  local normalized_report="${11}"
  local result_path="${12}"
  local methods_json=""

  methods_json="$(json_array_from_lines "${METHODS[@]}")"
  jq -n \
    --arg status "$status" \
    --arg classification "$classification" \
    --arg message "$message" \
    --arg run_root "$run_root" \
    --arg module_file "$module_file" \
    --arg module_name "$module_name" \
    --arg module_hash "$module_hash" \
    --arg raw_request "$raw_request" \
    --arg raw_response "$raw_response" \
    --arg normalized_report "$normalized_report" \
    --arg result_path "$result_path" \
    --arg service_state_path "$SERVICE_STATE_PATH" \
    --arg session_root "$SESSION_ROOT" \
    --arg started_at "$STARTED_AT" \
    --arg finished_at "$(timestamp_utc)" \
    --argjson methods "$methods_json" \
    --argjson client "$( [ "$RUN_CLIENT" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson ordinary_client "$( [ "$RUN_ORDINARY_CLIENT" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson server "$( [ "$RUN_SERVER" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    '{
      status: $status,
      classification: $classification,
      message: (if $message == "" then null else $message end),
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      service: {
        session_root: $session_root,
        state_json: $service_state_path
      },
      input: {
        module_file: $module_file,
        module_hash: $module_hash,
        module_name: $module_name,
        methods: $methods,
        flags: {
          client: $client,
          ordinaryClient: $ordinary_client,
          server: $server
        }
      },
      artifacts: {
        raw_rpc_request: $raw_request,
        raw_rpc_response: $raw_response,
        normalized_report: $normalized_report,
        controller_result: $result_path
      },
      failure: (if $status == "failed" then {classification: $classification, message: $message} else null end)
    }' >"$run_root/summary.json"
}

rpc_methods_json() {
  local method=""
  local rpc_methods=()
  for method in "${METHODS[@]}"; do
    if [[ "$method" == *.* ]]; then
      rpc_methods+=("$method")
    else
      rpc_methods+=("$MODULE_NAME.$method")
    fi
  done
  json_array_from_lines "${rpc_methods[@]}"
}

command_up() {
  local wait_status=0

  STARTED_AT="$(timestamp_utc)"
  prepare_sync_guard
  clear_current_link_if_reusable
  load_current_session
  if [ "$HAS_ACTIVE_SESSION" = "1" ] && [ "$(current_service_state)" != "stopped" ]; then
    write_summary "failed" "$FAILURE_EXIT_CODE" "startup failed" "YAxUnit warm RPC service is already active"
    exit "$FAILURE_EXIT_CODE"
  fi

  if [ "$SYNC_REQUIRED" = "1" ]; then
    write_summary "failed" "$FAILURE_EXIT_CODE" "yaxunit-sync required" "$SYNC_FAILURE_REASON"
    exit "$FAILURE_EXIT_CODE"
  fi

  prepare_session_layout
  update_service_state "starting" "starting local WebSocket controller"
  start_controller_process
  write_session_env
  update_service_state "starting" "waiting for controller listen"

  if ! wait_for_controller_listening; then
    update_service_state "failed" "controller did not start listening"
    write_summary "failed" "$FAILURE_EXIT_CODE" "startup failed" "YAxUnit warm RPC controller did not start listening"
    stop_started_processes
    exit "$FAILURE_EXIT_CODE"
  fi

  update_service_state "starting" "starting 1C client with warm RunUnitTests config"
  start_client_process
  write_session_env
  update_service_state "starting" "waiting for YAxUnit hello"

  if wait_for_up_ready; then
    update_service_state "ready" "YAxUnit hello accepted"
    write_summary "success" 0 "success" "YAxUnit warm RPC service is ready"
    return 0
  else
    wait_status="$?"
  fi

  case "$wait_status" in
    1)
      update_service_state "failed" "controller exited before hello"
      write_summary "failed" "$FAILURE_EXIT_CODE" "startup failed" "YAxUnit warm RPC controller exited before hello"
      stop_started_processes
      ;;
    2)
      update_service_state "failed" "1C client exited before hello"
      write_summary "failed" "$FAILURE_EXIT_CODE" "startup failed" "1C client exited before YAxUnit hello"
      stop_started_processes
      ;;
    *)
      update_service_state "failed" "timeout waiting for hello"
      write_summary "failed" "$FAILURE_EXIT_CODE" "handshake failed" "Timed out waiting for YAxUnit hello"
      stop_started_processes
      ;;
  esac
  exit "$FAILURE_EXIT_CODE"
}

command_run() {
  local module_file=""
  local module_hash=""
  local run_id=""
  local run_history=""
  local request_path=""
  local tmp_request_path=""
  local result_path=""
  local raw_request=""
  local raw_response=""
  local normalized_report=""
  local wait_status=0
  local controller_status=""
  local controller_classification=""
  local controller_message=""
  local test_count=""
  local failed_count=""
  local session_sync_prepared_at=""
  local session_sync_contract_hash=""

  STARTED_AT="$(timestamp_utc)"
  load_current_session
  if [ "$HAS_ACTIVE_SESSION" != "1" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "runtime failed" "YAxUnit warm RPC service is not running"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi
  if [ -n "$REQUESTED_PROFILE_PATH" ] && [ "$REQUESTED_PROFILE_PATH" != "$PROFILE_PATH" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "yaxunit-sync required" "requested profile differs from active warm RPC service profile"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi
  if [ "$(current_service_state)" != "ready" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "runtime failed" "YAxUnit warm RPC service is not ready"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi

  session_sync_prepared_at="$SYNC_EVIDENCE_PREPARED_AT"
  session_sync_contract_hash="$SYNC_CONTRACT_HASH"
  prepare_sync_guard
  if [ "$SYNC_REQUIRED" = "1" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "yaxunit-sync required" "$SYNC_FAILURE_REASON"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi
  if [ -n "$SYNC_EVIDENCE_PREPARED_AT" ] && [ "$SYNC_EVIDENCE_PREPARED_AT" != "${session_sync_prepared_at:-$SYNC_EVIDENCE_PREPARED_AT}" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "yaxunit-sync required" "selected sync was refreshed after service startup; run down and up before trusted warm RPC run"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi
  if [ -n "$SYNC_CONTRACT_HASH" ] && [ "$SYNC_CONTRACT_HASH" != "${session_sync_contract_hash:-$SYNC_CONTRACT_HASH}" ]; then
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "yaxunit-sync required" "selected sync contract changed after service startup; run down and up before trusted warm RPC run"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi

  if [ -z "$MODULE_FILE_INPUT" ]; then
    fail_run_input "YAxUnit warm RPC MVP supports temporary module payloads; pass --module-file <path>"
  fi
  module_file="$(resolve_module_file "$MODULE_FILE_INPUT")"
  [ -f "$module_file" ] || fail_run_input "module file not found: $module_file"
  [ -n "$MODULE_NAME" ] || fail_run_input "run requires --module-name <name>"
  [ "${#METHODS[@]}" -gt 0 ] || fail_run_input "run requires at least one --method <name>"
  module_hash="$(module_file_hash "$module_file")"

  run_id="$(date -u +%Y%m%dT%H%M%SZ)-run"
  run_history="$HISTORY_ROOT/$run_id"
  ensure_dir "$run_history"
  cp "$module_file" "$run_history/module.bsl"
  result_path="$run_history/controller-result.json"
  raw_request="$run_history/raw-rpc-request.json"
  raw_response="$run_history/raw-rpc-response.json"
  normalized_report="$run_history/normalized-report.json"
  request_path="$COMMAND_DIR/$run_id.request.json"
  tmp_request_path="$request_path.tmp.$$"

  update_service_state "busy" "executing warm RPC module"
  jq -n \
    --arg id "$run_id" \
    --rawfile module "$module_file" \
    --arg module_name "$MODULE_NAME" \
    --arg result_path "$result_path" \
    --arg raw_request_path "$raw_request" \
    --arg raw_response_path "$raw_response" \
    --argjson methods "$(rpc_methods_json)" \
    --argjson timeout_seconds "$TIMEOUT_SECONDS" \
    --argjson client "$( [ "$RUN_CLIENT" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson ordinary_client "$( [ "$RUN_ORDINARY_CLIENT" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson server "$( [ "$RUN_SERVER" = "1" ] && printf 'true' || printf 'false' )" \
    '{
      type: "run",
      id: $id,
      timeout_seconds: $timeout_seconds,
      module: $module,
      moduleName: $module_name,
      methods: $methods,
      client: $client,
      ordinaryClient: $ordinary_client,
      server: $server,
      result_path: $result_path,
      raw_request_path: $raw_request_path,
      raw_response_path: $raw_response_path
    }' >"$tmp_request_path"
  mv "$tmp_request_path" "$request_path"

  if wait_for_controller_result "$result_path"; then
    :
  else
    wait_status="$?"
    case "$wait_status" in
      1)
        update_service_state "failed" "controller exited during run"
        write_run_summary "$run_history" "failed" "$RUN_FAILURE_EXIT_CODE" "protocol failed" "YAxUnit warm RPC controller exited during run" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
        write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "protocol failed" "YAxUnit warm RPC controller exited during run" "$run_history"
        exit "$RUN_FAILURE_EXIT_CODE"
        ;;
      2)
        update_service_state "failed" "client exited during run"
        write_run_summary "$run_history" "failed" "$RUN_FAILURE_EXIT_CODE" "runtime failed" "1C client exited during warm RPC run" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
        write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "runtime failed" "1C client exited during warm RPC run" "$run_history"
        exit "$RUN_FAILURE_EXIT_CODE"
        ;;
      *)
        update_service_state "ready" "run timed out; service may still be reusable"
        write_run_summary "$run_history" "failed" "$RUN_FAILURE_EXIT_CODE" "timeout" "Timed out waiting for warm RPC result" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
        write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "timeout" "Timed out waiting for warm RPC result" "$run_history"
        exit "$RUN_FAILURE_EXIT_CODE"
        ;;
    esac
  fi

  controller_status="$(jq -r '.status // "failed"' "$result_path")"
  controller_classification="$(jq -r '.classification // "protocol failed"' "$result_path")"
  controller_message="$(jq -r '.message // empty' "$result_path")"
  if [ "$controller_status" != "success" ]; then
    update_service_state "ready" "run failed before report"
    write_run_summary "$run_history" "failed" "$RUN_FAILURE_EXIT_CODE" "$controller_classification" "$controller_message" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
    write_summary "failed" "$RUN_FAILURE_EXIT_CODE" "$controller_classification" "$controller_message" "$run_history"
    exit "$RUN_FAILURE_EXIT_CODE"
  fi

  normalize_report "$result_path" "$normalized_report"
  test_count="$(jq -r '.test_count // 0' "$normalized_report")"
  failed_count="$(jq -r '.failed_count // 0' "$normalized_report")"
  if [ "$failed_count" != "0" ]; then
    update_service_state "ready" "last warm RPC run returned test failures"
    write_run_summary "$run_history" "failed" 1 "tests failed" "YAxUnit warm RPC tests failed" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
    write_summary "failed" 1 "tests failed" "YAxUnit warm RPC tests failed" "$run_history"
    exit 1
  fi

  update_service_state "ready" "last warm RPC run succeeded"
  write_run_summary "$run_history" "success" 0 "success" "YAxUnit warm RPC tests passed; test_count=$test_count" "$module_file" "$MODULE_NAME" "$module_hash" "$raw_request" "$raw_response" "$normalized_report" "$result_path"
  write_summary "success" 0 "success" "YAxUnit warm RPC tests passed; test_count=$test_count" "$run_history"
}

command_status() {
  STARTED_AT="$(timestamp_utc)"
  load_current_session
  write_summary "success" 0 "success" "YAxUnit warm RPC status captured"
}

command_down() {
  STARTED_AT="$(timestamp_utc)"
  load_current_session
  if [ "$HAS_ACTIVE_SESSION" != "1" ]; then
    write_summary "success" 0 "success" "YAxUnit warm RPC service is not running"
    return 0
  fi

  update_service_state "stopped" "shutdown requested"
  printf 'STOP\n' >"$SHUTDOWN_FILE"

  if process_alive "${CONTROLLER_PID:-}"; then
    if ! wait_for_process_exit_with_grace "$CONTROLLER_PID" "$TIMEOUT_SECONDS"; then
      signal_process_tree TERM "$CONTROLLER_PID"
      wait_for_process_exit_with_grace "$CONTROLLER_PID" 5 || signal_process_tree KILL "$CONTROLLER_PID"
    fi
  fi
  if process_alive "${CLIENT_PID:-}"; then
    signal_process_tree TERM "$CLIENT_PID"
    wait_for_process_exit_with_grace "$CLIENT_PID" 5 || signal_process_tree KILL "$CLIENT_PID"
  fi

  update_service_state "stopped" "service session stopped"
  rm -f "$(yaxunit_warm_rpc_current_link)"
  write_summary "success" 0 "success" "YAxUnit warm RPC service stopped"
}

parse_args "$@"
prepare_run_root
resolve_profile_path
[[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || die "--timeout must be numeric"
require_command jq
require_command python3
require_command sha256sum

case "$COMMAND" in
  up)
    command_up
    ;;
  run)
    command_run
    ;;
  status)
    command_status
    ;;
  down)
    command_down
    ;;
  *)
    die "unsupported YAxUnit warm RPC command: $COMMAND"
    ;;
esac
