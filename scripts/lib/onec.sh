#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"
# shellcheck source=./runtime-profile.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-profile.sh"
# shellcheck source=./capability.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/capability.sh"
# shellcheck source=./ibcmd.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/ibcmd.sh"

capability_profile_key() {
  case "$1" in
    create-ib) printf 'createIb\n' ;;
    dump-src) printf 'dumpSrc\n' ;;
    load-src) printf 'loadSrc\n' ;;
    update-db) printf 'updateDb\n' ;;
    diff-src) printf 'diffSrc\n' ;;
    run-xunit) printf 'xunit\n' ;;
    run-bdd) printf 'bdd\n' ;;
    run-smoke) printf 'smoke\n' ;;
    publish-http) printf 'publishHttp\n' ;;
    *)
      die "unsupported capability id: $1"
      ;;
  esac
}

capability_command_expr() {
  local key=""

  key="$(capability_profile_key "$1")"
  printf '.capabilities.%s.command' "$key"
}

capability_unsupported_reason_expr() {
  local key=""

  key="$(capability_profile_key "$1")"
  printf '.capabilities.%s.unsupportedReason' "$key"
}

capability_driver_expr() {
  local key=""

  key="$(capability_profile_key "$1")"
  printf '.capabilities.%s.driver' "$key"
}

capability_supports_driver_selection() {
  case "$1" in
    create-ib|dump-src|load-src|update-db)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_project_tree_path() {
  local candidate="$1"
  local root=""

  case "$candidate" in
    /*)
      canonical_path "$candidate"
      ;;
    *)
      root="$(project_root)"
      canonical_path "$root/$candidate"
      ;;
  esac
}

capability_has_profile_driver() {
  profile_has_nonnull "$(capability_driver_expr "$1")"
}

capability_has_profile_unsupported_reason() {
  profile_has_nonnull "$(capability_unsupported_reason_expr "$1")"
}

command_basename() {
  local command_path="${1:-}"

  printf '%s\n' "${command_path##*/}"
}

command_targets_local_platform_gui() {
  local command_path="${1:-}"
  local name=""

  name="$(command_basename "$command_path")"
  case "$name" in
    1cv8|1cv8c)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

direct_platform_xvfb_enabled() {
  local enabled_type=""
  local enabled_value=""

  enabled_type="$(profile_string '(.platform.xvfb.enabled // null) | if . == null then "null" else type end')"
  case "$enabled_type" in
    null)
      return 1
      ;;
    boolean)
      ;;
    *)
      die "runtime profile field must be a boolean: .platform.xvfb.enabled"
      ;;
  esac

  enabled_value="$(profile_string '.platform.xvfb.enabled // false')"
  [ "$enabled_value" = "true" ]
}

direct_platform_ld_preload_enabled() {
  local enabled_type=""
  local enabled_value=""

  enabled_type="$(profile_string '(.platform.ldPreload.enabled // null) | if . == null then "null" else type end')"
  case "$enabled_type" in
    null)
      return 1
      ;;
    boolean)
      ;;
    *)
      die "runtime profile field must be a boolean: .platform.ldPreload.enabled"
      ;;
  esac

  enabled_value="$(profile_string '.platform.ldPreload.enabled // false')"
  [ "$enabled_value" = "true" ]
}

load_direct_platform_xvfb_server_args() {
  local array_name="$1"
  local server_args_type=""
  local -n out_ref="$array_name"

  out_ref=()
  if ! direct_platform_xvfb_enabled; then
    return 0
  fi

  server_args_type="$(profile_string '(.platform.xvfb.serverArgs // null) | if . == null then "null" else type end')"
  if [ "$server_args_type" != "array" ]; then
    die "runtime profile field must be an array: .platform.xvfb.serverArgs"
  fi

  profile_array_to_named_array '.platform.xvfb.serverArgs' "$array_name"
}

load_direct_platform_ld_preload_libraries() {
  local array_name="$1"
  local libraries_type=""
  local -n out_ref="$array_name"

  out_ref=()
  if ! direct_platform_ld_preload_enabled; then
    return 0
  fi

  libraries_type="$(profile_string '(.platform.ldPreload.libraries // null) | if . == null then "null" else type end')"
  if [ "$libraries_type" != "array" ]; then
    die "runtime profile field must be an array: .platform.ldPreload.libraries"
  fi

  profile_array_to_named_array '.platform.ldPreload.libraries' "$array_name"
}

build_json_array_from_named_array() {
  local array_name="$1"
  local -n array_ref="$array_name"

  require_command jq
  set -- "${array_ref[@]}"
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  jq -cn '$ARGS.positional' --args -- "${array_ref[@]}"
}

join_named_array_with_spaces() {
  local array_name="$1"
  local result=""
  local value=""
  local first=1
  local -n array_ref="$array_name"

  for value in "${array_ref[@]}"; do
    if [ "$first" -eq 0 ]; then
      result+=" "
    fi
    result+="$value"
    first=0
  done

  printf '%s\n' "$result"
}

join_named_array_with_colons() {
  local array_name="$1"
  local result=""
  local value=""
  local first=1
  local -n array_ref="$array_name"

  for value in "${array_ref[@]}"; do
    if [ "$first" -eq 0 ]; then
      result+=":"
    fi
    result+="$value"
    first=0
  done

  printf '%s\n' "$result"
}

direct_platform_xvfb_wrapper_selected_for_command() {
  local adapter="$1"
  local command_path="${2:-}"

  if [ "$adapter" != "direct-platform" ]; then
    return 1
  fi

  if ! direct_platform_xvfb_enabled; then
    return 1
  fi

  command_targets_local_platform_gui "$command_path"
}

direct_platform_ld_preload_selected_for_command() {
  local adapter="$1"
  local command_path="${2:-}"

  if [ "$adapter" != "direct-platform" ]; then
    return 1
  fi

  if ! direct_platform_ld_preload_enabled; then
    return 1
  fi

  command_targets_local_platform_gui "$command_path"
}

direct_platform_adapter_contour_selected_for_command() {
  local adapter="$1"
  local command_path="${2:-}"

  if direct_platform_xvfb_wrapper_selected_for_command "$adapter" "$command_path"; then
    return 0
  fi

  if direct_platform_ld_preload_selected_for_command "$adapter" "$command_path"; then
    return 0
  fi

  return 1
}

direct_platform_xvfb_failure_reason_for_command_path() {
  local adapter="$1"
  local command_path="${2:-}"

  if ! direct_platform_xvfb_wrapper_selected_for_command "$adapter" "$command_path"; then
    printf '\n'
    return 0
  fi

  if ! command -v xvfb-run >/dev/null 2>&1; then
    printf 'missing xvfb-run for direct-platform xvfb wrapper\n'
    return 0
  fi

  if ! command -v xauth >/dev/null 2>&1; then
    printf 'missing xauth for direct-platform xvfb wrapper\n'
    return 0
  fi

  printf '\n'
}

direct_platform_ld_preload_failure_reason_for_command_path() {
  local adapter="$1"
  local command_path="${2:-}"
  local library_path=""
  local -a libraries=()

  if ! direct_platform_ld_preload_selected_for_command "$adapter" "$command_path"; then
    printf '\n'
    return 0
  fi

  load_direct_platform_ld_preload_libraries libraries
  set -- "${libraries[@]}"
  if [ "$#" -eq 0 ]; then
    printf 'platform.ldPreload.libraries must not be empty for direct-platform ld-preload contour\n'
    return 0
  fi

  for library_path in "${libraries[@]}"; do
    case "$library_path" in
      /*)
        ;;
      *)
        printf 'direct-platform ld-preload library path must be absolute: %s\n' "$library_path"
        return 0
        ;;
    esac

    if [ ! -e "$library_path" ]; then
      printf 'missing direct-platform ld-preload library: %s\n' "$library_path"
      return 0
    fi
  done

  printf '\n'
}

direct_platform_adapter_failure_reason_for_command_path() {
  local adapter="$1"
  local command_path="${2:-}"
  local reason=""

  reason="$(direct_platform_xvfb_failure_reason_for_command_path "$adapter" "$command_path")"
  if [ -n "$reason" ]; then
    printf '%s\n' "$reason"
    return 0
  fi

  reason="$(direct_platform_ld_preload_failure_reason_for_command_path "$adapter" "$command_path")"
  printf '%s\n' "$reason"
}

build_direct_platform_adapter_context_json() {
  local -a server_args=()
  local -a libraries=()
  local server_args_json="[]"
  local libraries_json="[]"
  local has_xvfb=false
  local has_ld_preload=false

  if [ "${RUNTIME_PROFILE_RUNNER_ADAPTER:-}" != "direct-platform" ]; then
    printf '{}\n'
    return 0
  fi

  if direct_platform_xvfb_enabled; then
    has_xvfb=true
    load_direct_platform_xvfb_server_args server_args
    server_args_json="$(build_json_array_from_named_array server_args)"
  fi

  if direct_platform_ld_preload_enabled; then
    has_ld_preload=true
    load_direct_platform_ld_preload_libraries libraries
    libraries_json="$(build_json_array_from_named_array libraries)"
  fi

  if [ "$has_xvfb" = false ] && [ "$has_ld_preload" = false ]; then
    printf '{}\n'
    return 0
  fi

  jq -cn \
    --argjson has_xvfb "$has_xvfb" \
    --argjson has_ld_preload "$has_ld_preload" \
    --argjson server_args "$server_args_json" \
    --argjson libraries "$libraries_json" \
    '{
      adapter_context:
        ((if $has_xvfb then {
          wrapper: "xvfb-run",
          xvfb: {
            enabled: true,
            server_args: $server_args
          }
        } else {} end)
        + (if $has_ld_preload then {
          ld_preload: {
            enabled: true,
            libraries: $libraries
          }
        } else {} end))
    }'
}

build_capability_adapter_context_json() {
  local adapter="$1"
  local command_path="${2:-}"

  if ! direct_platform_adapter_contour_selected_for_command "$adapter" "$command_path"; then
    printf '{}\n'
    return 0
  fi

  build_direct_platform_adapter_context_json
}

build_capability_context_json() {
  local adapter="$1"
  local base_json="{}"
  local adapter_json="{}"

  base_json="$(build_redacted_context_json)"
  set -- "${CAPABILITY_COMMAND[@]}"
  if [ "$#" -gt 0 ]; then
    adapter_json="$(build_capability_adapter_context_json "$adapter" "${CAPABILITY_COMMAND[0]}")"
  fi

  jq -cn \
    --argjson base "$base_json" \
    --argjson extra "$adapter_json" \
    '$base + $extra'
}

build_doctor_context_json() {
  local adapter="$1"
  local base_json="{}"
  local adapter_json="{}"

  base_json="$(build_redacted_context_json)"
  if [ "$adapter" = "direct-platform" ] && { direct_platform_xvfb_enabled || direct_platform_ld_preload_enabled; }; then
    adapter_json="$(build_direct_platform_adapter_context_json)"
  fi

  jq -cn \
    --argjson base "$base_json" \
    --argjson extra "$adapter_json" \
    '$base + $extra'
}

profile_command_uses_direct_platform_wrapper() {
  local adapter="$1"
  local array_name="$2"
  local -n command_ref="$array_name"

  set -- "${command_ref[@]}"
  if [ "$#" -eq 0 ]; then
    return 1
  fi

  direct_platform_adapter_contour_selected_for_command "$adapter" "${command_ref[0]}"
}

doctor_requires_direct_platform_xvfb_tools() {
  local adapter="$1"

  [ "$adapter" = "direct-platform" ] || return 1
  direct_platform_xvfb_enabled
}

validate_capability_command_driver_contract() {
  local capability_id="$1"
  local has_command=1
  local has_driver=1
  local has_unsupported_reason=1

  if capability_has_profile_command "$capability_id"; then
    has_command=0
  fi

  if capability_has_profile_driver "$capability_id"; then
    has_driver=0
  fi

  if capability_has_profile_unsupported_reason "$capability_id"; then
    has_unsupported_reason=0
  fi

  if [ "$has_command" -eq 0 ] && [ "$has_driver" -eq 0 ]; then
    die "capability $capability_id must not define both driver and command in $RUNTIME_PROFILE_PATH"
  fi

  if [ "$has_command" -eq 0 ] && [ "$has_unsupported_reason" -eq 0 ]; then
    die "capability $capability_id must not define both command and unsupportedReason in $RUNTIME_PROFILE_PATH"
  fi

  if [ "$has_driver" -eq 0 ] && [ "$has_unsupported_reason" -eq 0 ]; then
    die "capability $capability_id must not define both driver and unsupportedReason in $RUNTIME_PROFILE_PATH"
  fi

  if [ "$has_driver" -eq 0 ] && ! capability_supports_driver_selection "$capability_id"; then
    die "capability $capability_id does not support driver selection in $RUNTIME_PROFILE_PATH"
  fi
}

resolve_capability_driver() {
  local capability_id="$1"
  local driver=""

  validate_capability_command_driver_contract "$capability_id"
  if ! capability_supports_driver_selection "$capability_id"; then
    printf '\n'
    return
  fi

  driver="$(profile_string "$(capability_driver_expr "$capability_id") // empty")"
  if [ -z "$driver" ]; then
    printf 'designer\n'
    return
  fi

  case "$driver" in
    designer|ibcmd)
      printf '%s\n' "$driver"
      ;;
    *)
      die "unsupported driver=$driver for capability $capability_id in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

build_redacted_context_json() {
  local mode=""
  local auth_mode=""
  local server=""
  local ref=""
  local file_path=""
  local profile_name=""

  if ! runtime_profile_loaded; then
    printf '{}\n'
    return
  fi

  mode="$(profile_string '.infobase.mode // empty')"
  auth_mode="$(profile_string '.infobase.auth.mode // "os"')"
  server="$(profile_string '.infobase.server // empty')"
  ref="$(profile_string '.infobase.ref // empty')"
  file_path="$(profile_string '.infobase.filePath // empty')"
  profile_name="$(profile_string '.profileName // empty')"

  jq -cn \
    --arg profile_name "$profile_name" \
    --arg mode "$mode" \
    --arg server "$server" \
    --arg ref "$ref" \
    --arg file_path "$file_path" \
    --arg auth_mode "$auth_mode" \
    '{
      runtime_profile: {
        name: (if $profile_name == "" then null else $profile_name end)
      },
      infobase: {
        mode: (if $mode == "" then null else $mode end),
        server: (if $server == "" then null else $server end),
        ref: (if $ref == "" then null else $ref end),
        file_path: (if $file_path == "" then null else $file_path end),
        auth_mode: (if $auth_mode == "" then null else $auth_mode end)
      }
    }'
}

build_unsupported_capability_context_json() {
  local reason="$1"
  local base_json="{}"

  base_json="$(build_redacted_context_json)"

  jq -cn \
    --argjson base "$base_json" \
    --arg reason "$reason" \
    '$base + {
      unsupported: {
        placeholder: true,
        reason: $reason
      }
    }'
}

set_prepared_context_from_profile() {
  local adapter="$1"

  set_capability_context_json "$(build_capability_context_json "$adapter")"
}

build_doctor_driver_context_json() {
  local capability_id="$1"
  local driver="$2"
  local ibcmd_context="{}"

  require_command jq

  case "$driver" in
    designer|"")
      printf '{}\n'
      ;;
    ibcmd)
      ibcmd_context="$(jq -c '.driver_context' <<<"$(build_ibcmd_capability_context_json false)")"
      printf '%s\n' "$ibcmd_context"
      ;;
    *)
      die "unsupported driver resolution for doctor context: $driver"
      ;;
  esac
}

capability_has_profile_command() {
  local expr=""

  expr="$(capability_command_expr "$1")"
  profile_has_nonnull "$expr"
}

load_profile_command_array() {
  local capability_id="$1"
  local array_name="$2"
  local expr=""
  local command_type=""

  expr="$(capability_command_expr "$capability_id")"
  command_type="$(profile_string "($expr // []) | type")"

  if [ "$command_type" != "array" ]; then
    die "runtime profile field must be an array: $expr"
  fi

  profile_array_to_named_array "$expr" "$array_name"
}

maybe_use_profile_command() {
  local capability_id="$1"
  local adapter="$2"
  local executor="direct"
  local -a profile_command=()

  validate_capability_command_driver_contract "$capability_id"
  if ! capability_has_profile_command "$capability_id"; then
    return 1
  fi

  load_profile_command_array "$capability_id" profile_command
  if [ "${profile_command[*]-}" = "" ]; then
    die "runtime profile capability command must not be empty: $(capability_command_expr "$capability_id")"
  fi

  if profile_command_uses_direct_platform_wrapper "$adapter" profile_command; then
    executor="adapter-wrapper"
  fi

  set_prepared_capability_command "" "profile-command" "$executor" "${profile_command[@]}"
  set_prepared_context_from_profile "$adapter"
  return 0
}

maybe_use_profile_unsupported_reason() {
  local capability_id="$1"
  local reason=""

  validate_capability_command_driver_contract "$capability_id"
  if ! capability_has_profile_unsupported_reason "$capability_id"; then
    return 1
  fi

  reason="$(require_profile_string "$(capability_unsupported_reason_expr "$capability_id") // empty" "$(capability_unsupported_reason_expr "$capability_id")")"
  set_prepared_capability_command "" "unsupported-profile" "builtin-unsupported" "$reason"
  set_capability_context_json "$(build_unsupported_capability_context_json "$reason")"
  return 0
}

platform_binary_path() {
  require_profile_string '.platform.binaryPath // empty' 'platform.binaryPath'
}

resolve_secret_value() {
  local env_name="$1"
  local value=""

  if [ -z "$env_name" ]; then
    printf '\n'
    return
  fi

  value="${!env_name:-}"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
    return
  fi

  if [ "$CAPABILITY_DRY_RUN" = "1" ]; then
    printf '__REDACTED_SECRET__\n'
    return
  fi

  die "required secret env var is not set: $env_name"
}

escape_connection_string_value() {
  local value="$1"

  value="${value//\"/\"\"}"
  printf '%s\n' "$value"
}

infobase_mode() {
  require_profile_string '.infobase.mode // empty' 'infobase.mode'
}

append_connection_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local override=""
  local mode=""
  local server=""
  local ref=""
  local file_path=""

  override="$(profile_string '.infobase.connectionStringOverride // empty')"
  if [ -n "$override" ]; then
    args_ref+=("/IBConnectionString" "$override")
    return
  fi

  mode="$(infobase_mode)"
  case "$mode" in
    file)
      file_path="$(require_profile_string '.infobase.filePath // empty' 'infobase.filePath')"
      args_ref+=("/F" "$file_path")
      ;;
    client-server)
      server="$(require_profile_string '.infobase.server // empty' 'infobase.server')"
      ref="$(require_profile_string '.infobase.ref // empty' 'infobase.ref')"
      args_ref+=("/S" "$server/$ref")
      ;;
    *)
      die "unsupported infobase.mode=$mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

append_auth_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local auth_mode=""
  local user=""
  local password_env=""
  local password_value=""

  auth_mode="$(profile_string '.infobase.auth.mode // "os"')"

  case "$auth_mode" in
    os)
      args_ref+=("/WA+")
      ;;
    user-password)
      user="$(require_profile_string '.infobase.auth.user // empty' 'infobase.auth.user')"
      password_env="$(require_profile_string '.infobase.auth.passwordEnv // empty' 'infobase.auth.passwordEnv')"
      password_value="$(resolve_secret_value "$password_env")"
      args_ref+=("/WA-" "/N" "$user" "/P" "$password_value")
      ;;
    *)
      die "unsupported infobase.auth.mode=$auth_mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

build_create_infobase_connection_string() {
  local override=""
  local mode=""
  local server=""
  local ref=""
  local file_path=""
  local auth_mode=""
  local user=""
  local password_env=""
  local password_value=""
  local escaped_user=""
  local escaped_password=""

  override="$(profile_string '.infobase.connectionStringOverride // empty')"
  if [ -n "$override" ]; then
    printf '%s\n' "$override"
    return
  fi

  mode="$(infobase_mode)"
  case "$mode" in
    file)
      file_path="$(require_profile_string '.infobase.filePath // empty' 'infobase.filePath')"
      printf 'File="%s"\n' "$(escape_connection_string_value "$file_path")"
      ;;
    client-server)
      server="$(require_profile_string '.infobase.server // empty' 'infobase.server')"
      ref="$(require_profile_string '.infobase.ref // empty' 'infobase.ref')"
      printf 'Srvr="%s";Ref="%s"' \
        "$(escape_connection_string_value "$server")" \
        "$(escape_connection_string_value "$ref")"

      auth_mode="$(profile_string '.infobase.auth.mode // "os"')"
      if [ "$auth_mode" = "user-password" ]; then
        user="$(require_profile_string '.infobase.auth.user // empty' 'infobase.auth.user')"
        password_env="$(require_profile_string '.infobase.auth.passwordEnv // empty' 'infobase.auth.passwordEnv')"
        password_value="$(resolve_secret_value "$password_env")"
        escaped_user="$(escape_connection_string_value "$user")"
        escaped_password="$(escape_connection_string_value "$password_value")"
        printf ';Usr="%s";Pwd="%s"' "$escaped_user" "$escaped_password"
      fi

      printf '\n'
      ;;
    *)
      die "unsupported infobase.mode=$mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

build_designer_command() {
  local array_name="$1"
  shift
  local -n out_ref="$array_name"
  local binary_path=""

  binary_path="$(platform_binary_path)"
  out_ref=("$binary_path" "DESIGNER")
  append_connection_args out_ref
  append_auth_args out_ref
  out_ref+=("$@")
}

capability_string_or_default() {
  local capability_id="$1"
  local field_name="$2"
  local default_value="$3"
  local key=""
  local value=""

  key="$(capability_profile_key "$capability_id")"
  value="$(profile_string ".capabilities.${key}.${field_name} // empty")"

  if [ -n "$value" ]; then
    printf '%s\n' "$value"
    return
  fi

  printf '%s\n' "$default_value"
}

prepare_create_ib_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local connection_string=""
  local binary_path=""

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$adapter"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  case "$driver" in
    designer)
      ;;
    ibcmd)
      prepare_ibcmd_create_ib_command "$capability_id" "$adapter"
      return 0
      ;;
    *)
      die "unsupported driver resolution for capability $capability_id: $driver"
      ;;
  esac

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.createIb.command for adapter $adapter"
      ;;
  esac

  binary_path="$(platform_binary_path)"
  connection_string="$(build_create_infobase_connection_string)"
  set_prepared_capability_command "designer" "standard-builder" "adapter-wrapper" "$binary_path" "CREATEINFOBASE" "$connection_string"
  set_prepared_context_from_profile "$adapter"
}

prepare_dump_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local output_dir=""
  local -a command=()

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$adapter"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  output_dir="$(capability_string_or_default "$capability_id" "outputDir" "./src/cf")"
  output_dir="$(resolve_project_tree_path "$output_dir")"
  case "$driver" in
    designer)
      ;;
    ibcmd)
      prepare_ibcmd_dump_src_command "$capability_id" "$adapter" "$output_dir"
      return 0
      ;;
    *)
      die "unsupported driver resolution for capability $capability_id: $driver"
      ;;
  esac

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.dumpSrc.command for adapter $adapter"
      ;;
  esac

  build_designer_command command "/DumpConfigToFiles" "$output_dir"
  set_prepared_capability_command "designer" "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile "$adapter"
}

prepare_load_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local source_dir=""
  local -a command=()

  if capability_selected_files_requested && capability_has_profile_command "$capability_id"; then
    die "partial load-src is not supported when capabilities.loadSrc.command override is set"
  fi

  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$adapter"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  source_dir="$(capability_string_or_default "$capability_id" "sourceDir" "./src/cf")"
  source_dir="$(resolve_project_tree_path "$source_dir")"
  if capability_selected_files_requested && [ "$driver" != "ibcmd" ]; then
    die "partial load-src is supported only for ibcmd driver"
  fi

  case "$driver" in
    designer)
      ;;
    ibcmd)
      prepare_ibcmd_load_src_command "$capability_id" "$adapter" "$source_dir"
      return 0
      ;;
    *)
      die "unsupported driver resolution for capability $capability_id: $driver"
      ;;
  esac

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.loadSrc.command for adapter $adapter"
      ;;
  esac

  build_designer_command command "/LoadConfigFromFiles" "$source_dir"
  set_prepared_capability_command "designer" "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile "$adapter"
}

prepare_update_db_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local -a command=()

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$adapter"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  case "$driver" in
    designer)
      ;;
    ibcmd)
      prepare_ibcmd_update_db_command "$capability_id" "$adapter"
      return 0
      ;;
    *)
      die "unsupported driver resolution for capability $capability_id: $driver"
      ;;
  esac

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.updateDb.command for adapter $adapter"
      ;;
  esac

  build_designer_command command "/UpdateDBCfg"
  set_prepared_capability_command "designer" "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile "$adapter"
}

prepare_diff_src_command() {
  local capability_id="$1"
  local _adapter="$2"

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$_adapter"; then
    return 0
  fi

  set_prepared_capability_command "" "builtin-command" "direct" git diff -- ./src
  set_prepared_context_from_profile "$_adapter"
}

prepare_required_profile_command() {
  local capability_id="$1"
  local _adapter="$2"

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_unsupported_reason "$capability_id"; then
    return 0
  fi
  if maybe_use_profile_command "$capability_id" "$_adapter"; then
    return 0
  fi

  die "runtime profile is missing $(capability_command_expr "$capability_id") in $RUNTIME_PROFILE_PATH"
}

collect_required_env_refs() {
  local array_name="$1"
  local -n env_refs="$array_name"
  local capability_id=""
  local driver=""
  local ref=""

  env_refs=()

  for ref in \
    "$(profile_string '.dbms.passwordEnv // empty')" \
    "$(profile_string '.clusterAdmin.passwordEnv // empty')"; do
    if [ -n "$ref" ]; then
      append_unique_field env_refs "$ref"
    fi
  done

  for capability_id in create-ib dump-src load-src update-db; do
    if capability_has_profile_command "$capability_id" || capability_has_profile_unsupported_reason "$capability_id"; then
      continue
    fi

    driver="$(resolve_capability_driver "$capability_id")"
    case "$driver" in
      designer)
        if [ "$(profile_string '.infobase.auth.mode // "os"')" = "user-password" ]; then
          ref="$(profile_string '.infobase.auth.passwordEnv // empty')"
          if [ -n "$ref" ]; then
            append_unique_field env_refs "$ref"
          fi
        fi
        ;;
      ibcmd)
        collect_ibcmd_required_env_refs_for_capability "$capability_id" env_refs
        ;;
    esac
  done
}

collect_designer_required_profile_fields() {
  local array_name="$1"
  local mode=""

  append_unique_field "$array_name" platform.binaryPath
  append_unique_field "$array_name" infobase.mode

  mode="$(profile_string '.infobase.mode // empty')"
  case "$mode" in
    file)
      append_unique_field "$array_name" infobase.filePath
      ;;
    client-server)
      append_unique_field "$array_name" infobase.server
      append_unique_field "$array_name" infobase.ref
      ;;
  esac

  if [ "$(profile_string '.infobase.auth.mode // "os"')" = "user-password" ]; then
    append_unique_field "$array_name" infobase.auth.user
    append_unique_field "$array_name" infobase.auth.passwordEnv
  fi
}

collect_direct_platform_xvfb_required_profile_fields() {
  local array_name="$1"

  append_unique_field "$array_name" platform.xvfb.enabled
  append_unique_field "$array_name" platform.xvfb.serverArgs
}

collect_direct_platform_ld_preload_required_profile_fields() {
  local array_name="$1"

  append_unique_field "$array_name" platform.ldPreload.enabled
  append_unique_field "$array_name" platform.ldPreload.libraries
}

collect_required_profile_fields() {
  local adapter="$1"
  local array_name="$2"
  local capability_id=""
  local driver=""
  local -n out_ref="$array_name"

  out_ref=(runnerAdapter)

  case "$adapter" in
    direct-platform|remote-windows|vrunner)
      ;;
    *)
      return 0
      ;;
  esac

  for capability_id in create-ib dump-src load-src update-db; do
    if capability_has_profile_command "$capability_id" || capability_has_profile_unsupported_reason "$capability_id"; then
      continue
    fi

    driver="$(resolve_capability_driver "$capability_id")"
    case "$driver" in
      designer)
        collect_designer_required_profile_fields out_ref
        ;;
      ibcmd)
        collect_ibcmd_required_profile_fields_for_capability "$capability_id" out_ref
        ;;
    esac
  done

  if [ "$adapter" = "direct-platform" ] && direct_platform_xvfb_enabled; then
    collect_direct_platform_xvfb_required_profile_fields out_ref
  fi

  if [ "$adapter" = "direct-platform" ] && direct_platform_ld_preload_enabled; then
    collect_direct_platform_ld_preload_required_profile_fields out_ref
  fi
}

doctor_capability_failure_reason() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local binary_path=""
  local infobase_mode=""
  local infobase_auth_mode=""
  local command_reason=""
  local -a profile_command=()

  validate_capability_command_driver_contract "$capability_id"
  if capability_has_profile_unsupported_reason "$capability_id"; then
    require_profile_string "$(capability_unsupported_reason_expr "$capability_id") // empty" "$(capability_unsupported_reason_expr "$capability_id")"
    return 0
  fi

  if capability_has_profile_command "$capability_id"; then
    load_profile_command_array "$capability_id" profile_command
    set -- "${profile_command[@]}"
    if [ "$#" -eq 0 ]; then
      printf 'empty %s\n' "$(capability_command_expr "$capability_id")"
      return 0
    fi

    command_reason="$(direct_platform_adapter_failure_reason_for_command_path "$adapter" "${profile_command[0]}")"
    printf '%s\n' "$command_reason"
    return 0
  fi

  case "$capability_id" in
    create-ib|dump-src|load-src|update-db)
      driver="$(resolve_capability_driver "$capability_id")"
      case "$driver" in
        designer)
          case "$adapter" in
            direct-platform|remote-windows)
              ;;
            *)
              printf 'driver=designer is unsupported with runnerAdapter=%s\n' "$adapter"
              return 0
              ;;
          esac

          binary_path="$(profile_string '.platform.binaryPath // empty')"
          [ -n "$binary_path" ] || {
            printf 'missing platform.binaryPath\n'
            return 0
          }

          infobase_mode="$(profile_string '.infobase.mode // empty')"
          case "$infobase_mode" in
            file)
              profile_has_nonnull '.infobase.filePath' || {
                printf 'missing infobase.filePath for infobase.mode=file\n'
                return 0
              }
              ;;
            client-server)
              profile_has_nonnull '.infobase.server' || {
                printf 'missing infobase.server for infobase.mode=client-server\n'
                return 0
              }
              profile_has_nonnull '.infobase.ref' || {
                printf 'missing infobase.ref for infobase.mode=client-server\n'
                return 0
              }
              ;;
            "")
              printf 'missing infobase.mode\n'
              return 0
              ;;
            *)
              printf 'unsupported infobase.mode=%s\n' "$infobase_mode"
              return 0
              ;;
          esac

          infobase_auth_mode="$(profile_string '.infobase.auth.mode // "os"')"
          case "$infobase_auth_mode" in
            os)
              ;;
            user-password)
              profile_has_nonnull '.infobase.auth.user' || {
                printf 'missing infobase.auth.user for infobase.auth.mode=user-password\n'
                return 0
              }
              profile_has_nonnull '.infobase.auth.passwordEnv' || {
                printf 'missing infobase.auth.passwordEnv for infobase.auth.mode=user-password\n'
                return 0
              }
              ;;
            *)
              printf 'unsupported infobase.auth.mode=%s\n' "$infobase_auth_mode"
              return 0
              ;;
          esac

          command_reason="$(direct_platform_adapter_failure_reason_for_command_path "$adapter" "$binary_path")"
          if [ -n "$command_reason" ]; then
            printf '%s\n' "$command_reason"
            return 0
          fi
          ;;
        ibcmd)
          printf '%s\n' "$(ibcmd_capability_failure_reason "$capability_id" "$adapter")"
          return 0
          ;;
        *)
          printf 'unsupported driver=%s for capability %s\n' "$driver" "$capability_id"
          return 0
          ;;
      esac
      ;;
    diff-src)
      if capability_has_profile_command "$capability_id"; then
        load_profile_command_array "$capability_id" profile_command
        set -- "${profile_command[@]}"
        if [ "$#" -eq 0 ]; then
          printf 'empty %s\n' "$(capability_command_expr "$capability_id")"
          return 0
        fi

        command_reason="$(direct_platform_adapter_failure_reason_for_command_path "$adapter" "${profile_command[0]}")"
        printf '%s\n' "$command_reason"
        return 0
      fi
      ;;
    run-xunit|run-bdd|run-smoke|publish-http)
      if ! capability_has_profile_command "$capability_id"; then
        printf 'missing %s\n' "$(capability_command_expr "$capability_id")"
        return 0
      fi

      load_profile_command_array "$capability_id" profile_command
      set -- "${profile_command[@]}"
      if [ "$#" -eq 0 ]; then
        printf 'empty %s\n' "$(capability_command_expr "$capability_id")"
        return 0
      fi

      command_reason="$(direct_platform_adapter_failure_reason_for_command_path "$adapter" "${profile_command[0]}")"
      printf '%s\n' "$command_reason"
      return 0
      ;;
    *)
      printf 'unsupported capability id: %s\n' "$capability_id"
      return 0
      ;;
  esac

  printf '\n'
}

build_doctor_capability_drivers_json() {
  local adapter="$1"
  local capability_id=""
  local status="present"
  local driver=""
  local source="driver-selection"
  local reason=""
  local context_json="{}"
  local item_json="{}"
  local result='{}'

  require_command jq

  for capability_id in create-ib dump-src load-src update-db; do
    validate_capability_command_driver_contract "$capability_id"
    reason=""
    if capability_has_profile_unsupported_reason "$capability_id"; then
      source="unsupported-profile"
      driver=""
      reason="$(require_profile_string "$(capability_unsupported_reason_expr "$capability_id") // empty" "$(capability_unsupported_reason_expr "$capability_id")")"
      context_json="$(jq -cn --arg reason "$reason" '{unsupported: {placeholder: true, reason: $reason}}')"
    elif capability_has_profile_command "$capability_id"; then
      source="profile-command"
      driver=""
      context_json='{}'
    else
      source="driver-selection"
      driver="$(resolve_capability_driver "$capability_id")"
      context_json="$(build_doctor_driver_context_json "$capability_id" "$driver")"
    fi

    if [ -z "$reason" ]; then
      reason="$(doctor_capability_failure_reason "$capability_id" "$adapter")"
    fi
    status="present"
    if [ -n "$reason" ]; then
      status="missing"
    fi

    item_json="$(jq -cn \
      --arg status "$status" \
      --arg source "$source" \
      --arg driver "$driver" \
      --arg reason "$reason" \
      --argjson context "$context_json" \
      '{
        status: $status,
        source: $source,
        driver: (if $driver == "" then null else $driver end),
        reason: (if $reason == "" then null else $reason end),
        context: $context
      }')"
    result="$(jq -cn \
      --argjson acc "$result" \
      --arg capability_id "$capability_id" \
      --argjson item "$item_json" \
      '$acc + {($capability_id): $item}')"
  done

  printf '%s\n' "$result"
}

doctor_has_required_capability() {
  local capability_id="$1"
  local adapter="$2"
  [ -z "$(doctor_capability_failure_reason "$capability_id" "$adapter")" ]
}

prepare_adapter_wrapper_env() {
  local adapter="$1"
  local array_name="$2"
  local server_args_string=""
  local -a server_args=()
  local ld_preload_string=""
  local -a ld_preload_libraries=()
  local -n out_ref="$array_name"

  out_ref=()
  if [ "$adapter" != "direct-platform" ]; then
    return 0
  fi

  if direct_platform_xvfb_enabled; then
    load_direct_platform_xvfb_server_args server_args
    server_args_string="$(join_named_array_with_spaces server_args)"
    out_ref+=("ONEC_DIRECT_PLATFORM_XVFB_ENABLED=1")
    out_ref+=("ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS=$server_args_string")
  fi

  if direct_platform_ld_preload_enabled; then
    load_direct_platform_ld_preload_libraries ld_preload_libraries
    ld_preload_string="$(join_named_array_with_colons ld_preload_libraries)"
    out_ref+=("ONEC_DIRECT_PLATFORM_LD_PRELOAD_ENABLED=1")
    out_ref+=("ONEC_DIRECT_PLATFORM_LD_PRELOAD=$ld_preload_string")
  fi
}
