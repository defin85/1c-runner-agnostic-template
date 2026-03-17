#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"
# shellcheck source=./runtime-profile.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-profile.sh"
# shellcheck source=./capability.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/capability.sh"

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

set_prepared_context_from_profile() {
  set_capability_context_json "$(build_redacted_context_json)"
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
  local -a profile_command=()

  if ! capability_has_profile_command "$capability_id"; then
    return 1
  fi

  load_profile_command_array "$capability_id" profile_command
  if [ "${profile_command[*]-}" = "" ]; then
    die "runtime profile capability command must not be empty: $(capability_command_expr "$capability_id")"
  fi

  set_prepared_capability_command "profile-command" "direct" "${profile_command[@]}"
  set_prepared_context_from_profile
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
  local connection_string=""
  local binary_path=""

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.createIb.command for adapter $adapter"
      ;;
  esac

  binary_path="$(platform_binary_path)"
  connection_string="$(build_create_infobase_connection_string)"
  set_prepared_capability_command "standard-builder" "adapter-wrapper" "$binary_path" "CREATEINFOBASE" "$connection_string"
  set_prepared_context_from_profile
}

prepare_dump_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local output_dir=""
  local -a command=()

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.dumpSrc.command for adapter $adapter"
      ;;
  esac

  output_dir="$(capability_string_or_default "$capability_id" "outputDir" "./src/cf")"
  build_designer_command command "/DumpConfigToFiles" "$output_dir"
  set_prepared_capability_command "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile
}

prepare_load_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local source_dir=""
  local -a command=()

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.loadSrc.command for adapter $adapter"
      ;;
  esac

  source_dir="$(capability_string_or_default "$capability_id" "sourceDir" "./src/cf")"
  build_designer_command command "/LoadConfigFromFiles" "$source_dir"
  set_prepared_capability_command "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile
}

prepare_update_db_command() {
  local capability_id="$1"
  local adapter="$2"
  local -a command=()

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  case "$adapter" in
    direct-platform|remote-windows)
      ;;
    *)
      die "capability $capability_id requires capabilities.updateDb.command for adapter $adapter"
      ;;
  esac

  build_designer_command command "/UpdateDBCfg"
  set_prepared_capability_command "standard-builder" "adapter-wrapper" "${command[@]}"
  set_prepared_context_from_profile
}

prepare_diff_src_command() {
  local capability_id="$1"
  local _adapter="$2"

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  set_prepared_capability_command "builtin-command" "direct" git diff -- ./src
  set_prepared_context_from_profile
}

prepare_required_profile_command() {
  local capability_id="$1"
  local _adapter="$2"

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  die "runtime profile is missing $(capability_command_expr "$capability_id") in $RUNTIME_PROFILE_PATH"
}

collect_required_env_refs() {
  local array_name="$1"
  local -n out_ref="$array_name"
  local ref=""

  out_ref=()

  for ref in \
    "$(profile_string '.infobase.auth.passwordEnv // empty')" \
    "$(profile_string '.dbms.passwordEnv // empty')" \
    "$(profile_string '.clusterAdmin.passwordEnv // empty')"; do
    if [ -n "$ref" ]; then
      out_ref+=("$ref")
    fi
  done
}

collect_required_profile_fields() {
  local adapter="$1"
  local array_name="$2"
  local mode=""
  local -n out_ref="$array_name"

  out_ref=(runnerAdapter)
  mode="$(profile_string '.infobase.mode // empty')"

  case "$adapter" in
    direct-platform|remote-windows)
      out_ref+=(platform.binaryPath infobase.mode)
      case "$mode" in
        file)
          out_ref+=(infobase.filePath)
          ;;
        client-server)
          out_ref+=(infobase.server infobase.ref)
          ;;
      esac
      ;;
    vrunner)
      out_ref+=(infobase.mode)
      ;;
  esac

  if [ "$(profile_string '.infobase.auth.mode // "os"')" = "user-password" ]; then
    out_ref+=(infobase.auth.user infobase.auth.passwordEnv)
  fi
}

doctor_has_required_capability() {
  local capability_id="$1"
  local adapter="$2"

  if capability_has_profile_command "$capability_id"; then
    return 0
  fi

  case "$capability_id" in
    create-ib|dump-src|load-src|update-db)
      case "$adapter" in
        direct-platform|remote-windows)
          profile_has_nonnull '.platform.binaryPath' || return 1
          if [ "$(profile_string '.infobase.mode // empty')" = "file" ]; then
            profile_has_nonnull '.infobase.filePath'
          else
            profile_has_nonnull '.infobase.server' && profile_has_nonnull '.infobase.ref'
          fi
          ;;
        *)
          return 1
          ;;
      esac
      ;;
    diff-src)
      return 0
      ;;
    run-xunit|run-bdd|run-smoke)
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}
