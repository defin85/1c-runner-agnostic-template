#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

LOAD_DIFF_RAW_PATHS=()
LOAD_DIFF_SELECTED_FILES=()
LOAD_DIFF_IGNORED_FILES=()

LOAD_DIFF_BOOTSTRAP_ERROR=""

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/load-diff-src.sh [options]

Options:
  --profile <file>   Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>   Directory for summary.json and command logs
  --dry-run          Resolve diff selection and delegated load-src dry-run only
  -h, --help         Show this help
EOF
}

append_load_diff_raw_path() {
  local path="$1"
  local array_name="$2"
  local -n out_ref="$array_name"
  local existing=""

  for existing in "${out_ref[@]}"; do
    if [ "$existing" = "$path" ]; then
      return 0
    fi
  done

  out_ref+=("$path")
}

resolve_load_diff_base_ref() {
  local repo_root="$1"

  if git -C "$repo_root" rev-parse --verify HEAD >/dev/null 2>&1; then
    printf 'HEAD\n'
    return 0
  fi

  git -C "$repo_root" hash-object -t tree /dev/null
}

collect_load_diff_raw_paths() {
  local repo_root="$1"
  local base_ref="$2"
  local array_name="$3"
  local path=""
  local -a tracked_paths=()
  local -a untracked_paths=()
  local -n out_ref="$array_name"

  out_ref=()

  mapfile -t tracked_paths < <(git_with_unquoted_paths -C "$repo_root" diff --name-only "$base_ref" -- .)
  mapfile -t untracked_paths < <(git_with_unquoted_paths -C "$repo_root" ls-files --others --exclude-standard -- .)

  for path in "${tracked_paths[@]}"; do
    [ -n "$path" ] || continue
    append_load_diff_raw_path "$path" "$array_name"
  done

  for path in "${untracked_paths[@]}"; do
    [ -n "$path" ] || continue
    append_load_diff_raw_path "$path" "$array_name"
  done
}

append_load_diff_ignored_file() {
  local path="$1"
  local reason="$2"
  local array_name="$3"
  local entry=""
  local -n out_ref="$array_name"

  entry="$(jq -cn --arg path "$path" --arg reason "$reason" '{path: $path, reason: $reason}')"
  out_ref+=("$entry")
}

classify_load_diff_paths() {
  local repo_root="$1"
  local source_dir_rel="$2"
  local raw_paths_name="$3"
  local selected_name="$4"
  local ignored_name="$5"
  local repo_path=""
  local source_relative=""
  local absolute_path=""
  local existing=""
  local -n raw_paths_ref="$raw_paths_name"
  local -n selected_ref="$selected_name"
  local -n ignored_ref="$ignored_name"

  selected_ref=()
  ignored_ref=()

  for repo_path in "${raw_paths_ref[@]}"; do
    repo_path="$(normalize_capability_selected_file "$repo_path")"

    if [[ "$repo_path" != "$source_dir_rel" && "$repo_path" != "$source_dir_rel/"* ]]; then
      append_load_diff_ignored_file "$repo_path" "outside-source-tree" "$ignored_name"
      continue
    fi

    absolute_path="$repo_root/$repo_path"
    if [ ! -f "$absolute_path" ]; then
      append_load_diff_ignored_file "$repo_path" "missing-or-deleted" "$ignored_name"
      continue
    fi

    source_relative="${repo_path#"$source_dir_rel"/}"
    if [ "$source_relative" = "$repo_path" ] || [ -z "$source_relative" ]; then
      append_load_diff_ignored_file "$repo_path" "not-a-source-file" "$ignored_name"
      continue
    fi

    for existing in "${selected_ref[@]}"; do
      if [ "$existing" = "$source_relative" ]; then
        continue 2
      fi
    done

    selected_ref+=("$source_relative")
  done
}

json_array_from_strings() {
  local array_name="$1"
  local item=""
  local -n source_ref="$array_name"

  if [ "${source_ref[0]+set}" != "set" ]; then
    printf '[]\n'
    return 0
  fi

  {
    for item in "${source_ref[@]}"; do
      printf '%s\n' "$item"
    done
  } | jq -R . | jq -s .
}

json_array_from_objects() {
  local array_name="$1"
  local item=""
  local -n source_ref="$array_name"

  if [ "${source_ref[0]+set}" != "set" ]; then
    printf '[]\n'
    return 0
  fi

  {
    for item in "${source_ref[@]}"; do
      printf '%s\n' "$item"
    done
  } | jq -s .
}

join_load_diff_selected_files() {
  local array_name="$1"
  local item=""
  local result=""
  local -n source_ref="$array_name"

  for item in "${source_ref[@]}"; do
    if [ -n "$result" ]; then
      result+=","
    fi
    result+="$item"
  done

  printf '%s\n' "$result"
}

build_load_diff_selection_json() {
  local source_dir="$1"
  local base_ref="$2"
  local selection_error="$3"
  local selected_name="$4"
  local ignored_name="$5"
  local selected_json=""
  local ignored_json=""

  selected_json="$(json_array_from_strings "$selected_name")"
  ignored_json="$(json_array_from_objects "$ignored_name")"

  jq -cn \
    --arg source_dir "$source_dir" \
    --arg base_ref "$base_ref" \
    --arg selection_error "$selection_error" \
    --argjson selected_files "$selected_json" \
    --argjson ignored_files "$ignored_json" \
    '{
      selection: {
        source_dir: $source_dir,
        base_ref: (if $base_ref == "" then null else $base_ref end),
        selected_files: $selected_files,
        ignored_files: $ignored_files,
        error: (if $selection_error == "" then null else $selection_error end)
      }
    }'
}

build_load_diff_delegated_json() {
  local delegated_summary_path="${1:-}"
  local delegated_run_root="${2:-}"

  if [ -z "$delegated_run_root" ]; then
    printf '{"delegated":null}\n'
    return 0
  fi

  jq -n \
    --arg delegated_run_root "$delegated_run_root" \
    --arg delegated_summary_path "$delegated_summary_path" \
    --arg delegated_stdout "$delegated_run_root/stdout.log" \
    --arg delegated_stderr "$delegated_run_root/stderr.log" \
    '{
      delegated: {
        capability: "load-src",
        run_root: $delegated_run_root,
        summary_json: $delegated_summary_path,
        stdout_log: $delegated_stdout,
        stderr_log: $delegated_stderr
      }
    }'
}

json_escape_load_diff() {
  local value="${1-}"

  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

json_bool_load_diff() {
  case "${1:-0}" in
    1|true)
      printf 'true'
      ;;
    *)
      printf 'false'
      ;;
  esac
}

json_string_or_null_load_diff() {
  local value="${1-}"

  if [ -z "$value" ]; then
    printf 'null'
    return 0
  fi

  printf '"%s"' "$(json_escape_load_diff "$value")"
}

write_load_diff_bootstrap_summary() {
  local summary_path="$1"
  local status="$2"
  local adapter="$3"
  local profile_path="$4"
  local run_root="$5"
  local exit_code="$6"
  local started_at="$7"
  local finished_at="$8"
  local stdout_log="$9"
  local stderr_log="${10}"
  local dry_run="${11}"
  local error_message="${12}"
  local summary_dir=""

  summary_dir="${summary_path%/*}"
  if [ "$summary_dir" = "$summary_path" ]; then
    summary_dir="."
  fi
  mkdir -p "$summary_dir"

  {
    printf '{\n'
    printf '  "status": "%s",\n' "$(json_escape_load_diff "$status")"
    printf '  "capability": {\n'
    printf '    "id": "load-diff-src",\n'
    printf '    "label": "Load source diff"\n'
    printf '  },\n'
    printf '  "adapter": %s,\n' "$(json_string_or_null_load_diff "$adapter")"
    printf '  "driver": null,\n'
    printf '  "profile_path": %s,\n' "$(json_string_or_null_load_diff "$profile_path")"
    printf '  "run_root": "%s",\n' "$(json_escape_load_diff "$run_root")"
    printf '  "started_at": "%s",\n' "$(json_escape_load_diff "$started_at")"
    printf '  "finished_at": "%s",\n' "$(json_escape_load_diff "$finished_at")"
    printf '  "exit_code": %s,\n' "$exit_code"
    printf '  "dry_run": %s,\n' "$(json_bool_load_diff "$dry_run")"
    printf '  "execution": {\n'
    printf '    "source": "git-diff-to-load-src",\n'
    printf '    "executor": "delegated-script"\n'
    printf '  },\n'
    printf '  "artifacts": {\n'
    printf '    "summary_json": "%s",\n' "$(json_escape_load_diff "$summary_path")"
    printf '    "stdout_log": "%s",\n' "$(json_escape_load_diff "$stdout_log")"
    printf '    "stderr_log": "%s"\n' "$(json_escape_load_diff "$stderr_log")"
    printf '  },\n'
    printf '  "selection": {\n'
    printf '    "source_dir": null,\n'
    printf '    "base_ref": null,\n'
    printf '    "selected_files": [],\n'
    printf '    "ignored_files": [],\n'
    printf '    "error": %s\n' "$(json_string_or_null_load_diff "$error_message")"
    printf '  },\n'
    printf '  "delegated": null\n'
    printf '}\n'
  } >"$summary_path"
}

probe_load_diff_bootstrap() {
  local root="$1"
  local profile_path="$2"

  if capability_selected_files_requested; then
    die "load-diff-src derives file selection internally; --files is not supported"
  fi

  require_command git
  require_command jq
  load_runtime_profile "$profile_path"
  require_runtime_profile_loaded
  printf 'bootstrap-ok\n'
}

capture_load_diff_bootstrap_error() {
  local probe_stderr_path="$1"
  local line=""

  LOAD_DIFF_BOOTSTRAP_ERROR=""
  while IFS= read -r line || [ -n "$line" ]; do
    if [ -n "$line" ]; then
      LOAD_DIFF_BOOTSTRAP_ERROR="$line"
      printf '%s\n' "$line" >>"$stderr_log"
    fi
  done <"$probe_stderr_path"

  LOAD_DIFF_BOOTSTRAP_ERROR="${LOAD_DIFF_BOOTSTRAP_ERROR#error: }"
  if [ -z "$LOAD_DIFF_BOOTSTRAP_ERROR" ]; then
    LOAD_DIFF_BOOTSTRAP_ERROR="load-diff-src bootstrap failed"
  fi
}

fail_load_diff_bootstrap() {
  local error_message="$1"
  local profile_path="$2"
  local exit_code="${3:-1}"
  local finished_at=""

  printf 'error: %s\n' "$error_message" >&2
  printf 'error: %s\n' "$error_message" >>"$stderr_log"
  finished_at="$(timestamp_utc)"
  write_load_diff_bootstrap_summary \
    "$summary_path" \
    "failed" \
    "${adapter-}" \
    "$profile_path" \
    "$run_root" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$stdout_log" \
    "$stderr_log" \
    "$CAPABILITY_DRY_RUN" \
    "$error_message"
  exit "$exit_code"
}

ensure_load_diff_git_worktree() {
  local repo_root="$1"
  local git_error=""

  if git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  git_error="$(git -C "$repo_root" rev-parse --is-inside-work-tree 2>&1 || true)"
  if [ -n "$git_error" ]; then
    printf '%s\n' "$git_error" >&2
  fi

  return 1
}

if capability_help_requested "$@"; then
  usage
  exit 0
fi

parse_capability_cli_args "$@"
if [ "$CAPABILITY_SHOW_HELP" = "1" ]; then
  usage
  exit 0
fi

root="$(project_root)"
run_root="$(prepare_capability_run_root "load-diff-src" "$CAPABILITY_RUN_ROOT_INPUT")"
summary_path="$(capability_summary_path "$run_root")"
stdout_log="$run_root/stdout.log"
stderr_log="$run_root/stderr.log"
: >"$stdout_log"
: >"$stderr_log"
started_at="$(timestamp_utc)"

profile_path="$(resolve_runtime_profile_path "$CAPABILITY_PROFILE_INPUT" "$root")"
bootstrap_probe_stderr="$run_root/bootstrap-probe.stderr"
: >"$bootstrap_probe_stderr"
if ! (probe_load_diff_bootstrap "$root" "$profile_path") >/dev/null 2>"$bootstrap_probe_stderr"; then
  capture_load_diff_bootstrap_error "$bootstrap_probe_stderr"
  fail_load_diff_bootstrap "$LOAD_DIFF_BOOTSTRAP_ERROR" "$profile_path"
fi
rm -f "$bootstrap_probe_stderr"

require_command git
require_command jq
load_runtime_profile "$profile_path"
require_runtime_profile_loaded

adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"

source_dir="$(capability_string_or_default "load-src" "sourceDir" "./src/cf")"
source_dir_rel="$(normalize_capability_selected_file "$source_dir")"
base_ref=""
selection_error=""

if ensure_load_diff_git_worktree "$root" 2>>"$stderr_log"; then
  base_ref="$(resolve_load_diff_base_ref "$root")"
  collect_load_diff_raw_paths "$root" "$base_ref" LOAD_DIFF_RAW_PATHS
  classify_load_diff_paths "$root" "$source_dir_rel" LOAD_DIFF_RAW_PATHS LOAD_DIFF_SELECTED_FILES LOAD_DIFF_IGNORED_FILES
else
  selection_error="git-backed diff requires a git worktree"
fi

selected_files_csv="$(join_load_diff_selected_files LOAD_DIFF_SELECTED_FILES)"
delegated_json='{"delegated":null}'
base_context_json="$(build_redacted_context_json)"
context_json='{}'
status="success"
exit_code=0
driver=""
delegated_run_root="$run_root/load-src"
delegated_summary_path=""

log "Load source diff"
log "adapter=$adapter"
log "profile=$profile_path"
log "run_root=$run_root"
printf 'source_dir=%s\n' "$source_dir" >>"$stdout_log"
printf 'base_ref=%s\n' "$base_ref" >>"$stdout_log"
printf 'selected_files=%s\n' "$selected_files_csv" >>"$stdout_log"

if [ -n "$selection_error" ]; then
  status="failed"
  exit_code=66
  printf 'error: %s\n' "$selection_error" | tee -a "$stderr_log" >&2
elif [ "${LOAD_DIFF_SELECTED_FILES[0]+set}" != "set" ]; then
  status="failed"
  exit_code=65
  selection_error="no eligible changed files inside source tree"
  printf 'error: %s\n' "$selection_error" | tee -a "$stderr_log" >&2
else
  delegate_cmd=("$root/scripts/platform/load-src.sh" "--profile" "$profile_path" "--run-root" "$delegated_run_root" "--files" "$selected_files_csv")
  if [ "$CAPABILITY_DRY_RUN" = "1" ]; then
    delegate_cmd+=("--dry-run")
  fi

  if "${delegate_cmd[@]}" >>"$stdout_log" 2>>"$stderr_log"; then
    if [ "$CAPABILITY_DRY_RUN" = "1" ]; then
      status="dry-run"
    fi
  else
    exit_code=$?
    status="failed"
  fi

  delegated_summary_path="$delegated_run_root/summary.json"
  delegated_json="$(build_load_diff_delegated_json "$delegated_summary_path" "$delegated_run_root")"
  if [ -f "$delegated_summary_path" ]; then
    driver="$(jq -r '.driver // empty' "$delegated_summary_path")"
  fi
fi

finished_at="$(timestamp_utc)"
selection_json="$(build_load_diff_selection_json "$source_dir" "$base_ref" "$selection_error" LOAD_DIFF_SELECTED_FILES LOAD_DIFF_IGNORED_FILES)"
context_json="$(jq -cs 'reduce .[] as $item ({}; . * $item)' <<<"$base_context_json
$selection_json
$delegated_json")"

write_capability_summary \
  "$summary_path" \
  "$status" \
  "load-diff-src" \
  "Load source diff" \
  "$adapter" \
  "$driver" \
  "$profile_path" \
  "$run_root" \
  "$exit_code" \
  "$started_at" \
  "$finished_at" \
  "$stdout_log" \
  "$stderr_log" \
  "$CAPABILITY_DRY_RUN" \
  "git-diff-to-load-src" \
  "delegated-script" \
  "$context_json"

log "summary_json=$summary_path"

if [ "$status" = "failed" ]; then
  exit "$exit_code"
fi
