#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

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

profile_field_status() {
  local field_name="$1"

  case "$field_name" in
    runnerAdapter)
      [ -n "${RUNTIME_PROFILE_RUNNER_ADAPTER:-}" ] && printf 'present\n' || printf 'missing\n'
      ;;
    platform.binaryPath)
      profile_has_nonnull '.platform.binaryPath' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.mode)
      profile_has_nonnull '.infobase.mode' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.filePath)
      profile_has_nonnull '.infobase.filePath' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.server)
      profile_has_nonnull '.infobase.server' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.ref)
      profile_has_nonnull '.infobase.ref' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.auth.user)
      profile_has_nonnull '.infobase.auth.user' && printf 'present\n' || printf 'missing\n'
      ;;
    infobase.auth.passwordEnv)
      profile_has_nonnull '.infobase.auth.passwordEnv' && printf 'present\n' || printf 'missing\n'
      ;;
    *)
      printf 'missing\n'
      ;;
  esac
}

capability_status() {
  local capability_id="$1"
  local adapter="$2"

  if doctor_has_required_capability "$capability_id" "$adapter"; then
    printf 'present\n'
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
  local required_fields_jsonl=""
  local required_env_refs_jsonl=""
  local required_capabilities_jsonl=""
  local optional_capabilities_jsonl=""
  local required_tools_json="[]"
  local optional_tools_json="[]"
  local required_fields_json="[]"
  local required_env_refs_json="[]"
  local required_capabilities_json="[]"
  local optional_capabilities_json="[]"
  local status="success"
  local tool_name=""
  local field_name=""
  local env_name=""
  local capability_id=""
  local check_status=""
  local -a required_tools=(git jq rg)
  local -a optional_tools=(openspec bd)
  local -a required_fields=()
  local -a required_env_refs=()
  local -a required_capabilities=(create-ib dump-src load-src update-db diff-src run-xunit run-bdd run-smoke)
  local -a optional_capabilities=(publish-http)

  parse_capability_cli_args "$@"
  if [ "$CAPABILITY_SHOW_HELP" = "1" ]; then
    usage
    exit 0
  fi

  root="$(project_root)"
  profile_path="$(resolve_runtime_profile_path "$CAPABILITY_PROFILE_INPUT" "$root")"
  load_runtime_profile "$profile_path"
  require_runtime_profile_loaded

  adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
  run_root="$(prepare_capability_run_root "doctor" "$CAPABILITY_RUN_ROOT_INPUT")"
  summary_path="$(capability_summary_path "$run_root")"
  required_tools_jsonl="$run_root/required-tools.jsonl"
  optional_tools_jsonl="$run_root/optional-tools.jsonl"
  required_fields_jsonl="$run_root/required-profile-fields.jsonl"
  required_env_refs_jsonl="$run_root/required-env-refs.jsonl"
  required_capabilities_jsonl="$run_root/required-capabilities.jsonl"
  optional_capabilities_jsonl="$run_root/optional-capabilities.jsonl"
  : >"$required_tools_jsonl"
  : >"$optional_tools_jsonl"
  : >"$required_fields_jsonl"
  : >"$required_env_refs_jsonl"
  : >"$required_capabilities_jsonl"
  : >"$optional_capabilities_jsonl"

  collect_required_profile_fields "$adapter" required_fields
  collect_required_env_refs required_env_refs

  log "Run 1C runtime doctor"
  log "adapter=$adapter"
  log "profile=$profile_path"
  log "run_root=$run_root"

  for tool_name in "${required_tools[@]}"; do
    if command -v "$tool_name" >/dev/null 2>&1; then
      check_status="present"
    else
      check_status="missing"
      status="failed"
    fi
    append_json_check "$required_tools_jsonl" "$tool_name" "$check_status" true
  done

  for tool_name in "${optional_tools[@]}"; do
    if command -v "$tool_name" >/dev/null 2>&1; then
      check_status="present"
    else
      check_status="missing"
    fi
    append_json_check "$optional_tools_jsonl" "$tool_name" "$check_status" false
  done

  for field_name in "${required_fields[@]}"; do
    check_status="$(profile_field_status "$field_name")"
    if [ "$check_status" != "present" ]; then
      status="failed"
    fi
    append_json_check "$required_fields_jsonl" "$field_name" "$check_status" true
  done

  for env_name in "${required_env_refs[@]}"; do
    if [ -n "${!env_name:-}" ]; then
      check_status="set"
    else
      check_status="missing"
      status="failed"
    fi
    append_json_check "$required_env_refs_jsonl" "$env_name" "$check_status" true
  done

  for capability_id in "${required_capabilities[@]}"; do
    check_status="$(capability_status "$capability_id" "$adapter")"
    if [ "$check_status" != "present" ]; then
      status="failed"
    fi
    append_json_check "$required_capabilities_jsonl" "$capability_id" "$check_status" true
  done

  for capability_id in "${optional_capabilities[@]}"; do
    check_status="$(capability_status "$capability_id" "$adapter")"
    append_json_check "$optional_capabilities_jsonl" "$capability_id" "$check_status" false
  done

  required_tools_json="$(jq -s '.' "$required_tools_jsonl")"
  optional_tools_json="$(jq -s '.' "$optional_tools_jsonl")"
  required_fields_json="$(jq -s '.' "$required_fields_jsonl")"
  required_env_refs_json="$(jq -s '.' "$required_env_refs_jsonl")"
  required_capabilities_json="$(jq -s '.' "$required_capabilities_jsonl")"
  optional_capabilities_json="$(jq -s '.' "$optional_capabilities_jsonl")"

  jq -n \
    --arg status "$status" \
    --arg adapter "$adapter" \
    --arg profile_path "$profile_path" \
    --arg run_root "$run_root" \
    --arg summary_path "$summary_path" \
    --argjson required_tools "$required_tools_json" \
    --argjson optional_tools "$optional_tools_json" \
    --argjson required_profile_fields "$required_fields_json" \
    --argjson required_env_refs "$required_env_refs_json" \
    --argjson required_capabilities "$required_capabilities_json" \
    --argjson optional_capabilities "$optional_capabilities_json" \
    --argjson context "$(build_redacted_context_json)" \
    '{
      status: $status,
      capability: {
        id: "doctor",
        label: "1C runtime doctor"
      },
      adapter: $adapter,
      profile_path: $profile_path,
      run_root: $run_root,
      artifacts: {
        summary_json: $summary_path
      },
      checks: {
        required_tools: $required_tools,
        optional_tools: $optional_tools,
        required_profile_fields: $required_profile_fields,
        required_env_refs: $required_env_refs,
        required_capabilities: $required_capabilities,
        optional_capabilities: $optional_capabilities
      }
    } + $context' >"$summary_path"

  log "summary_json=$summary_path"

  if [ "$status" = "failed" ] && [ "$CAPABILITY_DRY_RUN" != "1" ]; then
    exit 1
  fi
}

main "$@"
