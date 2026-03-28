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
LOAD_TASK_BOOTSTRAP_ERROR=""

record_load_task_cli_error() {
  local message="$1"
  local exit_code="${2:-1}"
  local error_var_name="$3"
  local exit_code_var_name="$4"
  local -n error_ref="$error_var_name"
  local -n exit_code_ref="$exit_code_var_name"

  if [ -n "$error_ref" ]; then
    return 0
  fi

  error_ref="$message"
  exit_code_ref="$exit_code"
}

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

json_escape_load_task() {
  local value="${1-}"

  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

json_bool_load_task() {
  case "${1:-0}" in
    1|true)
      printf 'true'
      ;;
    *)
      printf 'false'
      ;;
  esac
}

json_string_or_null_load_task() {
  local value="${1-}"

  if [ -z "$value" ]; then
    printf 'null'
    return 0
  fi

  printf '"%s"' "$(json_escape_load_task "$value")"
}

write_load_task_bootstrap_summary() {
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
  local selector_mode="${12}"
  local selector_value="${13}"
  local error_message="${14}"
  local summary_dir=""

  summary_dir="${summary_path%/*}"
  if [ "$summary_dir" = "$summary_path" ]; then
    summary_dir="."
  fi
  mkdir -p "$summary_dir"

  {
    printf '{\n'
    printf '  "status": "%s",\n' "$(json_escape_load_task "$status")"
    printf '  "capability": {\n'
    printf '    "id": "load-task-src",\n'
    printf '    "label": "Load task-scoped source changes"\n'
    printf '  },\n'
    printf '  "adapter": %s,\n' "$(json_string_or_null_load_task "$adapter")"
    printf '  "driver": null,\n'
    printf '  "profile_path": %s,\n' "$(json_string_or_null_load_task "$profile_path")"
    printf '  "run_root": "%s",\n' "$(json_escape_load_task "$run_root")"
    printf '  "started_at": "%s",\n' "$(json_escape_load_task "$started_at")"
    printf '  "finished_at": "%s",\n' "$(json_escape_load_task "$finished_at")"
    printf '  "exit_code": %s,\n' "$exit_code"
    printf '  "dry_run": %s,\n' "$(json_bool_load_task "$dry_run")"
    printf '  "execution": {\n'
    printf '    "source": "git-task-to-load-src",\n'
    printf '    "executor": "delegated-script"\n'
    printf '  },\n'
    printf '  "artifacts": {\n'
    printf '    "summary_json": "%s",\n' "$(json_escape_load_task "$summary_path")"
    printf '    "stdout_log": "%s",\n' "$(json_escape_load_task "$stdout_log")"
    printf '    "stderr_log": "%s"\n' "$(json_escape_load_task "$stderr_log")"
    printf '  },\n'
    printf '  "selection": {\n'
    printf '    "source_dir": null,\n'
    printf '    "selector": {\n'
    printf '      "mode": %s,\n' "$(json_string_or_null_load_task "$selector_mode")"
    printf '      "value": %s\n' "$(json_string_or_null_load_task "$selector_value")"
    printf '    },\n'
    printf '    "selected_commits": [],\n'
    printf '    "selected_files": [],\n'
    printf '    "ignored_files": [],\n'
    printf '    "deleted_paths": [],\n'
    printf '    "error": %s\n' "$(json_string_or_null_load_task "$error_message")"
    printf '  },\n'
    printf '  "delegated": null\n'
    printf '}\n'
  } >"$summary_path"
}

probe_load_task_bootstrap() {
  local profile_path="$1"

  require_command git
  require_command jq
  load_runtime_profile "$profile_path"
  require_runtime_profile_loaded
  printf 'bootstrap-ok\n'
}

capture_load_task_bootstrap_error() {
  local probe_stderr_path="$1"
  local line=""

  LOAD_TASK_BOOTSTRAP_ERROR=""
  while IFS= read -r line || [ -n "$line" ]; do
    if [ -n "$line" ]; then
      LOAD_TASK_BOOTSTRAP_ERROR="$line"
      printf '%s\n' "$line" >>"$stderr_log"
    fi
  done <"$probe_stderr_path"

  LOAD_TASK_BOOTSTRAP_ERROR="${LOAD_TASK_BOOTSTRAP_ERROR#error: }"
  if [ -z "$LOAD_TASK_BOOTSTRAP_ERROR" ]; then
    LOAD_TASK_BOOTSTRAP_ERROR="load-task-src bootstrap failed"
  fi
}

fail_load_task_bootstrap() {
  local error_message="$1"
  local profile_path="$2"
  local selector_mode="$3"
  local selector_value="$4"
  local exit_code="${5:-1}"
  local finished_at=""

  printf 'error: %s\n' "$error_message" >&2
  printf 'error: %s\n' "$error_message" >>"$stderr_log"
  finished_at="$(timestamp_utc)"
  write_load_task_bootstrap_summary \
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
    "$dry_run" \
    "$selector_mode" \
    "$selector_value" \
    "$error_message"
  exit "$exit_code"
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
  done < <(git -C "$repo_root" diff-tree --no-commit-id --root --name-status -r -m "$commit")
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
cli_error=""
cli_exit_code=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      if [ "$#" -lt 2 ]; then
        record_load_task_cli_error "--profile requires a value" 1 cli_error cli_exit_code
        break
      fi
      profile_input="$2"
      shift 2
      ;;
    --run-root)
      if [ "$#" -lt 2 ]; then
        record_load_task_cli_error "--run-root requires a value" 1 cli_error cli_exit_code
        break
      fi
      run_root_input="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --bead)
      if [ "$#" -lt 2 ]; then
        record_load_task_cli_error "--bead requires a value" 1 cli_error cli_exit_code
        break
      fi
      if [ -n "$selector_mode" ]; then
        record_load_task_cli_error "load-task-src requires exactly one selector" 1 cli_error cli_exit_code
        break
      fi
      selector_mode="bead"
      selector_value="$2"
      shift 2
      ;;
    --work-item)
      if [ "$#" -lt 2 ]; then
        record_load_task_cli_error "--work-item requires a value" 1 cli_error cli_exit_code
        break
      fi
      if [ -n "$selector_mode" ]; then
        record_load_task_cli_error "load-task-src requires exactly one selector" 1 cli_error cli_exit_code
        break
      fi
      selector_mode="work-item"
      selector_value="$2"
      shift 2
      ;;
    --range)
      if [ "$#" -lt 2 ]; then
        record_load_task_cli_error "--range requires a value" 1 cli_error cli_exit_code
        break
      fi
      if [ -n "$selector_mode" ]; then
        record_load_task_cli_error "load-task-src requires exactly one selector" 1 cli_error cli_exit_code
        break
      fi
      selector_mode="range"
      selector_value="$2"
      shift 2
      ;;
    --files)
      record_load_task_cli_error "load-task-src derives file selection internally; --files is not supported" 1 cli_error cli_exit_code
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      record_load_task_cli_error "unknown argument: $1" 1 cli_error cli_exit_code
      break
      ;;
  esac
done

if [ -z "$cli_error" ] && [ -z "$selector_mode" ]; then
  record_load_task_cli_error "load-task-src requires one of --bead, --work-item, or --range" 1 cli_error cli_exit_code
fi

root="$(project_root)"
run_root="$(prepare_capability_run_root "load-task-src" "$run_root_input")"
summary_path="$(capability_summary_path "$run_root")"
stdout_log="$run_root/stdout.log"
stderr_log="$run_root/stderr.log"
: >"$stdout_log"
: >"$stderr_log"
started_at="$(timestamp_utc)"

source_dir="./src/cf"
source_dir_rel="$(normalize_capability_selected_file "$source_dir")"
selected_files_csv=""
selection_json=""
delegated_json='{"delegated":null}'
base_context_json="{}"
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

profile_path="$(resolve_runtime_profile_path "$profile_input" "$root")"
adapter="${RUNNER_ADAPTER:-direct-platform}"
log "Load task-scoped source changes"
log "adapter=$adapter"
if [ -n "$profile_path" ]; then
  log "profile=$profile_path"
fi
log "run_root=$run_root"
printf 'source_dir=%s\n' "$source_dir" >>"$stdout_log"
printf 'selector_mode=%s\n' "$selector_mode" >>"$stdout_log"
printf 'selector_value=%s\n' "$selector_value" >>"$stdout_log"

if [ -z "$cli_error" ]; then
  bootstrap_probe_stderr="$run_root/bootstrap-probe.stderr"
  : >"$bootstrap_probe_stderr"
  if ! (probe_load_task_bootstrap "$profile_path") >/dev/null 2>"$bootstrap_probe_stderr"; then
    capture_load_task_bootstrap_error "$bootstrap_probe_stderr"
    fail_load_task_bootstrap "$LOAD_TASK_BOOTSTRAP_ERROR" "$profile_path" "$selector_mode" "$selector_value"
  fi
  rm -f "$bootstrap_probe_stderr"
fi

if [ -n "$cli_error" ]; then
  status="failed"
  exit_code="$cli_exit_code"
  selection_error="$cli_error"
  printf 'error: %s\n' "$selection_error" | tee -a "$stderr_log" >&2
else
  require_command git
  require_command jq
  load_runtime_profile "$profile_path"
  require_runtime_profile_loaded
  adapter="${RUNNER_ADAPTER:-${RUNTIME_PROFILE_RUNNER_ADAPTER:-direct-platform}}"
  source_dir="$(capability_string_or_default "load-src" "sourceDir" "./src/cf")"
  source_dir_rel="$(normalize_capability_selected_file "$source_dir")"
  printf 'resolved_source_dir=%s\n' "$source_dir" >>"$stdout_log"
  base_context_json="$(build_redacted_context_json)"
  selection_stderr_tmp="$(mktemp)"
fi

if [ "$status" != "failed" ]; then
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
fi

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
