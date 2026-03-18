#!/usr/bin/env bash
set -euo pipefail

ibcmd_binary_path() {
  require_profile_string '.platform.ibcmdPath // empty' 'platform.ibcmdPath'
}

ibcmd_connection_mode() {
  require_profile_string '.ibcmd.connectionMode // empty' 'ibcmd.connectionMode'
}

validate_ibcmd_phase1_support() {
  local capability_id="$1"
  local adapter="$2"
  local connection_mode=""

  if [ "$adapter" != "direct-platform" ]; then
    die "ibcmd driver is supported only with runnerAdapter=direct-platform in phase 1: capability $capability_id"
  fi

  connection_mode="$(ibcmd_connection_mode)"
  if [ "$connection_mode" != "data-dir" ]; then
    die "ibcmd.connectionMode=$connection_mode is not supported in phase 1; use data-dir"
  fi
}

append_ibcmd_connection_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local connection_mode=""
  local data_dir=""

  connection_mode="$(ibcmd_connection_mode)"
  case "$connection_mode" in
    data-dir)
      data_dir="$(require_profile_string '.ibcmd.dataDir // empty' 'ibcmd.dataDir')"
      args_ref+=("--data=$data_dir")
      ;;
    *)
      die "unsupported ibcmd.connectionMode=$connection_mode in $RUNTIME_PROFILE_PATH"
      ;;
  esac
}

append_ibcmd_auth_args() {
  local array_name="$1"
  local -n args_ref="$array_name"
  local user=""
  local password_env=""
  local password_value=""

  user="$(require_profile_string '.ibcmd.auth.user // empty' 'ibcmd.auth.user')"
  password_env="$(require_profile_string '.ibcmd.auth.passwordEnv // empty' 'ibcmd.auth.passwordEnv')"
  password_value="$(resolve_secret_value "$password_env")"
  args_ref+=("--user=$user" "--password=$password_value")
}

build_ibcmd_capability_context_json() {
  local partial_import="${1:-false}"
  local mode=""
  local auth_mode=""
  local server=""
  local ref=""
  local file_path=""
  local profile_name=""
  local connection_mode=""
  local data_dir=""
  local database_path=""

  mode="$(profile_string '.infobase.mode // empty')"
  auth_mode="$(profile_string '.infobase.auth.mode // "os"')"
  server="$(profile_string '.infobase.server // empty')"
  ref="$(profile_string '.infobase.ref // empty')"
  file_path="$(profile_string '.infobase.filePath // empty')"
  profile_name="$(profile_string '.profileName // empty')"
  connection_mode="$(profile_string '.ibcmd.connectionMode // empty')"
  data_dir="$(profile_string '.ibcmd.dataDir // empty')"
  database_path="$(profile_string '.ibcmd.databasePath // empty')"

  jq -cn \
    --arg profile_name "$profile_name" \
    --arg mode "$mode" \
    --arg server "$server" \
    --arg ref "$ref" \
    --arg file_path "$file_path" \
    --arg auth_mode "$auth_mode" \
    --arg connection_mode "$connection_mode" \
    --arg data_dir "$data_dir" \
    --arg database_path "$database_path" \
    --argjson partial_import "$partial_import" \
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
      driver_context: {
        connection_mode: (if $connection_mode == "" then null else $connection_mode end),
        data_dir: (if $data_dir == "" then null else $data_dir end),
        database_path: (if $database_path == "" then null else $database_path end),
        partial_import: $partial_import
      }
    }'
}

prepare_ibcmd_create_ib_command() {
  local capability_id="$1"
  local adapter="$2"
  local binary_path=""
  local database_path=""
  local -a command=()

  validate_ibcmd_phase1_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"
  database_path="$(require_profile_string '.ibcmd.databasePath // empty' 'ibcmd.databasePath')"

  command=("$binary_path")
  append_ibcmd_connection_args command
  command+=("infobase" "create" "--database-path=$database_path" "--create-database")
  append_ibcmd_auth_args command

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json false)"
}

prepare_ibcmd_dump_src_command() {
  local capability_id="$1"
  local adapter="$2"
  local output_dir="$3"
  local binary_path=""
  local -a command=()

  validate_ibcmd_phase1_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"

  command=("$binary_path")
  append_ibcmd_connection_args command
  command+=("config" "export" "--dir=$output_dir" "--format=hierarchical")
  append_ibcmd_auth_args command

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

  validate_ibcmd_phase1_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"
  load_capability_selected_files selected_files

  command=("$binary_path")
  append_ibcmd_connection_args command

  set -- "${selected_files[@]}"
  if [ "$#" -gt 0 ]; then
    partial_import="true"
    command+=("config" "import" "files" "--base-dir=$source_dir" "--partial")
    append_ibcmd_auth_args command
    command+=("${selected_files[@]}")
  else
    command+=("config" "import" "--dir=$source_dir" "--format=hierarchical")
    append_ibcmd_auth_args command
  fi

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json "$partial_import")"
}

prepare_ibcmd_update_db_command() {
  local capability_id="$1"
  local adapter="$2"
  local binary_path=""
  local -a command=()

  validate_ibcmd_phase1_support "$capability_id" "$adapter"
  binary_path="$(ibcmd_binary_path)"

  command=("$binary_path")
  append_ibcmd_connection_args command
  command+=("config" "apply")
  append_ibcmd_auth_args command

  set_prepared_capability_command "ibcmd" "ibcmd-builder" "adapter-wrapper" "${command[@]}"
  set_capability_context_json "$(build_ibcmd_capability_context_json false)"
}
