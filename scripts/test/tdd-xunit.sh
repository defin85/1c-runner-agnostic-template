#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

PROFILE_INPUT=""
RUN_ROOT_INPUT=""

usage() {
  cat <<'EOF'
Usage: ./scripts/test/tdd-xunit.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>   Directory for wrapper summary and delegated run roots
  -h, --help         Show this help
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

resolve_profile_path() {
  local resolved=""

  resolved="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
  [ -n "$resolved" ] || fail "runtime profile is required"
  printf '%s\n' "$(canonical_path "$resolved")"
}

resolve_run_root() {
  local resolved=""

  if [ -n "$RUN_ROOT_INPUT" ]; then
    resolved="$(canonical_path "$RUN_ROOT_INPUT")"
    mkdir -p "$resolved"
    printf '%s\n' "$resolved"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/1c-tdd-xunit.XXXXXX"
}

resolve_git_base_ref() {
  if git -C "$PROJECT_ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
    printf 'HEAD\n'
    return 0
  fi

  git -C "$PROJECT_ROOT" hash-object -t tree /dev/null
}

json_array_from_lines() {
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  printf '%s\n' "$@" | jq -R . | jq -s .
}

collect_cf_delta() {
  local base_ref="$1"
  local line=""

  CF_CHANGE_LINES=()
  mapfile -t GIT_DIFF_LINES < <(git -C "$PROJECT_ROOT" diff --name-status "$base_ref" -- src/cf)
  mapfile -t GIT_UNTRACKED_LINES < <(git -C "$PROJECT_ROOT" ls-files --others --exclude-standard -- src/cf)

  for line in "${GIT_DIFF_LINES[@]}"; do
    [ -n "$line" ] || continue
    CF_CHANGE_LINES+=("$line")
  done

  for line in "${GIT_UNTRACKED_LINES[@]}"; do
    [ -n "$line" ] || continue
    CF_CHANGE_LINES+=("??	$line")
  done
}

classify_cf_delta() {
  local line=""
  local kind=""

  SYNC_REQUIRED=false
  UNSUPPORTED_CF_LINES=()

  if [ "$(array_length CF_CHANGE_LINES)" -eq 0 ]; then
    return 0
  fi

  for line in "${CF_CHANGE_LINES[@]}"; do
    kind="${line%%$'\t'*}"
    case "$kind" in
      A|M|??)
        SYNC_REQUIRED=true
        ;;
      *)
        UNSUPPORTED_CF_LINES+=("$line")
        ;;
    esac
  done

  if [ "$(array_length UNSUPPORTED_CF_LINES)" -gt 0 ]; then
    SYNC_REQUIRED=false
    return 1
  fi

  return 0
}

write_summary() {
  local status="$1"
  local exit_code="$2"
  local sync_action="$3"
  local message="$4"
  local started_at="$5"
  local finished_at="$6"
  local cf_changes_json=""
  local unsupported_json=""

  cf_changes_json="$(json_array_from_lines "${CF_CHANGE_LINES[@]}")"
  unsupported_json="$(json_array_from_lines "${UNSUPPORTED_CF_LINES[@]}")"

  jq -n \
    --arg status "$status" \
    --arg profile_path "$PROFILE_PATH" \
    --arg run_root "$RUN_ROOT" \
    --arg sync_action "$sync_action" \
    --arg message "$message" \
    --arg started_at "$started_at" \
    --arg finished_at "$finished_at" \
    --arg load_diff_run_root "$LOAD_DIFF_RUN_ROOT" \
    --arg update_db_run_root "$UPDATE_DB_RUN_ROOT" \
    --arg xunit_run_root "$XUNIT_RUN_ROOT" \
    --argjson sync_required "$SYNC_REQUIRED" \
    --argjson exit_code "$exit_code" \
    --argjson cf_changes "$cf_changes_json" \
    --argjson unsupported_cf_changes "$unsupported_json" \
    '{
      status: $status,
      profile_path: $profile_path,
      run_root: $run_root,
      started_at: $started_at,
      finished_at: $finished_at,
      exit_code: $exit_code,
      sync: {
        required: $sync_required,
        action: $sync_action,
        cf_changes: $cf_changes,
        unsupported_cf_changes: $unsupported_cf_changes,
        message: (if $message == "" then null else $message end)
      },
      delegated: {
        load_diff_run_root: (if $load_diff_run_root == "" then null else $load_diff_run_root end),
        update_db_run_root: (if $update_db_run_root == "" then null else $update_db_run_root end),
        xunit_run_root: (if $xunit_run_root == "" then null else $xunit_run_root end)
      }
    }' > "$RUN_ROOT/summary.json"
}

run_phase() {
  local name="$1"
  shift

  log "$name"
  if "$@"; then
    return 0
  fi

  PHASE_EXIT_CODE=$?
  PHASE_ERROR="$name failed"
  return "$PHASE_EXIT_CODE"
}

if [[ "${1:-}" = "-h" || "${1:-}" = "--help" ]]; then
  usage
  exit 0
fi

parse_args "$@"

require_command git
require_command jq

PROFILE_PATH="$(resolve_profile_path)"
RUN_ROOT="$(resolve_run_root)"
LOAD_DIFF_RUN_ROOT="$RUN_ROOT/load-diff-src"
UPDATE_DB_RUN_ROOT="$RUN_ROOT/update-db"
XUNIT_RUN_ROOT="$RUN_ROOT/xunit"
started_at="$(timestamp_utc)"
SYNC_REQUIRED=false
CF_CHANGE_LINES=()
UNSUPPORTED_CF_LINES=()
PHASE_EXIT_CODE=0
PHASE_ERROR=""

git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "tdd-xunit requires a git worktree"

collect_cf_delta "$(resolve_git_base_ref)"
if ! classify_cf_delta; then
  message="tdd-xunit supports only added, modified, or untracked files under src/cf; for delete/rename/conflict changes use ./scripts/platform/load-src.sh -> ./scripts/platform/update-db.sh -> ./scripts/test/run-xunit.sh manually"
  printf 'error: %s\n' "$message" >&2
  if [ "$(array_length UNSUPPORTED_CF_LINES)" -gt 0 ]; then
    printf 'unsupported src/cf delta:\n' >&2
    printf '  %s\n' "${UNSUPPORTED_CF_LINES[@]}" >&2
  fi
  finished_at="$(timestamp_utc)"
  write_summary "failed" 65 "unsupported-delta-shape" "$message" "$started_at" "$finished_at"
  exit 65
fi

if [ "$SYNC_REQUIRED" = true ]; then
  if ! run_phase "Load git-backed src/cf diff" \
    "$PROJECT_ROOT/scripts/platform/load-diff-src.sh" \
    --profile "$PROFILE_PATH" \
    --run-root "$LOAD_DIFF_RUN_ROOT"; then
    finished_at="$(timestamp_utc)"
    write_summary "failed" "$PHASE_EXIT_CODE" "load-diff-src-failed" "$PHASE_ERROR" "$started_at" "$finished_at"
    exit "$PHASE_EXIT_CODE"
  fi

  if ! run_phase "Update DB configuration" \
    "$PROJECT_ROOT/scripts/platform/update-db.sh" \
    --profile "$PROFILE_PATH" \
    --run-root "$UPDATE_DB_RUN_ROOT"; then
    finished_at="$(timestamp_utc)"
    write_summary "failed" "$PHASE_EXIT_CODE" "update-db-failed" "$PHASE_ERROR" "$started_at" "$finished_at"
    exit "$PHASE_EXIT_CODE"
  fi

  SYNC_ACTION="load-diff-src-and-update-db"
else
  SYNC_ACTION="skip-clean-src-cf"
fi

if ! run_phase "Run xUnit contour" \
  "$PROJECT_ROOT/scripts/test/run-xunit.sh" \
  --profile "$PROFILE_PATH" \
  --run-root "$XUNIT_RUN_ROOT"; then
  finished_at="$(timestamp_utc)"
  write_summary "failed" "$PHASE_EXIT_CODE" "xunit-failed" "$PHASE_ERROR" "$started_at" "$finished_at"
  exit "$PHASE_EXIT_CODE"
fi

finished_at="$(timestamp_utc)"
write_summary "success" 0 "$SYNC_ACTION" "" "$started_at" "$finished_at"
