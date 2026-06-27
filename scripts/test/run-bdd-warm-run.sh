#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEC_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
PROFILE_PATH="${ONEC_PROFILE_PATH:-}"
TARGET_ID="${ONEC_TARGET_ID:-}"
RUN_ROOT="${ONEC_CAPABILITY_RUN_ROOT:-${TMPDIR:-/tmp}/bdd-warm-run}"
TIMEOUT_SECONDS="${ONEC_BDD_RUN_TIMEOUT_SECONDS:-1800}"

# shellcheck source=../lib/runtime-profile.sh
source "$PROJECT_ROOT/scripts/lib/runtime-profile.sh"

[ -n "$PROFILE_PATH" ] || { printf 'ONEC_PROFILE_PATH is required\n' >&2; exit 2; }
[ -n "$TARGET_ID" ] || { printf 'ONEC_TARGET_ID is required\n' >&2; exit 2; }
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded

mkdir -p "$RUN_ROOT/features" "$RUN_ROOT/warm-service"

json_escape_array() {
  jq -R . | jq -s .
}

read_service_token() {
  local file="$1"
  local value=""

  [ -f "$file" ] || return 0
  value="$(head -n 1 "$file" | tr -d '\r')"
  value="${value#$'\xef\xbb\xbf'}"
  printf '%s' "$value"
}

resolve_feature_path() {
  local value="$1"

  case "$value" in
    "")
      return 1
      ;;
    /*)
      printf '%s\n' "$value"
      ;;
    features/*)
      printf '%s/%s\n' "$PROJECT_ROOT" "$value"
      ;;
    tests/*)
      printf '%s/%s\n' "$PROJECT_ROOT" "$value"
      ;;
    *)
      printf '%s/features/vanessa/%s\n' "$PROJECT_ROOT" "$value"
      ;;
  esac
}

load_features() {
  local manifest="${ONEC_BDD_MANIFEST:-}"
  local raw_features="${ONEC_BDD_FEATURES:-${ONEC_BDD_FEATURE:-}}"
  local line=""

  if [ -z "$manifest" ]; then
    manifest="$(profile_string '.capabilities.bdd.manifestPath // empty')"
  fi
  if [ -z "$raw_features" ]; then
    raw_features="$(profile_jq_raw '.capabilities.bdd.featurePaths // [] | if type == "array" then join("\n") else "" end')"
  fi

  if [ -z "$manifest" ] && [ -z "$raw_features" ]; then
    printf 'BDD feature selection is required: set ONEC_BDD_MANIFEST, ONEC_BDD_FEATURES, capabilities.bdd.manifestPath, or capabilities.bdd.featurePaths\n' >&2
    exit 2
  fi

  if [ -n "$manifest" ]; then
    manifest="$(resolve_feature_path "$manifest")"
    [ -f "$manifest" ] || { printf 'BDD manifest not found: %s\n' "$manifest" >&2; exit 2; }
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line%$'\r'}"
      case "$line" in
        ""|\#*) continue ;;
      esac
      resolve_feature_path "$line"
    done <"$manifest"
    return 0
  fi

  printf '%s\n' "$raw_features" | tr ',' '\n' | while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      ""|\#*) continue ;;
    esac
    resolve_feature_path "$line"
  done
}

ensure_warm_service_ready() {
  "$PROJECT_ROOT/scripts/test/run-bdd-warm-service.sh" status \
    --profile "$PROFILE_PATH" \
    --target "$TARGET_ID" \
    --run-root "$RUN_ROOT/warm-service/status" >/dev/null

  if jq -e '.service.state == "ready"' "$RUN_ROOT/warm-service/status/summary.json" >/dev/null; then
    return 0
  fi

  "$PROJECT_ROOT/scripts/test/run-bdd-warm-service.sh" up \
    --profile "$PROFILE_PATH" \
    --target "$TARGET_ID" \
    --run-root "$RUN_ROOT/warm-service/up" >/dev/null
}

load_service_paths() {
  local status_summary="$RUN_ROOT/warm-service/status/summary.json"
  local state_json=""

  "$PROJECT_ROOT/scripts/test/run-bdd-warm-service.sh" status \
    --profile "$PROFILE_PATH" \
    --target "$TARGET_ID" \
    --run-root "$RUN_ROOT/warm-service/status" >/dev/null

  jq -e '.service.state == "ready"' "$status_summary" >/dev/null || {
    printf 'BDD warm service is not ready\n' >&2
    cat "$status_summary" >&2
    exit 65
  }

  state_json="$(jq -r '.service.state_json' "$status_summary")"
  jq -r '.service_files.feature_runtime // empty' "$state_json" >/dev/null 2>&1 || true
  SERVICE_STATE_JSON="$state_json"
  SERVICE_CONFIG="$(jq -r '.service_files.config' "$state_json")"
  REQUEST_FILE="$(jq -r '.service_files.request' "$state_json")"
  RESPONSE_FILE="$(jq -r '.service_files.response' "$state_json")"
  ERROR_FILE="$(jq -r '.service_files.error' "$state_json")"
  READY_FILE="$(jq -r '.service_files.ready' "$state_json")"
  BUILD_STATUS_FILE="$(jq -r '.service_files.build_status' "$state_json")"
  VANESSA_ONLINE_FILE="$(jq -r '.service_files.vanessa_online' "$state_json")"
  FEATURE_RUNTIME_FILE="$(sed -n 's/^FeatureRuntimePath=//p' "$SERVICE_CONFIG")"
  TEST_CLIENT_PORT="$(jq -r '.roles.test_client.port' "$state_json")"
}

run_feature() {
  local feature_path="$1"
  local index="$2"
  local feature_name=""
  local archive_dir=""
  local deadline=0
  local response=""

  [ -f "$feature_path" ] || { printf 'BDD feature not found: %s\n' "$feature_path" >&2; return 2; }

  feature_name="$(basename "$feature_path")"
  archive_dir="$RUN_ROOT/features/$(printf '%03d' "$index")"
  mkdir -p "$archive_dir"

  cp "$feature_path" "$FEATURE_RUNTIME_FILE"
  sed -i "s/__ONEC_TESTCLIENT_PORT__/$TEST_CLIENT_PORT/g" "$FEATURE_RUNTIME_FILE"
  : >"$RESPONSE_FILE"
  : >"$ERROR_FILE"
  : >"$BUILD_STATUS_FILE"
  printf 'RUN\n' >"$REQUEST_FILE"

  deadline=$((SECONDS + TIMEOUT_SECONDS))
  while [ "$SECONDS" -lt "$deadline" ]; do
    response="$(read_service_token "$RESPONSE_FILE")"
    case "$response" in
      OK)
        cp "$VANESSA_ONLINE_FILE" "$archive_dir/vanessa-online.log" 2>/dev/null || true
        printf '%s\tOK\t%s\n' "$index" "$feature_path" >>"$RUN_ROOT/results.tsv"
        return 0
        ;;
      ERROR)
        cp "$VANESSA_ONLINE_FILE" "$archive_dir/vanessa-online.log" 2>/dev/null || true
        cp "$ERROR_FILE" "$archive_dir/error.txt" 2>/dev/null || true
        printf '%s\tERROR\t%s\n' "$index" "$feature_path" >>"$RUN_ROOT/results.tsv"
        return 1
        ;;
    esac
    if [ "$(read_service_token "$READY_FILE")" = "READY" ] && [ -s "$BUILD_STATUS_FILE" ]; then
      response="$(read_service_token "$BUILD_STATUS_FILE")"
      if [ "$response" = "0" ]; then
        cp "$VANESSA_ONLINE_FILE" "$archive_dir/vanessa-online.log" 2>/dev/null || true
        printf '%s\tOK\t%s\n' "$index" "$feature_path" >>"$RUN_ROOT/results.tsv"
        return 0
      fi
    fi
    sleep 1
  done

  printf '%s\tTIMEOUT\t%s\n' "$index" "$feature_path" >>"$RUN_ROOT/results.tsv"
  return 124
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local features_json=""

  features_json="$(cut -f3- "$RUN_ROOT/results.tsv" 2>/dev/null | json_escape_array)"
  jq -n \
    --arg status "$status" \
    --arg target "$TARGET_ID" \
    --arg run_root "$RUN_ROOT" \
    --arg state_json "${SERVICE_STATE_JSON:-}" \
    --arg results "$RUN_ROOT/results.tsv" \
    --argjson exit_code "$exit_code" \
    --argjson features "$features_json" \
    '{
      status: $status,
      exit_code: $exit_code,
      contour: {id: "bdd", runner: "bdd-warm-run"},
      runtime_profile: {target: $target},
      run_root: $run_root,
      warm_service: {state_json: (if $state_json == "" then null else $state_json end)},
      features: $features,
      artifacts: {results_tsv: $results}
    }' >"$RUN_ROOT/bdd-warm-run-summary.json"
}

mapfile -t FEATURES < <(load_features)
[ "${#FEATURES[@]}" -gt 0 ] || { printf 'No BDD features selected\n' >&2; exit 2; }

: >"$RUN_ROOT/results.tsv"
ensure_warm_service_ready
load_service_paths

exit_code=0
for i in "${!FEATURES[@]}"; do
  if run_feature "${FEATURES[$i]}" "$((i + 1))"; then
    :
  else
    exit_code=$?
    break
  fi
done

if [ "$exit_code" -eq 0 ]; then
  write_summary "success" 0
else
  write_summary "failed" "$exit_code"
fi
exit "$exit_code"
