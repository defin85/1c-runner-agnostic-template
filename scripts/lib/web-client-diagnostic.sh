#!/usr/bin/env bash
set -euo pipefail

web_client_diagnostic_opt_in_enabled() {
  local profile_path="$1"
  local env_value="${ONEC_WEB_CLIENT_DIAGNOSTIC_ON_FAILURE:-auto}"

  case "$env_value" in
    1|true|yes|on)
      return 0
      ;;
    0|false|no|off)
      return 1
      ;;
  esac

  [ -f "$profile_path" ] || return 1
  jq -e '(.capabilities.webClientDiagnostic.postFailure // false) == true' "$profile_path" >/dev/null 2>&1
}

run_web_client_diagnostic_on_failure() {
  local project_root="$1"
  local profile_path="$2"
  local source_run_root="$3"
  local diagnostic_run_root="$4"
  local source_stage="$5"
  local source_feature="${6:-}"
  local source_scenario="${7:-}"
  local source_step="${8:-}"
  local -a command_args=()

  if ! web_client_diagnostic_opt_in_enabled "$profile_path"; then
    return 0
  fi

  mkdir -p "$diagnostic_run_root"
  command_args=(
    --profile "$profile_path"
    --run-root "$diagnostic_run_root"
    --source-run-root "$source_run_root"
    --source-stage "$source_stage"
  )
  if [ -n "$source_feature" ]; then
    command_args+=(--feature "$source_feature")
  fi
  if [ -n "$source_scenario" ]; then
    command_args+=(--scenario "$source_scenario")
  fi
  if [ -n "$source_step" ]; then
    command_args+=(--step "$source_step")
  fi

  set +e
  "$project_root/scripts/test/run-web-client-diagnostic.sh" "${command_args[@]}"
  set -e

  return 0
}

web_client_diagnostic_summary_path_for_run_root() {
  printf '%s/web-client-diagnostic/summary.json\n' "$1"
}

web_client_diagnostic_link_json() {
  local summary_path="$1"

  if [ ! -f "$summary_path" ]; then
    printf 'null\n'
    return 0
  fi

  jq -c '{
    status: .status,
    summary_json: (.artifacts.summaryJson // $summary_path),
    run_root: .runRoot,
    reason: .statusReason,
    source: .source,
    target: {
      profile: .target.profile,
      publication: .target.publication,
      sameInfobase: .target.sameInfobase
    },
    verdict_boundary: .verdictBoundary
  }' --arg summary_path "$summary_path" "$summary_path"
}
