#!/usr/bin/env bash
set -euo pipefail

ibcmd_binary_path() {
  require_profile_string '.platform.ibcmdPath // empty' 'platform.ibcmdPath'
}

ibcmd_runtime_mode() {
  require_profile_string '.ibcmd.runtimeMode // empty' 'ibcmd.runtimeMode'
}

ibcmd_server_access_mode() {
  require_profile_string '.ibcmd.serverAccess.mode // empty' 'ibcmd.serverAccess.mode'
}

ibcmd_server_access_data_dir() {
  require_profile_string '.ibcmd.serverAccess.dataDir // empty' 'ibcmd.serverAccess.dataDir'
}

ibcmd_database_path_field_name() {
  case "$1" in
    standalone-server)
      printf 'ibcmd.standalone.databasePath\n'
      ;;
    file-infobase)
      printf 'ibcmd.fileInfobase.databasePath\n'
      ;;
    *)
      die "runtime mode does not expose databasePath field: $1"
      ;;
  esac
}

ibcmd_require_database_path_for_mode() {
  local runtime_mode="$1"
  local expr=""
  local field_name=""

  case "$runtime_mode" in
    standalone-server)
      expr='.ibcmd.standalone.databasePath // empty'
      ;;
    file-infobase)
      expr='.ibcmd.fileInfobase.databasePath // empty'
      ;;
    *)
      die "runtime mode does not expose databasePath field: $runtime_mode"
      ;;
  esac

  field_name="$(ibcmd_database_path_field_name "$runtime_mode")"
  require_profile_string "$expr" "$field_name"
}

ibcmd_require_infobase_auth_user() {
  require_profile_string '.ibcmd.auth.user // empty' 'ibcmd.auth.user'
}

ibcmd_require_infobase_auth_password_env() {
  require_profile_string '.ibcmd.auth.passwordEnv // empty' 'ibcmd.auth.passwordEnv'
}

ibcmd_require_dbms_kind() {
  require_profile_string '.ibcmd.dbmsInfobase.kind // empty' 'ibcmd.dbmsInfobase.kind'
}

ibcmd_require_dbms_server() {
  require_profile_string '.ibcmd.dbmsInfobase.server // empty' 'ibcmd.dbmsInfobase.server'
}

ibcmd_require_dbms_name() {
  require_profile_string '.ibcmd.dbmsInfobase.name // empty' 'ibcmd.dbmsInfobase.name'
}

ibcmd_require_dbms_user() {
  require_profile_string '.ibcmd.dbmsInfobase.user // empty' 'ibcmd.dbmsInfobase.user'
}

ibcmd_require_dbms_password_env() {
  require_profile_string '.ibcmd.dbmsInfobase.passwordEnv // empty' 'ibcmd.dbmsInfobase.passwordEnv'
}

ibcmd_runtime_mode_context_json() {
  local runtime_mode="$1"
  local context='{}'
  local database_path=""
  local kind=""
  local server=""
  local name=""
  local user=""
  local password_env=""

  require_command jq

  case "$runtime_mode" in
    standalone-server)
      database_path="$(profile_string '.ibcmd.standalone.databasePath // empty')"
      context="$(jq -cn \
        --arg runtime_mode "$runtime_mode" \
        --arg database_path "$database_path" \
        '{
          topology: {
            kind: $runtime_mode,
            database_path: (if $database_path == "" then null else $database_path end)
          }
        }')"
      ;;
    file-infobase)
      database_path="$(profile_string '.ibcmd.fileInfobase.databasePath // empty')"
      context="$(jq -cn \
        --arg runtime_mode "$runtime_mode" \
        --arg database_path "$database_path" \
        '{
          topology: {
            kind: $runtime_mode,
            database_path: (if $database_path == "" then null else $database_path end)
          }
        }')"
      ;;
    dbms-infobase)
      kind="$(profile_string '.ibcmd.dbmsInfobase.kind // empty')"
      server="$(profile_string '.ibcmd.dbmsInfobase.server // empty')"
      name="$(profile_string '.ibcmd.dbmsInfobase.name // empty')"
      user="$(profile_string '.ibcmd.dbmsInfobase.user // empty')"
      password_env="$(profile_string '.ibcmd.dbmsInfobase.passwordEnv // empty')"
      context="$(jq -cn \
        --arg kind "$kind" \
        --arg server "$server" \
        --arg name "$name" \
        --arg user "$user" \
        --arg password_env "$password_env" \
        '{
          topology: {
            kind: "dbms-infobase",
            dbms: {
              kind: (if $kind == "" then null else $kind end),
              server: (if $server == "" then null else $server end),
              name: (if $name == "" then null else $name end),
              user: (if $user == "" then null else $user end),
              password_configured: ($password_env != "")
            }
          }
        }')"
      ;;
    *)
      printf '{}\n'
      return 0
      ;;
  esac

  printf '%s\n' "$context"
}

build_ibcmd_capability_context_json() {
  local partial_import="${1:-false}"
  local mode=""
  local auth_mode=""
  local server=""
  local ref=""
  local file_path=""
  local profile_name=""
  local runtime_mode=""
  local server_access_mode=""
  local server_access_data_dir=""
  local runtime_mode_context='{}'

  mode="$(profile_string '.infobase.mode // empty')"
  auth_mode="$(profile_string '.infobase.auth.mode // "os"')"
  server="$(profile_string '.infobase.server // empty')"
  ref="$(profile_string '.infobase.ref // empty')"
  file_path="$(profile_string '.infobase.filePath // empty')"
  profile_name="$(profile_string '.profileName // empty')"
  runtime_mode="$(profile_string '.ibcmd.runtimeMode // empty')"
  server_access_mode="$(profile_string '.ibcmd.serverAccess.mode // empty')"
  server_access_data_dir="$(profile_string '.ibcmd.serverAccess.dataDir // empty')"
  runtime_mode_context="$(ibcmd_runtime_mode_context_json "$runtime_mode")"

  jq -cn \
    --arg profile_name "$profile_name" \
    --arg mode "$mode" \
    --arg server "$server" \
    --arg ref "$ref" \
    --arg file_path "$file_path" \
    --arg auth_mode "$auth_mode" \
    --arg runtime_mode "$runtime_mode" \
    --arg server_access_mode "$server_access_mode" \
    --arg server_access_data_dir "$server_access_data_dir" \
    --argjson partial_import "$partial_import" \
    --argjson runtime_mode_context "$runtime_mode_context" \
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
      },
      driver_context: ({
        runtime_mode: (if $runtime_mode == "" then null else $runtime_mode end),
        server_access: {
          mode: (if $server_access_mode == "" then null else $server_access_mode end),
          data_dir: (if $server_access_data_dir == "" then null else $server_access_data_dir end)
        },
        partial_import: $partial_import
      } + $runtime_mode_context)
    }'
}

append_ibcmd_server_access_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local access_mode=""
  local data_dir=""

  access_mode="$(ibcmd_server_access_mode)"
  case "$access_mode" in
    data-dir)
      data_dir="$(ibcmd_server_access_data_dir)"
      args_ref+=("--data=$data_dir")
      ;;
    *)
      die "unsupported ibcmd.serverAccess.mode=$access_mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

append_ibcmd_target_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local runtime_mode=""
  local database_path=""
  local dbms_password_env=""
  local dbms_password_value=""

  runtime_mode="$(ibcmd_runtime_mode)"
  case "$runtime_mode" in
    standalone-server|file-infobase)
      database_path="$(ibcmd_require_database_path_for_mode "$runtime_mode")"
      args_ref+=("--database-path=$database_path")
      ;;
    dbms-infobase)
      dbms_password_env="$(ibcmd_require_dbms_password_env)"
      dbms_password_value="$(resolve_secret_value "$dbms_password_env")"
      args_ref+=(
        "--dbms=$(ibcmd_require_dbms_kind)"
        "--db-server=$(ibcmd_require_dbms_server)"
        "--db-name=$(ibcmd_require_dbms_name)"
        "--db-user=$(ibcmd_require_dbms_user)"
        "--db-pwd=$dbms_password_value"
      )
      ;;
    *)
      die "unsupported ibcmd.runtimeMode=$runtime_mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

append_ibcmd_infobase_auth_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local password_env=""
  local password_value=""

  password_env="$(ibcmd_require_infobase_auth_password_env)"
  password_value="$(resolve_secret_value "$password_env")"
  args_ref+=(
    "--user=$(ibcmd_require_infobase_auth_user)"
    "--password=$password_value"
  )
}

ibcmd_capability_failure_reason() {
  local capability_id="$1"
  local adapter="$2"
  local runtime_mode=""
  local access_mode=""

  if [ "$adapter" != "direct-platform" ]; then
    printf 'ibcmd driver is supported only with runnerAdapter=direct-platform\n'
    return 0
  fi

  profile_has_nonnull '.platform.ibcmdPath' || {
    printf 'missing platform.ibcmdPath\n'
    return 0
  }

  runtime_mode="$(profile_string '.ibcmd.runtimeMode // empty')"
  if [ -z "$runtime_mode" ]; then
    printf 'missing ibcmd.runtimeMode\n'
    return 0
  fi

  case "$runtime_mode" in
    standalone-server|file-infobase|dbms-infobase)
      ;;
    *)
      printf 'ibcmd.runtimeMode=%s is unsupported; use standalone-server, file-infobase, or dbms-infobase\n' "$runtime_mode"
      return 0
      ;;
  esac

  access_mode="$(profile_string '.ibcmd.serverAccess.mode // empty')"
  if [ -z "$access_mode" ]; then
    printf 'missing ibcmd.serverAccess.mode\n'
    return 0
  fi
  if [ "$access_mode" != "data-dir" ]; then
      printf 'ibcmd.serverAccess.mode=%s is unsupported in the current release; use data-dir\n' "$access_mode"
      return 0
  fi

  profile_has_nonnull '.ibcmd.serverAccess.dataDir' || {
    printf 'missing ibcmd.serverAccess.dataDir\n'
    return 0
  }

  case "$runtime_mode" in
    standalone-server)
      profile_has_nonnull '.ibcmd.standalone.databasePath' || {
        printf 'missing ibcmd.standalone.databasePath\n'
        return 0
      }
      ;;
    file-infobase)
      profile_has_nonnull '.ibcmd.fileInfobase.databasePath' || {
        printf 'missing ibcmd.fileInfobase.databasePath\n'
        return 0
      }
      ;;
    dbms-infobase)
      profile_has_nonnull '.ibcmd.dbmsInfobase.kind' || {
        printf 'missing ibcmd.dbmsInfobase.kind\n'
        return 0
      }
      profile_has_nonnull '.ibcmd.dbmsInfobase.server' || {
        printf 'missing ibcmd.dbmsInfobase.server\n'
        return 0
      }
      profile_has_nonnull '.ibcmd.dbmsInfobase.name' || {
        printf 'missing ibcmd.dbmsInfobase.name\n'
        return 0
      }
      profile_has_nonnull '.ibcmd.dbmsInfobase.user' || {
        printf 'missing ibcmd.dbmsInfobase.user\n'
        return 0
      }
      profile_has_nonnull '.ibcmd.dbmsInfobase.passwordEnv' || {
        printf 'missing ibcmd.dbmsInfobase.passwordEnv\n'
        return 0
      }
      ;;
  esac

  case "$capability_id" in
    create-ib)
      ;;
    dump-src|load-src|update-db)
      profile_has_nonnull '.ibcmd.auth.user' || {
        printf 'missing ibcmd.auth.user\n'
        return 0
      }
      profile_has_nonnull '.ibcmd.auth.passwordEnv' || {
        printf 'missing ibcmd.auth.passwordEnv\n'
        return 0
      }
      ;;
    *)
      printf 'unsupported capability id for ibcmd driver: %s\n' "$capability_id"
      return 0
      ;;
  esac

  printf '\n'
}

validate_ibcmd_capability_support() {
  local capability_id="$1"
  local adapter="$2"
  local reason=""

  reason="$(ibcmd_capability_failure_reason "$capability_id" "$adapter")"
  if [ -n "$reason" ]; then
    die "$reason"
  fi
}

collect_ibcmd_required_profile_fields_for_capability() {
  local capability_id="$1"
  local array_name="$2"
  local runtime_mode=""

  append_unique_field "$array_name" platform.ibcmdPath
  append_unique_field "$array_name" ibcmd.runtimeMode
  append_unique_field "$array_name" ibcmd.serverAccess.mode
  append_unique_field "$array_name" ibcmd.serverAccess.dataDir

  runtime_mode="$(profile_string '.ibcmd.runtimeMode // empty')"
  case "$runtime_mode" in
    standalone-server)
      append_unique_field "$array_name" ibcmd.standalone.databasePath
      ;;
    file-infobase)
      append_unique_field "$array_name" ibcmd.fileInfobase.databasePath
      ;;
    dbms-infobase)
      append_unique_field "$array_name" ibcmd.dbmsInfobase.kind
      append_unique_field "$array_name" ibcmd.dbmsInfobase.server
      append_unique_field "$array_name" ibcmd.dbmsInfobase.name
      append_unique_field "$array_name" ibcmd.dbmsInfobase.user
      append_unique_field "$array_name" ibcmd.dbmsInfobase.passwordEnv
      ;;
  esac

  case "$capability_id" in
    dump-src|load-src|update-db)
      append_unique_field "$array_name" ibcmd.auth.user
      append_unique_field "$array_name" ibcmd.auth.passwordEnv
      ;;
  esac
}

collect_ibcmd_required_env_refs_for_capability() {
  local capability_id="$1"
  local array_name="$2"
  local runtime_mode=""
  local ref=""

  runtime_mode="$(profile_string '.ibcmd.runtimeMode // empty')"
  if [ "$runtime_mode" = "dbms-infobase" ]; then
    ref="$(profile_string '.ibcmd.dbmsInfobase.passwordEnv // empty')"
    if [ -n "$ref" ]; then
      append_unique_field "$array_name" "$ref"
    fi
  fi

  case "$capability_id" in
    dump-src|load-src|update-db)
      ref="$(profile_string '.ibcmd.auth.passwordEnv // empty')"
      if [ -n "$ref" ]; then
        append_unique_field "$array_name" "$ref"
      fi
      ;;
  esac
}

prepare_ibcmd_create_ib_command() {
  local capability_id="$1"
  local adapter="$2"
  local binary_path=""
  local -a command=()

  validate_ibcmd_capability_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"

  command=("$binary_path" "infobase" "create")
  append_ibcmd_server_access_args command
  append_ibcmd_target_args command
  command+=("--create-database")

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json false)"
}

prepare_ibcmd_dump_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local output_dir="$3"
  local binary_path=""
  local -a command=()

  validate_ibcmd_capability_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"

  command=("$binary_path" "config" "export")
  append_ibcmd_server_access_args command
  append_ibcmd_target_args command
  append_ibcmd_infobase_auth_args command
  command+=("$output_dir")

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json false)"
}

prepare_ibcmd_load_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local source_dir="$3"
  local binary_path=""
  local partial_import="false"
  local -a selected_files=()
  local -a command=()

  validate_ibcmd_capability_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"
  load_capability_selected_files selected_files

  set -- "${selected_files[@]}"
  if [ "$#" -gt 0 ]; then
    partial_import="true"
    command=("$binary_path" "config" "import" "files")
    append_ibcmd_server_access_args command
    append_ibcmd_target_args command
    append_ibcmd_infobase_auth_args command
    command+=("--base-dir=$source_dir" "--partial")
    command+=("${selected_files[@]}")
  else
    command=("$binary_path" "config" "import")
    append_ibcmd_server_access_args command
    append_ibcmd_target_args command
    append_ibcmd_infobase_auth_args command
    command+=("$source_dir")
  fi

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json "$partial_import")"
}

prepare_ibcmd_update_db_command() {
  local capability_id="$1"
  local adapter="$2"
  local binary_path=""
  local -a command=()

  validate_ibcmd_capability_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"

  command=("$binary_path" "config" "apply")
  append_ibcmd_server_access_args command
  append_ibcmd_target_args command
  append_ibcmd_infobase_auth_args command
  command+=("--force")

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json false)"
}
