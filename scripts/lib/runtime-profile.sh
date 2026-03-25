#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

RUNTIME_PROFILE_PATH=""
RUNTIME_PROFILE_JSON=""
RUNTIME_PROFILE_NAME=""
RUNTIME_PROFILE_RUNNER_ADAPTER=""
RUNTIME_PROFILE_LOCAL_SANDBOX_DIR="env/.local/"
RUNTIME_PROFILE_POLICY_PATH="automation/context/runtime-profile-policy.json"

runtime_profile_loaded() {
  [ -n "$RUNTIME_PROFILE_PATH" ] && [ -n "$RUNTIME_PROFILE_JSON" ]
}

reset_runtime_profile_state() {
  RUNTIME_PROFILE_PATH=""
  RUNTIME_PROFILE_JSON=""
  RUNTIME_PROFILE_NAME=""
  RUNTIME_PROFILE_RUNNER_ADAPTER=""
}

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

runtime_profile_migration_error() {
  local profile_path="$1"

  die "runtime profile schemaVersion=1 is no longer supported: $profile_path. Migrate it with ./scripts/template/migrate-runtime-profile-v2.sh <legacy-profile> and see docs/migrations/runtime-profile-v2.md"
}

require_runtime_profile_loaded() {
  runtime_profile_loaded || die "runtime profile is required; pass --profile <file> or create env/local.json"
}

canonical_root_runtime_profile_filename() {
  local filename="$1"

  case "$filename" in
    *.example.json|local.json|wsl.json|ci.json|windows-executor.json)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

append_unique_field() {
  local array_name="$1"
  local candidate="$2"
  local existing=""
  local -n fields_ref="$array_name"

  for existing in "${fields_ref[@]}"; do
    if [ "$existing" = "$candidate" ]; then
      return 0
    fi
  done

  fields_ref+=("$candidate")
}

runtime_profile_policy_file_path() {
  local root="$1"

  printf '%s/%s\n' "$root" "$RUNTIME_PROFILE_POLICY_PATH"
}

load_sanctioned_additional_root_runtime_profiles() {
  local root="$1"
  local array_name="$2"
  local policy_path=""
  local relpath=""
  local -n out_ref="$array_name"

  out_ref=()
  policy_path="$(runtime_profile_policy_file_path "$root")"
  if [ ! -f "$policy_path" ]; then
    return 0
  fi

  require_command jq
  while IFS= read -r relpath; do
    [ -n "$relpath" ] || continue

    case "$relpath" in
      env/*.json)
        append_unique_field out_ref "$relpath"
        ;;
      *)
        die "runtime-profile policy lists a non env/*.json path: $relpath"
        ;;
    esac
  done < <(
    jq -r '
      (.rootEnvProfiles.sanctionedAdditionalProfiles // [])
      | if type != "array" then
          error("rootEnvProfiles.sanctionedAdditionalProfiles must be an array")
        else
          .[]
        end
      | tostring
    ' "$policy_path"
  )
}

root_runtime_profile_is_sanctioned_by_policy() {
  local root="$1"
  local relpath="$2"
  local candidate=""
  local -a sanctioned_paths=()

  load_sanctioned_additional_root_runtime_profiles "$root" sanctioned_paths
  for candidate in "${sanctioned_paths[@]}"; do
    if [ "$candidate" = "$relpath" ]; then
      return 0
    fi
  done

  return 1
}

collect_runtime_profile_layout_drift_paths() {
  local root="$1"
  local array_name="$2"
  local env_root="$root/env"
  local path=""
  local filename=""
  local relpath=""
  local -n out_ref="$array_name"

  out_ref=()

  [ -d "$env_root" ] || return 0

  shopt -s nullglob
  for path in "$env_root"/*.json; do
    [ -f "$path" ] || continue
    filename="$(basename "$path")"
    [ -n "$filename" ] || continue

    if canonical_root_runtime_profile_filename "$filename"; then
      continue
    fi

    relpath="env/$filename"
    if root_runtime_profile_is_sanctioned_by_policy "$root" "$relpath"; then
      continue
    fi

    out_ref+=("$relpath")
  done
  shopt -u nullglob
}

build_runtime_profile_layout_warning_json() {
  local root="$1"
  local status="clean"
  local unexpected_json="[]"
  local sanctioned_json="[]"
  local policy_path="$RUNTIME_PROFILE_POLICY_PATH"
  local -a unexpected_paths=()
  local -a sanctioned_paths=()

  require_command jq

  load_sanctioned_additional_root_runtime_profiles "$root" sanctioned_paths
  collect_runtime_profile_layout_drift_paths "$root" unexpected_paths
  if [ "${sanctioned_paths[*]-}" != "" ]; then
    sanctioned_json="$(printf '%s\n' "${sanctioned_paths[@]}" | jq -R . | jq -s '.')"
  fi
  if [ "${unexpected_paths[*]-}" != "" ]; then
    status="warning"
    unexpected_json="$(printf '%s\n' "${unexpected_paths[@]}" | jq -R . | jq -s '.')"
  fi

  jq -cn \
    --arg status "$status" \
    --arg recommended_sandbox "$RUNTIME_PROFILE_LOCAL_SANDBOX_DIR" \
    --arg policy_path "$policy_path" \
    --argjson unexpected_root_profiles "$unexpected_json" \
    --argjson sanctioned_additional_profiles "$sanctioned_json" \
    '{
      runtime_profile_layout: {
        status: $status,
        unexpected_root_profiles: $unexpected_root_profiles,
        recommended_sandbox: $recommended_sandbox,
        policy_path: $policy_path,
        sanctioned_additional_profiles: $sanctioned_additional_profiles
      }
    }'
}

profile_jq_raw() {
  local expr="$1"

  require_runtime_profile_loaded
  jq -r "$expr" <<<"$RUNTIME_PROFILE_JSON"
}

profile_jq_json() {
  local expr="$1"

  require_runtime_profile_loaded
  jq -c "$expr" <<<"$RUNTIME_PROFILE_JSON"
}

profile_has_nonnull() {
  local expr="$1"

  require_runtime_profile_loaded
  jq -e "($expr) != null" <<<"$RUNTIME_PROFILE_JSON" >/dev/null
}

profile_string() {
  local expr="$1"

  profile_jq_raw "$expr"
}

require_profile_string() {
  local expr="$1"
  local label="$2"
  local value=""

  value="$(profile_jq_raw "$expr")"
  if [ -z "$value" ] || [ "$value" = "null" ]; then
    die "runtime profile is missing $label in $RUNTIME_PROFILE_PATH"
  fi

  printf '%s\n' "$value"
}

profile_array_to_named_array() {
  local expr="$1"
  local array_name="$2"
  local array_type=""
  local -n out_ref="$array_name"

  out_ref=()

  require_runtime_profile_loaded

  array_type="$(profile_jq_raw "($expr // []) | type")"
  if [ "$array_type" != "array" ]; then
    die "runtime profile field must be an array: $expr"
  fi

  mapfile -d '' -t out_ref < <(jq -j "($expr // []) | .[] | tostring, \"\u0000\"" <<<"$RUNTIME_PROFILE_JSON")
}

load_runtime_profile() {
  local profile_path="$1"
  local root_type=""
  local schema_version=""
  local runner_adapter=""
  local profile_name=""
  local shell_env_type=""

  reset_runtime_profile_state

  if [ -z "$profile_path" ]; then
    return 0
  fi

  require_command jq

  if [ ! -f "$profile_path" ]; then
    die "runtime profile not found: $profile_path"
  fi

  RUNTIME_PROFILE_JSON="$(cat "$profile_path")"
  root_type="$(jq -r 'type' <<<"$RUNTIME_PROFILE_JSON")"
  if [ "$root_type" != "object" ]; then
    die "runtime profile root must be an object: $profile_path"
  fi

  schema_version="$(jq -r '.schemaVersion // empty' <<<"$RUNTIME_PROFILE_JSON")"
  shell_env_type="$(jq -r '(.shellEnv // null) | if . == null then "null" else type end' <<<"$RUNTIME_PROFILE_JSON")"

  if [ "$schema_version" = "1" ] || { [ -z "$schema_version" ] && [ "$shell_env_type" = "object" ]; }; then
    runtime_profile_migration_error "$profile_path"
  fi

  if [ "$schema_version" != "2" ]; then
    die "unsupported runtime profile schemaVersion=$schema_version in $profile_path"
  fi

  runner_adapter="$(jq -r '.runnerAdapter // empty' <<<"$RUNTIME_PROFILE_JSON")"
  profile_name="$(jq -r '.profileName // empty' <<<"$RUNTIME_PROFILE_JSON")"

  if [ -z "$runner_adapter" ]; then
    die "runtime profile is missing runnerAdapter in $profile_path"
  fi

  RUNTIME_PROFILE_PATH="$profile_path"
  RUNTIME_PROFILE_NAME="$profile_name"
  RUNTIME_PROFILE_RUNNER_ADAPTER="$runner_adapter"
}
