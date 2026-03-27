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
  local reason="${5-}"

  jq -cn \
    --arg name "$name" \
    --arg status "$status" \
    --arg reason "$reason" \
    --argjson required "$required" \
    '{
      name: $name,
      status: $status,
      required: $required,
      reason: (if $reason == "" then null else $reason end)
    }' >>"$jsonl_path"
}

doctor_partial_import_contour_state_json() {
  local contour_id="$1"
  local adapter="$2"
  local root="$3"
  local reason=""
  local status="present"
  local source="driver-selection"
  local load_src_driver=""

  if capability_has_profile_unsupported_reason "load-src"; then
    source="unsupported-profile"
    reason="$(require_profile_string "$(capability_unsupported_reason_expr "load-src") // empty" "$(capability_unsupported_reason_expr "load-src")")"
  elif capability_has_profile_command "load-src"; then
    source="profile-command"
    reason="partial load-src is not supported when capabilities.loadSrc.command override is set"
  else
    load_src_driver="$(resolve_capability_driver "load-src")"
    if [ "$load_src_driver" != "ibcmd" ]; then
      reason="partial load-src requires capabilities.loadSrc.driver=ibcmd"
    else
      reason="$(doctor_capability_failure_reason "load-src" "$adapter")"
      if [ -z "$reason" ]; then
        reason="$(doctor_partial_import_repo_dependency_reason "$contour_id" "$root")"
      fi
    fi
  fi

  if [ -n "$reason" ]; then
    status="missing"
  fi

  jq -cn \
    --arg name "$contour_id" \
    --arg status "$status" \
    --arg source "$source" \
    --arg driver "$load_src_driver" \
    --arg reason "$reason" \
    '{
      name: $name,
      status: $status,
      required: false,
      source: (if $source == "" then null else $source end),
      driver: (if $driver == "" then null else $driver end),
      reason: (if $reason == "" then null else $reason end)
    }'
}

doctor_partial_import_repo_dependency_reason() {
  local contour_id="$1"
  local root="$2"
  local rel_path=""
  local absolute_path=""
  local -a required_paths=()

  case "$contour_id" in
    load-diff-src)
      required_paths=("scripts/platform/load-diff-src.sh")
      ;;
    load-task-src)
      required_paths=("scripts/platform/load-task-src.sh" "scripts/git/task-trailers.sh")
      ;;
    *)
      printf '\n'
      return 0
      ;;
  esac

  for rel_path in "${required_paths[@]}"; do
    absolute_path="$root/$rel_path"
    if [ ! -f "$absolute_path" ]; then
      case "$rel_path" in
        scripts/git/*)
          printf 'missing repo helper: %s\n' "$rel_path"
          ;;
        *)
          printf 'missing repo script: %s\n' "$rel_path"
          ;;
      esac
      return 0
    fi

    if [ ! -x "$absolute_path" ]; then
      case "$rel_path" in
        scripts/git/*)
          printf 'repo helper is not executable: %s\n' "$rel_path"
          ;;
        *)
          printf 'repo script is not executable: %s\n' "$rel_path"
          ;;
      esac
      return 0
    fi
  done

  printf '\n'
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
    platform.ibcmdPath)
      profile_has_nonnull '.platform.ibcmdPath' && printf 'present\n' || printf 'missing\n'
      ;;
    platform.xvfb.enabled)
      [ "$(profile_string '(.platform.xvfb.enabled // null) | if . == null then "null" else type end')" = "boolean" ] && printf 'present\n' || printf 'missing\n'
      ;;
    platform.xvfb.serverArgs)
      [ "$(profile_string '(.platform.xvfb.serverArgs // null) | if . == null then "null" else type end')" = "array" ] && printf 'present\n' || printf 'missing\n'
      ;;
    platform.ldPreload.enabled)
      [ "$(profile_string '(.platform.ldPreload.enabled // null) | if . == null then "null" else type end')" = "boolean" ] && printf 'present\n' || printf 'missing\n'
      ;;
    platform.ldPreload.libraries)
      [ "$(profile_string '(.platform.ldPreload.libraries // null) | if . == null then "null" else type end')" = "array" ] && printf 'present\n' || printf 'missing\n'
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
    ibcmd.runtimeMode)
      profile_has_nonnull '.ibcmd.runtimeMode' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.serverAccess.mode)
      profile_has_nonnull '.ibcmd.serverAccess.mode' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.serverAccess.dataDir)
      profile_has_nonnull '.ibcmd.serverAccess.dataDir' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.auth.user)
      profile_has_nonnull '.ibcmd.auth.user' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.auth.passwordEnv)
      profile_has_nonnull '.ibcmd.auth.passwordEnv' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.standalone.databasePath)
      profile_has_nonnull '.ibcmd.standalone.databasePath' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.fileInfobase.databasePath)
      profile_has_nonnull '.ibcmd.fileInfobase.databasePath' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.dbmsInfobase.kind)
      profile_has_nonnull '.ibcmd.dbmsInfobase.kind' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.dbmsInfobase.server)
      profile_has_nonnull '.ibcmd.dbmsInfobase.server' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.dbmsInfobase.name)
      profile_has_nonnull '.ibcmd.dbmsInfobase.name' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.dbmsInfobase.user)
      profile_has_nonnull '.ibcmd.dbmsInfobase.user' && printf 'present\n' || printf 'missing\n'
      ;;
    ibcmd.dbmsInfobase.passwordEnv)
      profile_has_nonnull '.ibcmd.dbmsInfobase.passwordEnv' && printf 'present\n' || printf 'missing\n'
      ;;
    *)
      printf 'missing\n'
      ;;
  esac
}

capability_status() {
  local capability_id="$1"
  local adapter="$2"
  local check_reason=""

  if capability_has_profile_unsupported_reason "$capability_id"; then
    check_reason="$(require_profile_string "$(capability_unsupported_reason_expr "$capability_id") // empty" "$(capability_unsupported_reason_expr "$capability_id")")"
    printf 'unsupported\t%s\n' "$check_reason"
    return 0
  fi

  check_reason="$(doctor_capability_failure_reason "$capability_id" "$adapter")"
  if [ -z "$check_reason" ]; then
    printf 'present\n'
  else
    printf 'missing\t%s\n' "$check_reason"
  fi
}

doctor_allows_unsupported_required_capability() {
  case "$1" in
    run-xunit|run-bdd|run-smoke)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

main() {
  local root=""
  local profile_path=""
  local adapter=""
  local run_root=""
  local summary_path=""
  local stdout_log=""
  local stderr_log=""
  local required_tools_jsonl=""
  local optional_tools_jsonl=""
  local required_fields_jsonl=""
  local required_env_refs_jsonl=""
  local required_capabilities_jsonl=""
  local optional_capabilities_jsonl=""
  local derived_contours_jsonl=""
  local capability_drivers_json="{}"
  local required_tools_json="[]"
  local optional_tools_json="[]"
  local required_fields_json="[]"
  local required_env_refs_json="[]"
  local required_capabilities_json="[]"
  local optional_capabilities_json="[]"
  local derived_contours_json="[]"
  local status="success"
  local layout_warning_json="{}"
  local tool_name=""
  local field_name=""
  local env_name=""
  local capability_id=""
  local derived_contour_id=""
  local check_status=""
  local check_reason=""
  local derived_state_json=""
  local warning_path_list=""
  local -a layout_drift_paths=()
  local -a required_tools=(git jq rg)
  local -a optional_tools=(openspec bd)
  local -a required_fields=()
  local -a required_env_refs=()
  local -a required_capabilities=(create-ib dump-src load-src update-db diff-src run-xunit run-bdd run-smoke)
  local -a optional_capabilities=(publish-http)
  local -a derived_contours=(load-diff-src load-task-src)

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
  if doctor_requires_direct_platform_xvfb_tools "$adapter"; then
    required_tools+=(xvfb-run xauth)
  fi
  run_root="$(prepare_capability_run_root "doctor" "$CAPABILITY_RUN_ROOT_INPUT")"
  summary_path="$(capability_summary_path "$run_root")"
  stdout_log="$run_root/stdout.log"
  stderr_log="$run_root/stderr.log"
  required_tools_jsonl="$run_root/required-tools.jsonl"
  optional_tools_jsonl="$run_root/optional-tools.jsonl"
  required_fields_jsonl="$run_root/required-profile-fields.jsonl"
  required_env_refs_jsonl="$run_root/required-env-refs.jsonl"
  required_capabilities_jsonl="$run_root/required-capabilities.jsonl"
  optional_capabilities_jsonl="$run_root/optional-capabilities.jsonl"
  derived_contours_jsonl="$run_root/derived-contours.jsonl"
  : >"$stdout_log"
  : >"$stderr_log"
  : >"$required_tools_jsonl"
  : >"$optional_tools_jsonl"
  : >"$required_fields_jsonl"
  : >"$required_env_refs_jsonl"
  : >"$required_capabilities_jsonl"
  : >"$optional_capabilities_jsonl"
  : >"$derived_contours_jsonl"

  exec 3>&1 4>&2
  exec > >(tee -a "$stdout_log" >&3) 2> >(tee -a "$stderr_log" >&4)

  collect_required_profile_fields "$adapter" required_fields
  collect_required_env_refs required_env_refs
  collect_runtime_profile_layout_drift_paths "$root" layout_drift_paths
  layout_warning_json="$(build_runtime_profile_layout_warning_json "$root")"

  log "Run 1C runtime doctor"
  log "adapter=$adapter"
  log "profile=$profile_path"
  log "run_root=$run_root"
  if [ "${layout_drift_paths[*]-}" != "" ]; then
    warning_path_list="$(printf '%s, ' "${layout_drift_paths[@]}")"
    warning_path_list="${warning_path_list%, }"
    log "warning: non-canonical runtime profiles in env/: $warning_path_list. Move ad-hoc profiles to ${RUNTIME_PROFILE_LOCAL_SANDBOX_DIR}"
  fi

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
    check_status="present"
    check_reason=""
    if doctor_allows_unsupported_required_capability "$capability_id" && capability_has_profile_unsupported_reason "$capability_id"; then
      check_status="unsupported"
      check_reason="$(require_profile_string "$(capability_unsupported_reason_expr "$capability_id") // empty" "$(capability_unsupported_reason_expr "$capability_id")")"
    else
      check_reason="$(doctor_capability_failure_reason "$capability_id" "$adapter")"
      if [ -n "$check_reason" ]; then
        check_status="missing"
      fi
    fi
    if [ "$check_status" = "missing" ]; then
      status="failed"
      log "missing capability precondition: $capability_id ($check_reason)"
    fi
    append_json_check "$required_capabilities_jsonl" "$capability_id" "$check_status" true "$check_reason"
  done

  for capability_id in "${optional_capabilities[@]}"; do
    IFS=$'\t' read -r check_status check_reason <<EOF
$(capability_status "$capability_id" "$adapter")
EOF
    append_json_check "$optional_capabilities_jsonl" "$capability_id" "$check_status" false "$check_reason"
  done

  for derived_contour_id in "${derived_contours[@]}"; do
    derived_state_json="$(doctor_partial_import_contour_state_json "$derived_contour_id" "$adapter" "$root")"
    printf '%s\n' "$derived_state_json" >>"$derived_contours_jsonl"
    check_status="$(jq -r '.status' <<<"$derived_state_json")"
    check_reason="$(jq -r '.reason // empty' <<<"$derived_state_json")"
    if [ "$check_status" = "missing" ]; then
      log "operator-local contour not ready: $derived_contour_id ($check_reason)"
    fi
  done

  required_tools_json="$(jq -s '.' "$required_tools_jsonl")"
  optional_tools_json="$(jq -s '.' "$optional_tools_jsonl")"
  required_fields_json="$(jq -s '.' "$required_fields_jsonl")"
  required_env_refs_json="$(jq -s '.' "$required_env_refs_jsonl")"
  required_capabilities_json="$(jq -s '.' "$required_capabilities_jsonl")"
  optional_capabilities_json="$(jq -s '.' "$optional_capabilities_jsonl")"
  derived_contours_json="$(jq -s '.' "$derived_contours_jsonl")"
  capability_drivers_json="$(build_doctor_capability_drivers_json "$adapter")"

  jq -n \
    --arg status "$status" \
    --arg adapter "$adapter" \
    --arg profile_path "$profile_path" \
    --arg run_root "$run_root" \
    --arg summary_path "$summary_path" \
    --arg stdout_log "$stdout_log" \
    --arg stderr_log "$stderr_log" \
    --argjson required_tools "$required_tools_json" \
    --argjson optional_tools "$optional_tools_json" \
    --argjson required_profile_fields "$required_fields_json" \
    --argjson required_env_refs "$required_env_refs_json" \
    --argjson required_capabilities "$required_capabilities_json" \
    --argjson optional_capabilities "$optional_capabilities_json" \
    --argjson derived_contours "$derived_contours_json" \
    --argjson capability_drivers "$capability_drivers_json" \
    --argjson warnings "$layout_warning_json" \
    --argjson context "$(build_doctor_context_json "$adapter")" \
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
        summary_json: $summary_path,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log
      },
      capability_drivers: $capability_drivers,
      checks: {
        required_tools: $required_tools,
        optional_tools: $optional_tools,
        required_profile_fields: $required_profile_fields,
        required_env_refs: $required_env_refs,
        required_capabilities: $required_capabilities,
        optional_capabilities: $optional_capabilities,
        derived_contours: $derived_contours
      },
      warnings: $warnings
    } + $context' >"$summary_path"

  log "summary_json=$summary_path"

  if [ "$status" = "failed" ] && [ "$CAPABILITY_DRY_RUN" != "1" ]; then
    exit 1
  fi
}

main "$@"
