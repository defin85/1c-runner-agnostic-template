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

capability_has_profile_driver() {
  profile_has_nonnull "$(capability_driver_expr "$1")"
}

validate_capability_command_driver_contract() {
  local capability_id="$1"
  local has_command=1
  local has_driver=1

  if capability_has_profile_command "$capability_id"; then
    has_command=0
  fi

  if capability_has_profile_driver "$capability_id"; then
    has_driver=0
  fi

  if [ "$has_command" -eq 0 ] && [ "$has_driver" -eq 0 ]; then
    die "capability $capability_id must not define both driver and command in $RUNTIME_PROFILE_PATH"
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

set_prepared_context_from_profile() {
  set_capability_context_json "$(build_redacted_context_json)"
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
      jq -cn \
        --arg capability_id "$capability_id" \
        --argjson context "$ibcmd_context" \
        '$context + (if $capability_id == "load-src" then {partial_import_supported: true} else {} end)'
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
  local -a profile_command=()

  validate_capability_command_driver_contract "$capability_id"
  if ! capability_has_profile_command "$capability_id"; then
    return 1
  fi

  load_profile_command_array "$capability_id" profile_command
  if [ "${profile_command[*]-}" = "" ]; then
    die "runtime profile capability command must not be empty: $(capability_command_expr "$capability_id")"
  fi

  set_prepared_capability_command "" "profile-command" "direct" "${profile_command[@]}"
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
  local driver=""
  local connection_string=""
  local binary_path=""

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_command "$capability_id"; then
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
  set_prepared_context_from_profile
}

prepare_dump_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local output_dir=""
  local -a command=()

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  output_dir="$(capability_string_or_default "$capability_id" "outputDir" "./src/cf")"
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
  set_prepared_context_from_profile
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

  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  driver="$(resolve_capability_driver "$capability_id")"
  source_dir="$(capability_string_or_default "$capability_id" "sourceDir" "./src/cf")"
  if capability_selected_files_requested && [ "$driver" != "ibcmd" ]; then
    die "partial load-src is supported only for ibcmd driver in phase 1"
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
  set_prepared_context_from_profile
}

prepare_update_db_command() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local -a command=()

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_command "$capability_id"; then
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
  set_prepared_context_from_profile
}

prepare_diff_src_command() {
  local capability_id="$1"
  local _adapter="$2"

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_command "$capability_id"; then
    return 0
  fi

  set_prepared_capability_command "" "builtin-command" "direct" git diff -- ./src
  set_prepared_context_from_profile
}

prepare_required_profile_command() {
  local capability_id="$1"
  local _adapter="$2"

  reject_capability_selected_files "$capability_id"
  if maybe_use_profile_command "$capability_id"; then
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
    if capability_has_profile_command "$capability_id"; then
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
        ref="$(profile_string '.ibcmd.auth.passwordEnv // empty')"
        if [ -n "$ref" ]; then
          append_unique_field env_refs "$ref"
        fi
        ;;
    esac
  done
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

collect_ibcmd_required_profile_fields() {
  local array_name="$1"
  local create_driver=""

  append_unique_field "$array_name" platform.ibcmdPath
  append_unique_field "$array_name" ibcmd.connectionMode
  append_unique_field "$array_name" ibcmd.dataDir
  append_unique_field "$array_name" ibcmd.auth.user
  append_unique_field "$array_name" ibcmd.auth.passwordEnv

  create_driver="$(resolve_capability_driver "create-ib")"
  if [ "$create_driver" = "ibcmd" ]; then
    append_unique_field "$array_name" ibcmd.databasePath
  fi
}

collect_required_profile_fields() {
  local adapter="$1"
  local array_name="$2"
  local capability_id=""
  local driver=""
  local designer_required=1
  local ibcmd_required=1
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
    if capability_has_profile_command "$capability_id"; then
      continue
    fi

    driver="$(resolve_capability_driver "$capability_id")"
    case "$driver" in
      designer)
        designer_required=0
        ;;
      ibcmd)
        ibcmd_required=0
        ;;
    esac
  done

  if [ "$designer_required" -eq 0 ]; then
    collect_designer_required_profile_fields out_ref
  fi

  if [ "$ibcmd_required" -eq 0 ]; then
    collect_ibcmd_required_profile_fields out_ref
  fi
}

doctor_capability_failure_reason() {
  local capability_id="$1"
  local adapter="$2"
  local driver=""
  local infobase_mode=""
  local infobase_auth_mode=""
  local connection_mode=""

  validate_capability_command_driver_contract "$capability_id"
  if capability_has_profile_command "$capability_id"; then
    printf '\n'
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

          profile_has_nonnull '.platform.binaryPath' || {
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
          ;;
        ibcmd)
          if [ "$adapter" != "direct-platform" ]; then
            printf 'ibcmd driver is supported only with runnerAdapter=direct-platform in phase 1\n'
            return 0
          fi

          profile_has_nonnull '.platform.ibcmdPath' || {
            printf 'missing platform.ibcmdPath\n'
            return 0
          }

          connection_mode="$(profile_string '.ibcmd.connectionMode // empty')"
          if [ -z "$connection_mode" ]; then
            printf 'missing ibcmd.connectionMode\n'
            return 0
          fi
          if [ "$connection_mode" != "data-dir" ]; then
            printf 'ibcmd.connectionMode=%s is not supported in phase 1; use data-dir\n' "$connection_mode"
            return 0
          fi

          profile_has_nonnull '.ibcmd.dataDir' || {
            printf 'missing ibcmd.dataDir\n'
            return 0
          }
          profile_has_nonnull '.ibcmd.auth.user' || {
            printf 'missing ibcmd.auth.user\n'
            return 0
          }
          profile_has_nonnull '.ibcmd.auth.passwordEnv' || {
            printf 'missing ibcmd.auth.passwordEnv\n'
            return 0
          }

          if [ "$capability_id" = "create-ib" ] && ! profile_has_nonnull '.ibcmd.databasePath'; then
            printf 'missing ibcmd.databasePath for create-ib with driver=ibcmd\n'
            return 0
          fi
          ;;
        *)
          printf 'unsupported driver=%s for capability %s\n' "$driver" "$capability_id"
          return 0
          ;;
      esac
      ;;
    diff-src)
      ;;
    run-xunit|run-bdd|run-smoke|publish-http)
      printf 'missing %s\n' "$(capability_command_expr "$capability_id")"
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
    if capability_has_profile_command "$capability_id"; then
      source="profile-command"
      driver=""
      context_json='{}'
    else
      source="driver-selection"
      driver="$(resolve_capability_driver "$capability_id")"
      context_json="$(build_doctor_driver_context_json "$capability_id" "$driver")"
    fi

    reason="$(doctor_capability_failure_reason "$capability_id" "$adapter")"
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
