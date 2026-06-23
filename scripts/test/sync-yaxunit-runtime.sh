#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/runtime-profile.sh
source "$SCRIPT_DIR/../lib/runtime-profile.sh"
# shellcheck source=../lib/yaxunit.sh
source "$SCRIPT_DIR/../lib/yaxunit.sh"

PROFILE_INPUT=""
RUN_ROOT_INPUT=""
SYNC_LABEL="yaxunit-runtime"
DRY_RUN=0
WITH_DESIGNER_CHECKS=0
SOURCE_EXTENSIONS=()
RUNTIME_FLAG_EXTENSIONS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/test/sync-yaxunit-runtime.sh [options]

Options:
  --profile <file>       Runtime profile JSON
  --run-root <dir>       Directory for stage summary and delegated artifacts
  --sync-label <label>   Label recorded in YAxUnit sync evidence
  --extension <name>     Source extension directory to sync; repeatable. Defaults to YAxUnit and YAxUnitTests when present.
  --with-designer-checks Run selected Designer applicability/config diagnostics before update-db
  --dry-run              Resolve staged commands and write dry-run summaries only
  -h, --help             Show this help
EOF
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
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
        [ "$#" -ge 2 ] || fail "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --run-root)
        [ "$#" -ge 2 ] || fail "--run-root requires a value"
        RUN_ROOT_INPUT="$2"
        shift 2
        ;;
      --sync-label)
        [ "$#" -ge 2 ] || fail "--sync-label requires a value"
        SYNC_LABEL="$2"
        shift 2
        ;;
      --extension)
        [ "$#" -ge 2 ] || fail "--extension requires a value"
        append_unique SOURCE_EXTENSIONS "$(yaxunit_source_extension_name "$2")"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --with-designer-checks)
        WITH_DESIGNER_CHECKS=1
        shift
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

resolve_run_root() {
  local resolved=""

  if [ -n "$RUN_ROOT_INPUT" ]; then
    resolved="$(canonical_path "$RUN_ROOT_INPUT")"
    mkdir -p "$resolved"
    printf '%s\n' "$resolved"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/yaxunit-sync.XXXXXX"
}

resolve_profile_path() {
  local resolved=""

  resolved="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$resolved" ] || fail "--profile is required"
  printf '%s\n' "$(canonical_path "$resolved")"
}

collect_default_extensions() {
  if [ "${#SOURCE_EXTENSIONS[@]}" -gt 0 ]; then
    return 0
  fi

  if [ -d "$PROJECT_ROOT/src/cfe/YAxUnit" ]; then
    SOURCE_EXTENSIONS+=("YAxUnit")
  fi
  if [ -d "$PROJECT_ROOT/src/cfe/YAxUnitTests" ]; then
    SOURCE_EXTENSIONS+=("YAxUnitTests")
  elif [ -d "$PROJECT_ROOT/src/cfe/Smoke" ]; then
    SOURCE_EXTENSIONS+=("Smoke")
  fi
}

validate_source_extensions() {
  local extension_name=""

  for extension_name in "${SOURCE_EXTENSIONS[@]}"; do
    [ -d "$PROJECT_ROOT/src/cfe/$extension_name" ] || fail "extension source not found under src/cfe: $extension_name"
  done
}

collect_runtime_flag_extensions() {
  local source_extension=""

  RUNTIME_FLAG_EXTENSIONS=()
  for source_extension in "${SOURCE_EXTENSIONS[@]}"; do
    append_unique RUNTIME_FLAG_EXTENSIONS "$(yaxunit_runtime_extension_name "$source_extension")"
  done
}

stage_status() {
  local summary_path="$1"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r '.status // empty' "$summary_path"
}

stage_failure_classification() {
  local step="$1"
  local summary_path=""
  local classification=""

  case "$step" in
    load-cfe)
      summary_path="$LOAD_CFE_RUN_ROOT/summary.json"
      ;;
    configure-cfe-runtime-flags)
      summary_path="$CONFIGURE_CFE_RUNTIME_FLAGS_RUN_ROOT/summary.json"
      ;;
    check-cfe-applicability)
      summary_path="$CHECK_CFE_APPLICABILITY_RUN_ROOT/summary.json"
      ;;
    check-cfe-config)
      summary_path="$CHECK_CFE_CONFIG_RUN_ROOT/summary.json"
      ;;
    update-db)
      summary_path="$UPDATE_DB_RUN_ROOT/summary.json"
      ;;
    *)
      printf '\n'
      return 0
      ;;
  esac

  if [ -f "$summary_path" ]; then
    classification="$(jq -r '.failure.classification // .failure_classification // empty' "$summary_path")"
  fi
  if [ -n "$classification" ]; then
    printf '%s\n' "$classification"
    return 0
  fi

  case "$step" in
    load-cfe)
      printf 'sync failed\n'
      ;;
    configure-cfe-runtime-flags)
      printf 'runtime-flags failed\n'
      ;;
    check-cfe-applicability|check-cfe-config)
      printf 'config failed\n'
      ;;
    update-db)
      printf 'config failed\n'
      ;;
    *)
      printf '\n'
      ;;
  esac
}

extension_args() {
  local extension_name=""

  for extension_name in "${SOURCE_EXTENSIONS[@]}"; do
    printf '%s\n' "--extension"
    printf '%s\n' "$extension_name"
  done
}

runtime_flag_extension_args() {
  local extension_name=""

  for extension_name in "${RUNTIME_FLAG_EXTENSIONS[@]}"; do
    printf '%s\n' "--extension"
    printf '%s\n' "$extension_name"
  done
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local failed_step="$3"
  local started_at="$4"
  local finished_at="$5"
  local sync_evidence_path=""
  local source_extensions_json=""
  local runtime_flag_extensions_json=""
  local failure_classification=""

  source_extensions_json="$(json_array_from_lines "${SOURCE_EXTENSIONS[@]}")"
  runtime_flag_extensions_json="$(json_array_from_lines "${RUNTIME_FLAG_EXTENSIONS[@]}")"
  sync_evidence_path="$(yaxunit_sync_evidence_path "$PROFILE_PATH")"
  failure_classification="$(stage_failure_classification "$failed_step")"

  jq -n \
    --arg status "$status" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg sync_label "$SYNC_LABEL" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg failed_step "$failed_step" \
    --arg failure_classification "$failure_classification" \
    --arg sync_evidence_path "$sync_evidence_path" \
    --arg load_cfe_run_root "$LOAD_CFE_RUN_ROOT" \
    --arg configure_cfe_runtime_flags_run_root "$CONFIGURE_CFE_RUNTIME_FLAGS_RUN_ROOT" \
    --arg check_cfe_applicability_run_root "$CHECK_CFE_APPLICABILITY_RUN_ROOT" \
    --arg check_cfe_config_run_root "$CHECK_CFE_CONFIG_RUN_ROOT" \
    --arg update_db_run_root "$UPDATE_DB_RUN_ROOT" \
    --arg load_cfe_status "$(stage_status "$LOAD_CFE_RUN_ROOT/summary.json")" \
    --arg configure_cfe_runtime_flags_status "$(stage_status "$CONFIGURE_CFE_RUNTIME_FLAGS_RUN_ROOT/summary.json")" \
    --arg check_cfe_applicability_status "$(stage_status "$CHECK_CFE_APPLICABILITY_RUN_ROOT/summary.json")" \
    --arg check_cfe_config_status "$(stage_status "$CHECK_CFE_CONFIG_RUN_ROOT/summary.json")" \
    --arg update_db_status "$(stage_status "$UPDATE_DB_RUN_ROOT/summary.json")" \
    --argjson exit_code "$exit_code" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson with_designer_checks "$( [ "$WITH_DESIGNER_CHECKS" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson source_extensions "$source_extensions_json" \
    --argjson runtime_flag_extensions "$runtime_flag_extensions_json" \
    '{
      status: $status,
      stage: {
        id: "sync-yaxunit-runtime",
        label: "Sync YAxUnit runtime"
      },
      profile_path: $profile_path,
      run_root: $run_root,
      sync_label: (if $sync_label == "" then null else $sync_label end),
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      dry_run: $dry_run,
      designer_checks: {
        enabled: $with_designer_checks
      },
      selected_source_extensions: $source_extensions,
      runtime_flag_extensions: $runtime_flag_extensions,
      failed_step: (if $failed_step == "" then null else $failed_step end),
      failure_classification: (if $failure_classification == "" then null else $failure_classification end),
      steps: [
        {id: "load-cfe", run_root: $load_cfe_run_root, summary_json: ($load_cfe_run_root + "/summary.json"), status: (if $load_cfe_status == "" then null else $load_cfe_status end)},
        {id: "configure-cfe-runtime-flags", run_root: $configure_cfe_runtime_flags_run_root, summary_json: ($configure_cfe_runtime_flags_run_root + "/summary.json"), status: (if $configure_cfe_runtime_flags_status == "" then null else $configure_cfe_runtime_flags_status end)},
        {id: "check-cfe-applicability", run_root: $check_cfe_applicability_run_root, summary_json: ($check_cfe_applicability_run_root + "/summary.json"), status: (if $check_cfe_applicability_status == "" then null else $check_cfe_applicability_status end)},
        {id: "check-cfe-config", run_root: $check_cfe_config_run_root, summary_json: ($check_cfe_config_run_root + "/summary.json"), status: (if $check_cfe_config_status == "" then null else $check_cfe_config_status end)},
        {id: "update-db", run_root: $update_db_run_root, summary_json: ($update_db_run_root + "/summary.json"), status: (if $update_db_status == "" then null else $update_db_status end)}
      ],
      artifacts: {
        summary_json: ($run_root + "/summary.json"),
        stdout_log: ($run_root + "/stdout.log"),
        stderr_log: ($run_root + "/stderr.log"),
        yaxunit_sync_evidence: $sync_evidence_path
      }
    }' >"$RUN_ROOT/summary.json"
}

run_step() {
  local step_name="$1"
  local exit_code=0
  shift

  printf '[sync-yaxunit-runtime] %s\n' "$step_name" >>"$STDOUT_LOG"
  set +e
  "$@" >>"$STDOUT_LOG" 2>>"$STDERR_LOG"
  exit_code=$?
  set -e
  if [ "$exit_code" -eq 0 ]; then
    return 0
  fi

  STEP_FAILED="$step_name"
  STEP_EXIT_CODE="$exit_code"
  return "$exit_code"
}

parse_args "$@"

require_command jq
collect_default_extensions
[ "${#SOURCE_EXTENSIONS[@]}" -gt 0 ] || fail "no YAxUnit source extensions selected"
validate_source_extensions
collect_runtime_flag_extensions

PROFILE_PATH="$(resolve_profile_path)"
RUN_ROOT="$(resolve_run_root)"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"
LOAD_CFE_RUN_ROOT="$RUN_ROOT/load-cfe"
CONFIGURE_CFE_RUNTIME_FLAGS_RUN_ROOT="$RUN_ROOT/configure-cfe-runtime-flags"
CHECK_CFE_APPLICABILITY_RUN_ROOT="$RUN_ROOT/check-cfe-applicability"
CHECK_CFE_CONFIG_RUN_ROOT="$RUN_ROOT/check-cfe-config"
UPDATE_DB_RUN_ROOT="$RUN_ROOT/update-db"
STEP_FAILED=""
STEP_EXIT_CODE=0
STEP_ARGS=()
SOURCE_EXTENSION_ARGS=()
RUNTIME_FLAG_EXTENSION_ARGS=()

mkdir -p "$RUN_ROOT"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

if [ "$DRY_RUN" = "1" ]; then
  STEP_ARGS+=(--dry-run)
fi
mapfile -t SOURCE_EXTENSION_ARGS < <(extension_args)
mapfile -t RUNTIME_FLAG_EXTENSION_ARGS < <(runtime_flag_extension_args)

started_at="$(timestamp_utc)"
status="success"

if ! run_step "load-cfe" \
  "$PROJECT_ROOT/scripts/platform/load-cfe.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$LOAD_CFE_RUN_ROOT" \
  "${SOURCE_EXTENSION_ARGS[@]}" \
  "${STEP_ARGS[@]}"; then
  status="failed"
elif ! run_step "configure-cfe-runtime-flags" \
  "$PROJECT_ROOT/scripts/platform/configure-cfe-runtime-flags.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$CONFIGURE_CFE_RUNTIME_FLAGS_RUN_ROOT" \
  "${RUNTIME_FLAG_EXTENSION_ARGS[@]}" \
  "${STEP_ARGS[@]}"; then
  status="failed"
elif [ "$WITH_DESIGNER_CHECKS" = "1" ] && ! run_step "check-cfe-applicability" \
  "$PROJECT_ROOT/scripts/platform/check-cfe-applicability.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$CHECK_CFE_APPLICABILITY_RUN_ROOT" \
  "${SOURCE_EXTENSION_ARGS[@]}" \
  "${STEP_ARGS[@]}"; then
  status="failed"
elif [ "$WITH_DESIGNER_CHECKS" = "1" ] && ! run_step "check-cfe-config" \
  "$PROJECT_ROOT/scripts/platform/check-cfe-config.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$CHECK_CFE_CONFIG_RUN_ROOT" \
  "${SOURCE_EXTENSION_ARGS[@]}" \
  "${STEP_ARGS[@]}"; then
  status="failed"
elif ! run_step "update-db" \
  "$PROJECT_ROOT/scripts/platform/update-db.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$UPDATE_DB_RUN_ROOT" \
  "${STEP_ARGS[@]}"; then
  status="failed"
fi

if [ "$status" = "success" ] && [ "$DRY_RUN" != "1" ]; then
  yaxunit_write_sync_evidence \
    "$PROJECT_ROOT" \
    "$PROFILE_PATH" \
    "$RUN_ROOT" \
    "$SYNC_LABEL" \
    SOURCE_EXTENSIONS \
    RUNTIME_FLAG_EXTENSIONS >>"$STDOUT_LOG"
fi

if [ "$status" = "success" ] && [ "$DRY_RUN" = "1" ]; then
  status="dry-run"
fi

finished_at="$(timestamp_utc)"
write_summary "$status" "$STEP_EXIT_CODE" "$STEP_FAILED" "$started_at" "$finished_at"

if [ "$status" = "failed" ]; then
  exit "$STEP_EXIT_CODE"
fi
