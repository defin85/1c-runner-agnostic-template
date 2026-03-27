#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/git/task-trailers.sh <command> [options]

Commands:
  render [--bead <id>] [--work-item <id>]
  validate-message --file <path> [--require-any]
  select-commits [--repo <path>] (--bead <id> | --work-item <id> | --range <revset>)
EOF
}

append_unique_line() {
  local value="$1"
  local array_name="$2"
  local existing=""
  local -n out_ref="$array_name"

  for existing in "${out_ref[@]}"; do
    if [ "$existing" = "$value" ]; then
      return 0
    fi
  done

  out_ref+=("$value")
}

normalize_trailer_value() {
  local value="$1"

  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s\n' "$value"
}

canonical_trailer_lines_from_file() {
  local message_file="$1"
  local line=""

  while IFS= read -r line; do
    case "$line" in
      "Bead:"*|"Work-Item:"*)
        printf '%s\n' "$line"
        ;;
    esac
  done < <(git interpret-trailers --parse <"$message_file")
}

validate_message_command() {
  local message_file=""
  local require_any=0
  local line=""
  local key=""
  local value=""
  local bead_count=0
  local work_item_count=0

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --file)
        [ "$#" -ge 2 ] || die "--file requires a value"
        message_file="$2"
        shift 2
        ;;
      --require-any)
        require_any=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument for validate-message: $1"
        ;;
    esac
  done

  [ -n "$message_file" ] || die "validate-message requires --file"
  [ -f "$message_file" ] || die "message file not found: $message_file"

  while IFS= read -r line; do
    key="${line%%:*}"
    value="$(normalize_trailer_value "${line#*:}")"
    [ -n "$value" ] || die "empty value for trailer: $key"

    case "$key" in
      Bead)
        bead_count=$((bead_count + 1))
        [ "$bead_count" -le 1 ] || die "duplicate trailer: Bead"
        ;;
      Work-Item)
        work_item_count=$((work_item_count + 1))
        [ "$work_item_count" -le 1 ] || die "duplicate trailer: Work-Item"
        ;;
    esac
  done < <(canonical_trailer_lines_from_file "$message_file")

  if [ "$require_any" -eq 1 ] && [ "$bead_count" -eq 0 ] && [ "$work_item_count" -eq 0 ]; then
    die "message does not contain canonical task trailers"
  fi
}

render_command() {
  local bead=""
  local work_item=""

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --bead)
        [ "$#" -ge 2 ] || die "--bead requires a value"
        bead="$(normalize_trailer_value "$2")"
        shift 2
        ;;
      --work-item)
        [ "$#" -ge 2 ] || die "--work-item requires a value"
        work_item="$(normalize_trailer_value "$2")"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument for render: $1"
        ;;
    esac
  done

  [ -n "$bead" ] || [ -n "$work_item" ] || die "render requires --bead and/or --work-item"

  if [ -n "$bead" ]; then
    printf 'Bead: %s\n' "$bead"
  fi
  if [ -n "$work_item" ]; then
    printf 'Work-Item: %s\n' "$work_item"
  fi
}

commit_trailer_value() {
  local repo="$1"
  local rev="$2"
  local trailer_key="$3"
  local message_file=""
  local line=""
  local value=""
  local result=""
  local count=0
  local invalid=0

  message_file="$(mktemp)"
  trap 'rm -f "$message_file"' RETURN
  git -C "$repo" log -1 --format=%B "$rev" >"$message_file"

  while IFS= read -r line; do
    if [[ "$line" == "$trailer_key:"* ]]; then
      value="$(normalize_trailer_value "${line#*:}")"
      if [ -z "$value" ]; then
        invalid=1
        continue
      fi

      count=$((count + 1))
      if [ "$count" -eq 1 ]; then
        result="$value"
      else
        invalid=1
      fi
    fi
  done < <(canonical_trailer_lines_from_file "$message_file")

  if [ "$invalid" -eq 1 ] || [ "$count" -ne 1 ]; then
    printf '\n'
    return 0
  fi

  printf '%s\n' "$result"
}

select_commits_command() {
  local repo=""
  local selector_mode=""
  local selector_value=""
  local rev=""
  local line=""
  local trailer_key=""
  local matched_value=""
  local -a commits=()

  repo="$(pwd)"

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo)
        [ "$#" -ge 2 ] || die "--repo requires a value"
        repo="$2"
        shift 2
        ;;
      --bead)
        [ "$#" -ge 2 ] || die "--bead requires a value"
        [ -z "$selector_mode" ] || die "select-commits requires exactly one selector"
        selector_mode="bead"
        selector_value="$(normalize_trailer_value "$2")"
        shift 2
        ;;
      --work-item)
        [ "$#" -ge 2 ] || die "--work-item requires a value"
        [ -z "$selector_mode" ] || die "select-commits requires exactly one selector"
        selector_mode="work-item"
        selector_value="$(normalize_trailer_value "$2")"
        shift 2
        ;;
      --range)
        [ "$#" -ge 2 ] || die "--range requires a value"
        [ -z "$selector_mode" ] || die "select-commits requires exactly one selector"
        selector_mode="range"
        selector_value="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument for select-commits: $1"
        ;;
    esac
  done

  [ -n "$selector_mode" ] || die "select-commits requires one of --bead, --work-item, or --range"

  case "$selector_mode" in
    range)
      git -C "$repo" rev-list --reverse "$selector_value"
      return 0
      ;;
    bead)
      trailer_key="Bead"
      ;;
    work-item)
      trailer_key="Work-Item"
      ;;
  esac

  while IFS= read -r rev; do
    [ -n "$rev" ] || continue
    matched_value="$(commit_trailer_value "$repo" "$rev" "$trailer_key")"
    if [ "$matched_value" = "$selector_value" ]; then
      append_unique_line "$rev" commits
    fi
  done < <(git -C "$repo" rev-list --reverse HEAD)

  for line in "${commits[@]}"; do
    printf '%s\n' "$line"
  done
}

command="${1:-}"
case "$command" in
  render)
    shift
    render_command "$@"
    ;;
  validate-message)
    shift
    validate_message_command "$@"
    ;;
  select-commits)
    shift
    select_commits_command "$@"
    ;;
  ""|-h|--help)
    usage
    ;;
  *)
    die "unknown command: $command"
    ;;
esac
