#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/diag/doctor.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>   Directory for summary.json and diagnostic artifacts
  --dry-run          Resolve profile and write summary without failing the shell
  -h, --help         Show this help
EOF
}

append_json_check() {
  local jsonl_path="$1"
  local name="$2"
  local status="$3"
  local required="$4"

  jq -cn \
    --arg name "$name" \
    --arg status "$status" \
    --argjson required "$required" \
    '{name: $name, status: $status, required: $required}' >>"$jsonl_path"
}

env_var_status() {
  local var_name="$1"
  if [ -n "${!var_name:-}" ]; then
    printf 'set\n'
  else
    printf 'missing\n'
  fi
}

main() {
  local root=""
  local profile_path=""
  local adapter=""
  local run_root=""
  local summary_path=""
  local required_tools_jsonl=""
  local optional_tools_jsonl=""
  local required_env_jsonl=""
  local optional_env_jsonl=""
  local required_tools_json="[]"
  local optional_tools_json="[]"
  local required_env_json="[]"
  local optional_env_json="[]"
  local status="success"
  local tool_name=""
  local env_name=""
  local required_status=""
  local optional_status=""
  local -a required_tools=(git jq rg)
  local -a optional_tools=(openspec bd)
  local -a required_env=()
  local -a optional_env=(BSL_LANGUAGE_SERVER_JAR)

  parse_capability_cli_args "$@"
  if [ "$CAPABILITY_SHOW_HELP" = "1" ]; then
    usage
    exit 0
  fi

  root="$(project_root)"
  profile_path="$(resolve_runtime_profile_path "$CAPABILITY_PROFILE_INPUT" "$root")"
  load_runtime_profile "$profile_path"

  adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
  run_root="$(prepare_capability_run_root "doctor" "$CAPABILITY_RUN_ROOT_INPUT")"
  summary_path="$(capability_summary_path "$run_root")"
  required_tools_jsonl="$run_root/required-tools.jsonl"
  optional_tools_jsonl="$run_root/optional-tools.jsonl"
  required_env_jsonl="$run_root/required-env.jsonl"
  optional_env_jsonl="$run_root/optional-env.jsonl"
  : >"$required_tools_jsonl"
  : >"$optional_tools_jsonl"
  : >"$required_env_jsonl"
  : >"$optional_env_jsonl"

  case "$adapter" in
    direct-platform)
      required_env=(
        CREATE_IB_CMD
        DUMP_SRC_CMD
        LOAD_SRC_CMD
        UPDATE_DB_CMD
        DIFF_SRC_CMD
        XUNIT_RUN_CMD
        BDD_RUN_CMD
        SMOKE_RUN_CMD
      )
      optional_env+=(PUBLISH_HTTP_CMD)
      ;;
    remote-windows)
      required_env=(
        WINDOWS_CREATE_IB_CMD
        WINDOWS_DUMP_SRC_CMD
        WINDOWS_LOAD_SRC_CMD
        WINDOWS_UPDATE_DB_CMD
        WINDOWS_DIFF_SRC_CMD
        WINDOWS_XUNIT_RUN_CMD
        WINDOWS_BDD_RUN_CMD
        WINDOWS_SMOKE_RUN_CMD
      )
      optional_env+=(WINDOWS_PUBLISH_HTTP_CMD)
      ;;
    vrunner)
      required_env=(
        VRUNNER_CREATE_IB_CMD
        VRUNNER_DUMP_SRC_CMD
        VRUNNER_LOAD_SRC_CMD
        VRUNNER_UPDATE_DB_CMD
        VRUNNER_DIFF_SRC_CMD
        VRUNNER_XUNIT_CMD
        VRUNNER_BDD_CMD
        VRUNNER_SMOKE_CMD
      )
      optional_env+=(VRUNNER_PUBLISH_HTTP_CMD)
      ;;
    *)
      die "unsupported RUNNER_ADAPTER: $adapter"
      ;;
  esac

  log "Run 1C runtime doctor"
  log "adapter=$adapter"
  if [ -n "$profile_path" ]; then
    log "profile=$profile_path"
  fi
  log "run_root=$run_root"

  for tool_name in "${required_tools[@]}"; do
    if command -v "$tool_name" >/dev/null 2>&1; then
      required_status="present"
    else
      required_status="missing"
      status="failed"
    fi
    append_json_check "$required_tools_jsonl" "$tool_name" "$required_status" true
  done

  for tool_name in "${optional_tools[@]}"; do
    if command -v "$tool_name" >/dev/null 2>&1; then
      optional_status="present"
    else
      optional_status="missing"
    fi
    append_json_check "$optional_tools_jsonl" "$tool_name" "$optional_status" false
  done

  for env_name in "${required_env[@]}"; do
    required_status="$(env_var_status "$env_name")"
    if [ "$required_status" != "set" ]; then
      status="failed"
    fi
    append_json_check "$required_env_jsonl" "$env_name" "$required_status" true
  done

  for env_name in "${optional_env[@]}"; do
    append_json_check "$optional_env_jsonl" "$env_name" "$(env_var_status "$env_name")" false
  done

  required_tools_json="$(jq -s '.' "$required_tools_jsonl")"
  optional_tools_json="$(jq -s '.' "$optional_tools_jsonl")"
  required_env_json="$(jq -s '.' "$required_env_jsonl")"
  optional_env_json="$(jq -s '.' "$optional_env_jsonl")"

  jq -n \
    --arg status "$status" \
    --arg adapter "$adapter" \
    --arg profile_path "$profile_path" \
    --arg run_root "$run_root" \
    --arg summary_path "$summary_path" \
    --argjson required_tools "$required_tools_json" \
    --argjson optional_tools "$optional_tools_json" \
    --argjson required_env "$required_env_json" \
    --argjson optional_env "$optional_env_json" \
    '{
      status: $status,
      capability: {
        id: "doctor",
        label: "1C runtime doctor"
      },
      adapter: $adapter,
      profile_path: (if $profile_path == "" then null else $profile_path end),
      run_root: $run_root,
      artifacts: {
        summary_json: $summary_path
      },
      checks: {
        required_tools: $required_tools,
        optional_tools: $optional_tools,
        required_env: $required_env,
        optional_env: $optional_env
      }
    }' >"$summary_path"

  log "summary_json=$summary_path"

  if [ "$status" = "failed" ] && [ "$CAPABILITY_DRY_RUN" != "1" ]; then
    exit 1
  fi
}

main "$@"
