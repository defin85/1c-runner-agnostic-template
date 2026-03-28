#!/usr/bin/env bash
set -euo pipefail

project_root() {
  local script_dir
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$script_dir"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '[%s] %s\n' "$(basename "$0")" "$*"
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    die "command not found: $name"
  fi
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    die "required env var is not set: $name"
  fi
}

ensure_dir() {
  mkdir -p "$1"
}

canonical_path() {
  realpath -m "$1"
}

git_with_unquoted_paths() {
  git -c core.quotepath=false "$@"
}

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

run_command_string() {
  local label="$1"
  local command_string="$2"

  log "$label"
  printf '%s\n' "$command_string"

  if [ "${DRY_RUN:-0}" = "1" ]; then
    return 0
  fi

  bash -lc "$command_string"
}
