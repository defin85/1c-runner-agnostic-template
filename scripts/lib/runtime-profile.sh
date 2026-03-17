#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

RUNTIME_PROFILE_PATH=""
RUNTIME_PROFILE_NAME=""
RUNTIME_PROFILE_RUNNER_ADAPTER=""

resolve_runtime_profile_path() {
  local requested_path="${1:-}"
  local root="$2"
  local resolved=""

  if [ -n "$requested_path" ]; then
    resolved="$requested_path"
  elif [ -n "${ONEC_PROFILE:-}" ]; then
    resolved="$ONEC_PROFILE"
  elif [ -f "$root/env/local.json" ]; then
    resolved="$root/env/local.json"
  fi

  if [ -z "$resolved" ]; then
    printf '\n'
    return
  fi

  printf '%s\n' "$(canonical_path "$resolved")"
}

load_runtime_profile() {
  local profile_path="$1"
  local shell_env_type=""
  local runner_adapter=""
  local profile_name=""
  local schema_version=""

  if [ -z "$profile_path" ]; then
    return 0
  fi

  require_command jq

  if [ ! -f "$profile_path" ]; then
    die "runtime profile not found: $profile_path"
  fi

  schema_version="$(jq -r '.schemaVersion // 1' "$profile_path")"
  if [ "$schema_version" != "1" ]; then
    die "unsupported runtime profile schemaVersion=$schema_version in $profile_path"
  fi

  shell_env_type="$(jq -r '(.shellEnv // {}) | type' "$profile_path")"
  if [ "$shell_env_type" != "object" ]; then
    die "runtime profile field shellEnv must be an object: $profile_path"
  fi

  runner_adapter="$(jq -r '.runnerAdapter // empty' "$profile_path")"
  profile_name="$(jq -r '.profileName // empty' "$profile_path")"

  while IFS=$'\t' read -r key value; do
    export "$key=$value"
  done < <(jq -r '.shellEnv // {} | to_entries[] | [.key, (.value | tostring)] | @tsv' "$profile_path")

  if [ -n "$runner_adapter" ] && [ -z "${RUNNER_ADAPTER:-}" ]; then
    export RUNNER_ADAPTER="$runner_adapter"
  fi

  RUNTIME_PROFILE_PATH="$profile_path"
  RUNTIME_PROFILE_NAME="$profile_name"
  RUNTIME_PROFILE_RUNNER_ADAPTER="$runner_adapter"
}
