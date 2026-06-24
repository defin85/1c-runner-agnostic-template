#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"
# shellcheck source=../lib/yaxunit.sh
source "$SCRIPT_DIR/../lib/yaxunit.sh"

PROFILE_INPUT="${ONEC_PROFILE_PATH:-}"
RUN_ROOT_INPUT="${ONEC_CAPABILITY_RUN_ROOT:-}"
CONFIG_INPUT=""
TARGET_INPUT=""
DRY_RUN=0
TIMEOUT_SECONDS="${ONEC_YAXUNIT_TIMEOUT_SECONDS:-900}"

FILTER_EXTENSIONS=()
FILTER_MODULES=()
FILTER_TESTS=()
FILTER_TAGS=()
FILTER_PATHS=()
REQUIRED_SOURCE_EXTENSIONS=()

PROFILE_PATH=""
RUN_ROOT=""
STDOUT_LOG=""
STDERR_LOG=""
COMMAND_TXT=""
ENTERPRISE_OUT=""
EFFECTIVE_CONFIG=""
EXIT_CODE_FILE=""
REPORTS_DIR=""
JUNIT_XML=""
JSON_REPORT=""
ALLURE_DIR=""
YAXUNIT_LOG=""
SYNC_EVIDENCE_PATH=""
SYNC_STATUS="not-checked"
SYNC_MESSAGE=""
STARTED_AT=""
FINISHED_AT=""
FINAL_EXIT_CODE=0
CLASSIFICATION=""
MESSAGE=""
RUNNER_EXIT_CODE=0
YAXUNIT_EXIT_CODE=""
YAXUNIT_TEST_COUNT=""
TIMED_OUT=false
CLIENT_BINARY=""
ADAPTER=""

usage() {
  cat <<'EOF'
Usage: ./scripts/test/run-yaxunit.sh [options]

Options:
  --profile <file>     Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>     Directory for summary.json, resolved config, logs, and reports
  --config <file>      YAxUnit JSON config to copy/normalize into run-root
  --target <id>        Target id from automation/context/target-matrix.json
  --extension <name>   YAxUnit filter.extensions entry; repeatable
  --module <name>      YAxUnit filter.modules entry; repeatable
  --test <name>        YAxUnit filter.tests entry; repeatable
  --tag <name>         YAxUnit filter.tags entry; repeatable
  --path <name>        YAxUnit filter.paths entry; repeatable
  --timeout-seconds <n>  Total timeout for the 1C/YAxUnit launch
  --dry-run            Resolve config and command without launching 1C or checking sync evidence
  -h, --help           Show this help
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
      --config)
        [ "$#" -ge 2 ] || fail "--config requires a value"
        CONFIG_INPUT="$2"
        shift 2
        ;;
      --target)
        [ "$#" -ge 2 ] || fail "--target requires a value"
        TARGET_INPUT="$2"
        shift 2
        ;;
      --extension)
        [ "$#" -ge 2 ] || fail "--extension requires a value"
        FILTER_EXTENSIONS+=("$2")
        shift 2
        ;;
      --module)
        [ "$#" -ge 2 ] || fail "--module requires a value"
        FILTER_MODULES+=("$2")
        shift 2
        ;;
      --test)
        [ "$#" -ge 2 ] || fail "--test requires a value"
        FILTER_TESTS+=("$2")
        shift 2
        ;;
      --tag)
        [ "$#" -ge 2 ] || fail "--tag requires a value"
        FILTER_TAGS+=("$2")
        shift 2
        ;;
      --path)
        [ "$#" -ge 2 ] || fail "--path requires a value"
        FILTER_PATHS+=("$2")
        shift 2
        ;;
      --timeout-seconds)
        [ "$#" -ge 2 ] || fail "--timeout-seconds requires a value"
        TIMEOUT_SECONDS="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        CAPABILITY_DRY_RUN=1
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

resolve_project_path() {
  local value="$1"

  case "$value" in
    /*)
      canonical_path "$value"
      ;;
    *)
      canonical_path "$PROJECT_ROOT/$value"
      ;;
  esac
}

resolve_profile_input() {
  local resolved=""

  resolved="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$resolved" ] || fail "runtime profile is required; pass --profile <file> or create env/local.json"
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

  mktemp -d "${TMPDIR:-/tmp}/yaxunit-run.XXXXXX"
}

resolve_config_input() {
  local resolved=""

  if [ -z "$CONFIG_INPUT" ]; then
    printf '\n'
    return 0
  fi

  resolved="$(resolve_project_path "$CONFIG_INPUT")"
  [ -f "$resolved" ] || fail_with_summary 64 "config failed" "YAxUnit config not found: $resolved"
  printf '%s\n' "$resolved"
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

  fail_with_summary 64 "runtime failed" "platform client binary not found next to platform.binaryPath: $candidate"
}

json_array_from_named_array_or_null() {
  local array_name="$1"
  local -n array_ref="$array_name"

  if [ "${#array_ref[@]}" -eq 0 ]; then
    printf 'null\n'
    return 0
  fi

  json_array_from_lines "${array_ref[@]}"
}

filter_patch_json() {
  local extensions_json=""
  local modules_json=""
  local tests_json=""
  local tags_json=""
  local paths_json=""

  extensions_json="$(json_array_from_named_array_or_null FILTER_EXTENSIONS)"
  modules_json="$(json_array_from_named_array_or_null FILTER_MODULES)"
  tests_json="$(json_array_from_named_array_or_null FILTER_TESTS)"
  tags_json="$(json_array_from_named_array_or_null FILTER_TAGS)"
  paths_json="$(json_array_from_named_array_or_null FILTER_PATHS)"

  jq -cn \
    --argjson extensions "$extensions_json" \
    --argjson modules "$modules_json" \
    --argjson tests "$tests_json" \
    --argjson tags "$tags_json" \
    --argjson paths "$paths_json" \
    '({})
      | if $extensions == null then . else .extensions = $extensions end
      | if $modules == null then . else .modules = $modules end
      | if $tests == null then . else .tests = $tests end
      | if $tags == null then . else .tags = $tags end
      | if $paths == null then . else .paths = $paths end'
}

cli_filter_present() {
  [ "${#FILTER_EXTENSIONS[@]}" -gt 0 ] \
    || [ "${#FILTER_MODULES[@]}" -gt 0 ] \
    || [ "${#FILTER_TESTS[@]}" -gt 0 ] \
    || [ "${#FILTER_TAGS[@]}" -gt 0 ] \
    || [ "${#FILTER_PATHS[@]}" -gt 0 ]
}

effective_config_has_selection() {
  jq -e '
    (.filter // {}) as $filter
    | [
        ($filter.extensions // []),
        ($filter.modules // []),
        ($filter.tests // []),
        ($filter.tags // []),
        ($filter.paths // []),
        ($filter.suites // []),
        ($filter.contexts // [])
      ]
    | map(select(type == "array" and length > 0))
    | length > 0
  ' "$EFFECTIVE_CONFIG" >/dev/null
}

create_base_config() {
  jq -n '{}'
}

write_effective_config() {
  local source_config="$1"
  local base_config=""
  local patch_json=""

  patch_json="$(filter_patch_json)"
  if [ -n "$source_config" ]; then
    base_config="$source_config"
  else
    base_config="$RUN_ROOT/yaxunit-empty-config.json"
    create_base_config >"$base_config"
  fi

  jq \
    --arg project_root "$PROJECT_ROOT" \
    --arg run_root "$RUN_ROOT" \
    --arg exit_code "$EXIT_CODE_FILE" \
    --arg log_file "$YAXUNIT_LOG" \
    --arg junit_xml "$JUNIT_XML" \
    --arg json_report "$JSON_REPORT" \
    --arg allure_dir "$ALLURE_DIR" \
    --argjson filter_patch "$patch_json" \
    '
      . + {
        "ВыполнятьМодульноеТестирование": true,
        projectPath: $project_root,
        workspacePath: $run_root,
        closeAfterTests: true,
        showReport: false,
        reportFormat: "jUnit",
        reportPath: $junit_xml,
        exitCode: $exit_code
      }
      | .logging = ((.logging // {}) + {
          enable: true,
          console: false,
          file: $log_file
        })
      | .reports = [
          {format: "jUnit", path: $junit_xml},
          {format: "dumpjson", path: $json_report},
          {format: "allure", path: $allure_dir}
        ]
      | .filter = ((.filter // {}) + $filter_patch)
    ' "$base_config" >"$EFFECTIVE_CONFIG"

  if ! effective_config_has_selection; then
    fail_with_summary 64 "config failed" "YAxUnit requires --extension/--module/--test/--tag/--path or a config with a non-empty filter"
  fi
}

collect_required_source_extensions() {
  local filter_extension=""
  local source_extension=""

  REQUIRED_SOURCE_EXTENSIONS=()
  if [ -d "$PROJECT_ROOT/src/cfe/YAxUnit" ]; then
    append_unique REQUIRED_SOURCE_EXTENSIONS "YAxUnit"
  fi

  for filter_extension in "${FILTER_EXTENSIONS[@]}"; do
    source_extension="$(yaxunit_source_extension_name "$filter_extension")"
    if [ -d "$PROJECT_ROOT/src/cfe/$source_extension" ]; then
      append_unique REQUIRED_SOURCE_EXTENSIONS "$source_extension"
    fi
  done

  while IFS= read -r filter_extension; do
    [ -n "$filter_extension" ] || continue
    source_extension="$(yaxunit_source_extension_name "$filter_extension")"
    if [ -d "$PROJECT_ROOT/src/cfe/$source_extension" ]; then
      append_unique REQUIRED_SOURCE_EXTENSIONS "$source_extension"
    fi
  done < <(jq -r '(.filter.extensions // [])[]?' "$EFFECTIVE_CONFIG")
}

check_sync_evidence() {
  local selected_extensions_json=""
  local current_hash=""
  local evidence_hash=""
  local required_extension=""

  collect_required_source_extensions
  SYNC_EVIDENCE_PATH="$(yaxunit_sync_evidence_path "$PROFILE_PATH")"

  if [ "${#REQUIRED_SOURCE_EXTENSIONS[@]}" -eq 0 ]; then
    SYNC_STATUS="not-required"
    return 0
  fi

  if [ ! -f "$SYNC_EVIDENCE_PATH" ]; then
    SYNC_STATUS="missing"
    SYNC_MESSAGE="YAxUnit sync evidence is missing. Run ./scripts/test/sync-yaxunit-runtime.sh --profile $PROFILE_PATH --run-root /tmp/yaxunit-sync-run before run-yaxunit."
    fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
  fi

  if [ "$(jq -r '.status // empty' "$SYNC_EVIDENCE_PATH")" != "success" ]; then
    SYNC_STATUS="invalid"
    SYNC_MESSAGE="YAxUnit sync evidence is not successful: $SYNC_EVIDENCE_PATH"
    fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
  fi

  if [ "$(jq -r '.contour_id // empty' "$SYNC_EVIDENCE_PATH")" != "$YAXUNIT_CONTOUR_ID" ]; then
    SYNC_STATUS="invalid"
    SYNC_MESSAGE="YAxUnit sync evidence has unexpected contour_id: $SYNC_EVIDENCE_PATH"
    fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
  fi

  for required_extension in "${REQUIRED_SOURCE_EXTENSIONS[@]}"; do
    if ! jq -e --arg extension "$required_extension" '(.selected_source_extensions // []) | index($extension)' "$SYNC_EVIDENCE_PATH" >/dev/null; then
      SYNC_STATUS="incomplete"
      SYNC_MESSAGE="YAxUnit sync evidence does not include required source extension: $required_extension"
      fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
    fi
  done

  mapfile -t EVIDENCE_SOURCE_EXTENSIONS < <(jq -r '.selected_source_extensions[]?' "$SYNC_EVIDENCE_PATH")
  selected_extensions_json="$(json_array_from_lines "${EVIDENCE_SOURCE_EXTENSIONS[@]}")"
  if [ "$(jq -c '.selected_source_extensions // []' "$SYNC_EVIDENCE_PATH")" != "$(jq -c '.' <<<"$selected_extensions_json")" ]; then
    SYNC_STATUS="invalid"
    SYNC_MESSAGE="YAxUnit sync evidence selected_source_extensions must be an array of strings: $SYNC_EVIDENCE_PATH"
    fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
  fi

  current_hash="$(yaxunit_contract_hash "$PROJECT_ROOT" EVIDENCE_SOURCE_EXTENSIONS)"
  evidence_hash="$(jq -r '.contract_hash // empty' "$SYNC_EVIDENCE_PATH")"
  if [ "$evidence_hash" != "$current_hash" ]; then
    SYNC_STATUS="stale"
    SYNC_MESSAGE="YAxUnit sync evidence is stale for selected source extensions. Run ./scripts/test/sync-yaxunit-runtime.sh --profile $PROFILE_PATH --run-root /tmp/yaxunit-sync-run."
    fail_with_summary 65 "yaxunit-sync required" "$SYNC_MESSAGE"
  fi

  SYNC_STATUS="current"
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

build_launch_command() {
  local array_name="$1"
  local -n out_ref="$array_name"

  CLIENT_BINARY="$(platform_client_binary_path)"
  ADAPTER="${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}"
  [ "$ADAPTER" = "direct-platform" ] || fail_with_summary 64 "runtime failed" "YAxUnit runner currently requires runnerAdapter=direct-platform"

  out_ref=("$CLIENT_BINARY" "ENTERPRISE")
  append_connection_args out_ref
  append_auth_args out_ref
  out_ref+=(
    "/Lru"
    "/VLru"
    "/DisableStartupMessages"
    "/DisableStartupDialogs"
    "/C"
    "RunUnitTests=$EFFECTIVE_CONFIG"
    "/out$ENTERPRISE_OUT"
  )
}

read_yaxunit_exit_code() {
  local raw=""

  if [ ! -s "$EXIT_CODE_FILE" ]; then
    printf '\n'
    return 0
  fi

  raw="$(tr -d '\r\n' <"$EXIT_CODE_FILE")"
  raw="${raw#$'\xEF\xBB\xBF'}"
  printf '%s\n' "$raw"
}

any_report_artifact_exists() {
  [ -s "$JUNIT_XML" ] || [ -s "$JSON_REPORT" ] || find "$ALLURE_DIR" -type f -size +0c 2>/dev/null | grep -q .
}

json_report_test_count() {
  if [ ! -s "$JSON_REPORT" ]; then
    printf '\n'
    return 0
  fi

  jq -r '[.[]?."НаборыТестов"[]?."Тесты"[]?] | length' "$JSON_REPORT"
}

classify_runtime_result() {
  YAXUNIT_EXIT_CODE="$(read_yaxunit_exit_code)"

  if [ "$TIMED_OUT" = true ]; then
    CLASSIFICATION="runner failed"
    MESSAGE="YAxUnit runner timed out"
    FINAL_EXIT_CODE=124
    return 0
  fi

  if [ -n "$YAXUNIT_EXIT_CODE" ]; then
    if ! [[ "$YAXUNIT_EXIT_CODE" =~ ^[0-9]+$ ]]; then
      CLASSIFICATION="runner failed"
      MESSAGE="YAxUnit exit-code artifact is not numeric"
      FINAL_EXIT_CODE=2
      return 0
    fi

    if [ -s "$JSON_REPORT" ]; then
      if ! YAXUNIT_TEST_COUNT="$(json_report_test_count)"; then
        CLASSIFICATION="runner failed"
        MESSAGE="YAxUnit JSON report is not valid JSON"
        FINAL_EXIT_CODE=2
        return 0
      fi
    fi

    if [ "$YAXUNIT_EXIT_CODE" = "0" ]; then
      if any_report_artifact_exists; then
        if [ -n "$YAXUNIT_TEST_COUNT" ]; then
          if [ "$YAXUNIT_TEST_COUNT" = "0" ]; then
            CLASSIFICATION="tests empty"
            MESSAGE="YAxUnit finished successfully but selected zero tests"
            FINAL_EXIT_CODE=2
            return 0
          fi
        fi
        CLASSIFICATION="success"
        MESSAGE="YAxUnit tests passed"
        FINAL_EXIT_CODE=0
        return 0
      fi
      CLASSIFICATION="runner failed"
      MESSAGE="YAxUnit wrote exit code 0 but no report artifacts were found"
      FINAL_EXIT_CODE=2
      return 0
    fi

    CLASSIFICATION="tests failed"
    MESSAGE="YAxUnit tests returned non-zero exit code"
    if [ "$YAXUNIT_EXIT_CODE" -le 255 ]; then
      FINAL_EXIT_CODE="$YAXUNIT_EXIT_CODE"
    else
      FINAL_EXIT_CODE=1
    fi
    return 0
  fi

  if [ "$RUNNER_EXIT_CODE" -ne 0 ]; then
    CLASSIFICATION="runner failed"
    MESSAGE="1C/YAxUnit process exited before writing exit-code artifact"
    FINAL_EXIT_CODE="$RUNNER_EXIT_CODE"
    return 0
  fi

  CLASSIFICATION="runner failed"
  MESSAGE="YAxUnit process exited without exit-code artifact"
  FINAL_EXIT_CODE=2
}

filters_json() {
  local extensions_json=""
  local modules_json=""
  local tests_json=""
  local tags_json=""
  local paths_json=""

  extensions_json="$(json_array_from_named_array_or_null FILTER_EXTENSIONS)"
  modules_json="$(json_array_from_named_array_or_null FILTER_MODULES)"
  tests_json="$(json_array_from_named_array_or_null FILTER_TESTS)"
  tags_json="$(json_array_from_named_array_or_null FILTER_TAGS)"
  paths_json="$(json_array_from_named_array_or_null FILTER_PATHS)"

  jq -cn \
    --argjson extensions "$extensions_json" \
    --argjson modules "$modules_json" \
    --argjson tests "$tests_json" \
    --argjson tags "$tags_json" \
    --argjson paths "$paths_json" \
    '{
      extensions: (if $extensions == null then [] else $extensions end),
      modules: (if $modules == null then [] else $modules end),
      tests: (if $tests == null then [] else $tests end),
      tags: (if $tags == null then [] else $tags end),
      paths: (if $paths == null then [] else $paths end)
    }'
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local classification="$3"
  local message="$4"
  local filters=""
  local required_sources_json=""
  local profile_target=""

  filters="$(filters_json)"
  required_sources_json="$(json_array_from_lines "${REQUIRED_SOURCE_EXTENSIONS[@]}")"
  profile_target="$(target_profile_id)"

  jq -n \
    --arg status "$status" \
    --arg profile_path "$PROFILE_PATH" \
    --arg profile_target "$profile_target" \
    --arg run_root "$RUN_ROOT" \
    --arg started_at "$STARTED_AT" \
    --arg finished_at "$FINISHED_AT" \
    --arg classification "$classification" \
    --arg message "$message" \
    --arg config_input "$CONFIG_INPUT" \
    --arg effective_config "$EFFECTIVE_CONFIG" \
    --arg command_txt "$COMMAND_TXT" \
    --arg stdout_log "$STDOUT_LOG" \
    --arg stderr_log "$STDERR_LOG" \
    --arg enterprise_out "$ENTERPRISE_OUT" \
    --arg exit_code_file "$EXIT_CODE_FILE" \
    --arg junit_xml "$JUNIT_XML" \
    --arg json_report "$JSON_REPORT" \
    --arg allure_dir "$ALLURE_DIR" \
    --arg yaxunit_log "$YAXUNIT_LOG" \
    --arg sync_evidence_path "$SYNC_EVIDENCE_PATH" \
    --arg sync_status "$SYNC_STATUS" \
    --arg sync_message "$SYNC_MESSAGE" \
    --arg client_binary "$CLIENT_BINARY" \
    --arg adapter "$ADAPTER" \
    --arg yaxunit_exit_code "$YAXUNIT_EXIT_CODE" \
    --arg yaxunit_test_count "$YAXUNIT_TEST_COUNT" \
    --argjson dry_run "$( [ "$DRY_RUN" = "1" ] && printf 'true' || printf 'false' )" \
    --argjson exit_code "$exit_code" \
    --argjson runner_exit_code "$RUNNER_EXIT_CODE" \
    --argjson timed_out "$TIMED_OUT" \
    --argjson timeout_seconds "$TIMEOUT_SECONDS" \
    --argjson filters "$filters" \
    --argjson required_sources "$required_sources_json" \
    '{
      status: $status,
      capability: {
        id: "yaxunit",
        label: "Run YAxUnit checks"
      },
      profile_path: $profile_path,
      runtime_profile: {
        target: (if $profile_target == "" then null else $profile_target end)
      },
      run_root: $run_root,
      started_at: (if $started_at == "" then null else $started_at end),
      finished_at: (if $finished_at == "" then null else $finished_at end),
      exit_code: $exit_code,
      dry_run: $dry_run,
      classification: $classification,
      message: $message,
      runtime: {
        adapter: (if $adapter == "" then null else $adapter end),
        client_binary: (if $client_binary == "" then null else $client_binary end),
        timeout_seconds: $timeout_seconds,
        timed_out: $timed_out,
        runner_exit_code: $runner_exit_code,
        yaxunit_exit_code: (if $yaxunit_exit_code == "" then null else ($yaxunit_exit_code | tonumber? // $yaxunit_exit_code) end),
        yaxunit_test_count: (if $yaxunit_test_count == "" then null else ($yaxunit_test_count | tonumber? // $yaxunit_test_count) end)
      },
      selection: {
        config_input: (if $config_input == "" then null else $config_input end),
        filters: $filters,
        effective_config: $effective_config
      },
      sync: {
        status: $sync_status,
        message: (if $sync_message == "" then null else $sync_message end),
        evidence_path: (if $sync_evidence_path == "" then null else $sync_evidence_path end),
        required_source_extensions: $required_sources
      },
      failure: (if $status == "failed" then {
        classification: $classification,
        message: $message
      } else null end),
      artifacts: {
        summary_json: ($run_root + "/summary.json"),
        effective_config: $effective_config,
        command_txt: $command_txt,
        stdout_log: $stdout_log,
        stderr_log: $stderr_log,
        enterprise_out: $enterprise_out,
        exit_code_file: $exit_code_file,
        yaxunit_log: $yaxunit_log,
        reports: {
          junit_xml: $junit_xml,
          json_report: $json_report,
          allure_dir: $allure_dir
        }
      }
    }' >"$RUN_ROOT/summary.json"
}

fail_with_summary() {
  local exit_code="$1"
  local classification="$2"
  local message="$3"

  FINAL_EXIT_CODE="$exit_code"
  CLASSIFICATION="$classification"
  MESSAGE="$message"
  FINISHED_AT="$(timestamp_utc)"
  if [ -n "$RUN_ROOT" ]; then
    write_summary "failed" "$FINAL_EXIT_CODE" "$CLASSIFICATION" "$MESSAGE"
  fi
  printf 'yaxunit-classification=%s\n' "$CLASSIFICATION" >&2
  printf 'yaxunit-message=%s\n' "$MESSAGE" >&2
  [ -z "$RUN_ROOT" ] || printf 'yaxunit-run-root=%s\n' "$RUN_ROOT" >&2
  exit "$FINAL_EXIT_CODE"
}

run_yaxunit() {
  local -a launch_command=()
  local -a adapter_env=()
  local -a wrapped_command=()
  local -a exec_prefix=()
  local -a target_env=()

  build_launch_command launch_command
  write_redacted_command_file "$COMMAND_TXT" "${launch_command[@]}"

  if [ "$DRY_RUN" = "1" ]; then
    CLASSIFICATION="dry-run"
    MESSAGE="YAxUnit dry-run completed"
    FINAL_EXIT_CODE=0
    FINISHED_AT="$(timestamp_utc)"
    write_summary "dry-run" "$FINAL_EXIT_CODE" "$CLASSIFICATION" "$MESSAGE"
    return 0
  fi

  check_sync_evidence

  wrapped_command=("$PROJECT_ROOT/scripts/adapters/direct-platform.sh" "${launch_command[@]}")
  prepare_adapter_wrapper_env "$ADAPTER" adapter_env
  if [ -n "$TARGET_INPUT" ]; then
    target_env=("ONEC_TARGET_ID=$TARGET_INPUT")
  fi
  if command -v timeout >/dev/null 2>&1; then
    exec_prefix=(timeout "$TIMEOUT_SECONDS")
  fi

  set +e
  env "${target_env[@]}" "${adapter_env[@]}" "${exec_prefix[@]}" "${wrapped_command[@]}" >"$STDOUT_LOG" 2>"$STDERR_LOG"
  RUNNER_EXIT_CODE=$?
  set -e
  if [ "$RUNNER_EXIT_CODE" -eq 124 ]; then
    TIMED_OUT=true
  fi

  classify_runtime_result
  FINISHED_AT="$(timestamp_utc)"
  if [ "$FINAL_EXIT_CODE" -eq 0 ]; then
    write_summary "success" "$FINAL_EXIT_CODE" "$CLASSIFICATION" "$MESSAGE"
  else
    write_summary "failed" "$FINAL_EXIT_CODE" "$CLASSIFICATION" "$MESSAGE"
  fi
}

parse_args "$@"

require_command jq
[[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || fail "--timeout-seconds must be numeric"

PROFILE_PATH="$(resolve_profile_input)"
RUN_ROOT="$(resolve_run_root_input)"
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded
target_require_requested "$PROJECT_ROOT" "$TARGET_INPUT"

REPORTS_DIR="$RUN_ROOT/reports"
JUNIT_XML="$REPORTS_DIR/junit.xml"
JSON_REPORT="$REPORTS_DIR/report.json"
ALLURE_DIR="$REPORTS_DIR/allure"
YAXUNIT_LOG="$RUN_ROOT/yaxunit.log"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"
ENTERPRISE_OUT="$RUN_ROOT/enterprise.out.log"
COMMAND_TXT="$RUN_ROOT/yaxunit.command.txt"
EFFECTIVE_CONFIG="$RUN_ROOT/yaxunit.effective.json"
EXIT_CODE_FILE="$RUN_ROOT/yaxunit.exit-code.txt"

mkdir -p "$RUN_ROOT" "$REPORTS_DIR" "$ALLURE_DIR"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

STARTED_AT="$(timestamp_utc)"
CONFIG_PATH="$(resolve_config_input)"
if [ -z "$CONFIG_PATH" ] && ! cli_filter_present; then
  fail_with_summary 64 "config failed" "YAxUnit requires --extension/--module/--test/--tag/--path or --config"
fi

write_effective_config "$CONFIG_PATH"
collect_required_source_extensions
run_yaxunit

printf 'yaxunit-run-root=%s\n' "$RUN_ROOT"
printf 'yaxunit-classification=%s\n' "$CLASSIFICATION"
printf 'yaxunit-exit-code=%s\n' "$FINAL_EXIT_CODE"

exit "$FINAL_EXIT_CODE"
