#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"
# shellcheck source=../lib/onec.sh
source "$SCRIPT_DIR/../lib/onec.sh"

LOAD_TASK_SELECTED_COMMITS=()
LOAD_TASK_SELECTED_FILES=()
LOAD_TASK_IGNORED_FILES=()
LOAD_TASK_DELETED_PATHS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/platform/load-task-src.sh [options]

Options:
  --profile <file>      Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>      Directory for summary.json and command logs
  --bead <id>           Select committed changes by commit trailer Bead:
  --work-item <id>      Select committed changes by commit trailer Work-Item:
  --range <revset>      Explicit git revset fallback
  --dry-run             Resolve selection and delegated load-src dry-run only
  -h, --help            Show this help
EOF
}

append_load_task_selected_file() {
  local value="$1"
  local existing=""
  local -n out_ref="$2"

  for existing in "${out_ref[@]}"; do
    if [ "$existing" = "$value" ]; then
      return 0
    fi
  done

  out_ref+=("$value")
}

append_load_task_object() {
  local entry="$1"
  local existing=""
  local -n out_ref="$2"

  for existing in "${out_ref[@]}"; do
    if [ "$existing" = "$entry" ]; then
      return 0
    fi
  done

  out_ref+=("$entry")
}

append_load_task_ignored_file() {
  local path="$1"
  local reason="$2"
  local commit="$3"
  local entry=""

  entry="$(jq -cn --arg path "$path" --arg reason "$reason" --arg commit "$commit" '{path: $path, reason: $reason, commit: $commit}')"
  append_load_task_object "$entry" LOAD_TASK_IGNORED_FILES
}

append_load_task_deleted_path() {
  local path="$1"
  local commit="$2"
  local entry=""

  entry="$(jq -cn --arg path "$path" --arg commit "$commit" '{path: $path, commit: $commit}')"
  append_load_task_object "$entry" LOAD_TASK_DELETED_PATHS
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

join_load_task_selected_files() {
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

build_load_task_selection_json() {
  local source_dir="$1"
  local selector_mode="$2"
  local selector_value="$3"
  local selected_commits_json=""
  local selected_files_json=""
  local ignored_files_json=""
  local deleted_paths_json=""
  local selection_error="${4:-}"

  selected_commits_json="$(json_array_from_strings LOAD_TASK_SELECTED_COMMITS)"
  selected_files_json="$(json_array_from_strings LOAD_TASK_SELECTED_FILES)"
  ignored_files_json="$(json_array_from_objects LOAD_TASK_IGNORED_FILES)"
  deleted_paths_json="$(json_array_from_objects LOAD_TASK_DELETED_PATHS)"

  jq -cn \
    --arg source_dir "$source_dir" \
    --arg selector_mode "$selector_mode" \
    --arg selector_value "$selector_value" \
    --arg selection_error "$selection_error" \
    --argjson selected_commits "$selected_commits_json" \
    --argjson selected_files "$selected_files_json" \
    --argjson ignored_files "$ignored_files_json" \
    --argjson deleted_paths "$deleted_paths_json" \
    '{
      selection: {
        source_dir: $source_dir,
        selector: {
          mode: $selector_mode,
          value: $selector_value
        },
        selected_commits: $selected_commits,
        selected_files: $selected_files,
        ignored_files: $ignored_files,
        deleted_paths: $deleted_paths,
        error: (if $selection_error == "" then null else $selection_error end)
      }
    }'
}

build_load_task_delegated_json() {
  local delegated_summary_path="${1:-}"
  local delegated_run_root="${2:-}"

  if [ -z "$delegated_summary_path" ] || [ -z "$delegated_run_root" ]; then
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

classify_load_task_path() {
  local repo_root="$1"
  local source_dir_rel="$2"
  local repo_path="$3"
  local commit="$4"
  local absolute_path=""
  local source_relative=""

  repo_path="$(normalize_capability_selected_file "$repo_path")"

  if [[ "$repo_path" != "$source_dir_rel" && "$repo_path" != "$source_dir_rel/"* ]]; then
    append_load_task_ignored_file "$repo_path" "outside-source-tree" "$commit"
    return 0
  fi

  absolute_path="$repo_root/$repo_path"
  if [ ! -f "$absolute_path" ]; then
    append_load_task_ignored_file "$repo_path" "missing-or-deleted" "$commit"
    return 0
  fi

  source_relative="${repo_path#"$source_dir_rel"/}"
  if [ "$source_relative" = "$repo_path" ] || [ -z "$source_relative" ]; then
    append_load_task_ignored_file "$repo_path" "not-a-source-file" "$commit"
    return 0
  fi

  append_load_task_selected_file "$source_relative" LOAD_TASK_SELECTED_FILES
}

collect_load_task_paths_for_commit() {
  local repo_root="$1"
  local source_dir_rel="$2"
  local commit="$3"
  local line=""
  local status=""
  local status_class=""
  local first_path=""
  local second_path=""
  local repo_path=""

  while IFS= read -r line; do
    [ -n "$line" ] || continue
    IFS=$'\t' read -r status first_path second_path <<<"$line"
    status_class="${status%%[0-9]*}"

    case "$status_class" in
      D)
        repo_path="$(normalize_capability_selected_file "$first_path")"
        if [[ "$repo_path" != "$source_dir_rel" && "$repo_path" != "$source_dir_rel/"* ]]; then
          append_load_task_ignored_file "$repo_path" "outside-source-tree" "$commit"
        else
          append_load_task_deleted_path "$repo_path" "$commit"
        fi
        ;;
      R|C)
        classify_load_task_path "$repo_root" "$source_dir_rel" "$second_path" "$commit"
        ;;
      *)
        classify_load_task_path "$repo_root" "$source_dir_rel" "$first_path" "$commit"
        ;;
    esac
  done < <(git -C "$repo_root" diff-tree --no-commit-id --root --name-status -r "$commit")
}

if capability_help_requested "$@"; then
  usage
  exit 0
fi

profile_input=""
run_root_input=""
dry_run="${DRY_RUN:-0}"
selector_mode=""
selector_value=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      [ "$#" -ge 2 ] || die "--profile requires a value"
      profile_input="$2"
      shift 2
      ;;
    --run-root)
      [ "$#" -ge 2 ] || die "--run-root requires a value"
      run_root_input="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --bead)
      [ "$#" -ge 2 ] || die "--bead requires a value"
      [ -z "$selector_mode" ] || die "load-task-src requires exactly one selector"
      selector_mode="bead"
      selector_value="$2"
      shift 2
      ;;
    --work-item)
      [ "$#" -ge 2 ] || die "--work-item requires a value"
      [ -z "$selector_mode" ] || die "load-task-src requires exactly one selector"
      selector_mode="work-item"
      selector_value="$2"
      shift 2
      ;;
    --range)
      [ "$#" -ge 2 ] || die "--range requires a value"
      [ -z "$selector_mode" ] || die "load-task-src requires exactly one selector"
      selector_mode="range"
      selector_value="$2"
      shift 2
      ;;
    --files)
      die "load-task-src derives file selection internally; --files is not supported"
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

[ -n "$selector_mode" ] || die "load-task-src requires one of --bead, --work-item, or --range"

require_command git
require_command jq

root="$(project_root)"
profile_path="$(resolve_runtime_profile_path "$profile_input" "$root")"
load_runtime_profile "$profile_path"
require_runtime_profile_loaded

adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
run_root="$(prepare_capability_run_root "load-task-src" "$run_root_input")"
summary_path="$(capability_summary_path "$run_root")"
stdout_log="$run_root/stdout.log"
stderr_log="$run_root/stderr.log"
: >"$stdout_log"
: >"$stderr_log"

source_dir="$(capability_string_or_default "load-src" "sourceDir" "./src/cf")"
source_dir_rel="$(normalize_capability_selected_file "$source_dir")"
selected_files_csv=""
selection_json=""
delegated_json='{"delegated":null}'
base_context_json="$(build_redacted_context_json)"
context_json="{}"
status="success"
exit_code=0
driver=""
delegated_run_root="$run_root/load-src"
delegated_summary_path=""
selection_error=""
selection_output=""
selection_stderr_tmp=""
task_trailer_helper="$root/scripts/git/task-trailers.sh"

log "Load task-scoped source changes"
log "adapter=$adapter"
log "profile=$profile_path"
log "run_root=$run_root"
printf 'source_dir=%s\n' "$source_dir" >>"$stdout_log"
printf 'selector_mode=%s\n' "$selector_mode" >>"$stdout_log"
printf 'selector_value=%s\n' "$selector_value" >>"$stdout_log"

started_at="$(timestamp_utc)"
selection_stderr_tmp="$(mktemp)"

if selection_output="$("$task_trailer_helper" select-commits --repo "$root" "--$selector_mode" "$selector_value" 2>"$selection_stderr_tmp")"; then
  if [ -n "$selection_output" ]; then
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      LOAD_TASK_SELECTED_COMMITS+=("$line")
    done <<<"$selection_output"
  fi
else
  status="failed"
  exit_code=66
  selection_error="$(<"$selection_stderr_tmp")"
  printf '%s\n' "$selection_error" >>"$stderr_log"
fi
rm -f "$selection_stderr_tmp"

if [ "$status" != "failed" ] && [ "${LOAD_TASK_SELECTED_COMMITS[0]+set}" != "set" ]; then
  status="failed"
  exit_code=65
  selection_error="no commits matched selector"
  printf 'error: %s\n' "$selection_error" | tee -a "$stderr_log" >&2
fi

if [ "$status" != "failed" ]; then
  for commit in "${LOAD_TASK_SELECTED_COMMITS[@]}"; do
    collect_load_task_paths_for_commit "$root" "$source_dir_rel" "$commit"
  done
fi

if [ "$status" != "failed" ] && [ "${LOAD_TASK_SELECTED_FILES[0]+set}" != "set" ]; then
  status="failed"
  exit_code=65
  selection_error="no eligible committed files inside source tree"
  printf 'error: %s\n' "$selection_error" | tee -a "$stderr_log" >&2
fi

selected_files_csv="$(join_load_task_selected_files LOAD_TASK_SELECTED_FILES)"
selection_json="$(build_load_task_selection_json "$source_dir" "$selector_mode" "$selector_value" "$selection_error")"

if [ "$status" != "failed" ]; then
  delegate_cmd=("$root/scripts/platform/load-src.sh" "--profile" "$profile_path" "--run-root" "$delegated_run_root" "--files" "$selected_files_csv")
  if [ "$dry_run" = "1" ]; then
    delegate_cmd+=("--dry-run")
  fi

  if "${delegate_cmd[@]}" >>"$stdout_log" 2>>"$stderr_log"; then
    if [ "$dry_run" = "1" ]; then
      status="dry-run"
    fi
  else
    exit_code=$?
    status="failed"
  fi

  delegated_summary_path="$delegated_run_root/summary.json"
  delegated_json="$(build_load_task_delegated_json "$delegated_summary_path" "$delegated_run_root")"
  if [ -f "$delegated_summary_path" ]; then
    driver="$(jq -r '.driver // empty' "$delegated_summary_path")"
  fi
fi

finished_at="$(timestamp_utc)"
context_json="$(jq -cs 'reduce .[] as $item ({}; . * $item)' <<<"$base_context_json
$selection_json
$delegated_json")"

write_capability_summary \
  "$summary_path" \
  "$status" \
  "load-task-src" \
  "Load task-scoped source changes" \
  "$adapter" \
  "$driver" \
  "$profile_path" \
  "$run_root" \
  "$exit_code" \
  "$started_at" \
  "$finished_at" \
  "$stdout_log" \
  "$stderr_log" \
  "$dry_run" \
  "git-task-to-load-src" \
  "delegated-script" \
  "$context_json"

log "summary_json=$summary_path"

if [ "$status" = "failed" ]; then
  exit "$exit_code"
fi
