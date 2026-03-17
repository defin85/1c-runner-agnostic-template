#!/usr/bin/env bash
set -euo pipefail

project_root() {
  local script_dir
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$script_dir"
}

log() {
  printf '[%s] %s\n' "$(basename "$0")" "$*"
}

require_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    printf 'error: command not found: %s\n' "$name" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    printf 'error: required env var is not set: %s\n' "$name" >&2
    exit 1
  fi
}

ensure_dir() {
  mkdir -p "$1"
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
