#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/template/migrate-runtime-profile-v2.sh <legacy-profile.json>

Prints a best-effort schemaVersion 2 skeleton to stdout.
Review the result before replacing your local runtime profile.
EOF
}

legacy_string() {
  local profile_path="$1"
  local expr="$2"

  jq -r "$expr // empty" "$profile_path"
}

wrap_shell_command_json() {
  local command_string="$1"

  if [ -z "$command_string" ]; then
    printf 'null\n'
    return
  fi

  jq -cn --arg cmd "$command_string" '["bash", "-lc", $cmd]'
}

first_token() {
  local command_string="$1"

  if [ -z "$command_string" ]; then
    printf '\n'
    return
  fi

  awk '{print $1}' <<<"$command_string"
}

extract_switch_value() {
  local command_string="$1"
  local switch_name="$2"
  local raw_value=""

  raw_value="$(printf '%s\n' "$command_string" | grep -oE "/${switch_name}([[:space:]]+[^[:space:]]+|[^[:space:]]+)" | head -n 1 || true)"
  raw_value="${raw_value#/$switch_name}"
  raw_value="${raw_value# }"
  raw_value="${raw_value%\"}"
  raw_value="${raw_value#\"}"
  printf '%s\n' "$raw_value"
}

normalize_server_ref() {
  local value="$1"
  local server=""
  local ref=""

  if [ -z "$value" ]; then
    printf '\n\n'
    return
  fi

  if [[ "$value" == *\\* ]]; then
    server="${value%%\\*}"
    ref="${value#*\\}"
  elif [[ "$value" == */* ]]; then
    server="${value%%/*}"
    ref="${value#*/}"
  else
    server="$value"
    ref=""
  fi

  printf '%s\n%s\n' "$server" "$ref"
}

main() {
  local legacy_profile=""
  local schema_version=""
  local profile_name=""
  local project_name=""
  local project_slug=""
  local description=""
  local runner_adapter=""
  local create_cmd=""
  local dump_cmd=""
  local load_cmd=""
  local update_cmd=""
  local diff_cmd=""
  local xunit_cmd=""
  local bdd_cmd=""
  local smoke_cmd=""
  local publish_cmd=""
  local binary_path=""
  local s_value=""
  local server=""
  local ref=""
  local file_path=""
  local user=""
  local auth_mode="os"
  local password_env="null"
  local password_env_json="null"
  local xunit_json=""
  local bdd_json=""
  local smoke_json=""
  local publish_json=""
  local diff_json=""
  local notes_json="[]"

  if [ "$#" -ne 1 ]; then
    usage >&2
    exit 1
  fi

  legacy_profile="$1"
  require_command jq

  if [ ! -f "$legacy_profile" ]; then
    die "legacy profile not found: $legacy_profile"
  fi

  schema_version="$(jq -r '.schemaVersion // 1' "$legacy_profile")"
  if [ "$schema_version" != "1" ]; then
    die "migration helper expects schemaVersion=1 profile: $legacy_profile"
  fi

  profile_name="$(legacy_string "$legacy_profile" '.profileName')"
  project_name="$(legacy_string "$legacy_profile" '.projectName')"
  project_slug="$(legacy_string "$legacy_profile" '.projectSlug')"
  description="$(legacy_string "$legacy_profile" '.description')"
  runner_adapter="$(legacy_string "$legacy_profile" '.runnerAdapter')"
  create_cmd="$(legacy_string "$legacy_profile" '.shellEnv.CREATE_IB_CMD')"
  dump_cmd="$(legacy_string "$legacy_profile" '.shellEnv.DUMP_SRC_CMD')"
  load_cmd="$(legacy_string "$legacy_profile" '.shellEnv.LOAD_SRC_CMD')"
  update_cmd="$(legacy_string "$legacy_profile" '.shellEnv.UPDATE_DB_CMD')"
  diff_cmd="$(legacy_string "$legacy_profile" '.shellEnv.DIFF_SRC_CMD')"
  xunit_cmd="$(legacy_string "$legacy_profile" '.shellEnv.XUNIT_RUN_CMD')"
  bdd_cmd="$(legacy_string "$legacy_profile" '.shellEnv.BDD_RUN_CMD')"
  smoke_cmd="$(legacy_string "$legacy_profile" '.shellEnv.SMOKE_RUN_CMD')"
  publish_cmd="$(legacy_string "$legacy_profile" '.shellEnv.PUBLISH_HTTP_CMD')"

  binary_path="$(first_token "$load_cmd")"
  [ -n "$binary_path" ] || binary_path="$(first_token "$dump_cmd")"
  [ -n "$binary_path" ] || binary_path="$(first_token "$update_cmd")"
  [ -n "$binary_path" ] || binary_path="$(first_token "$create_cmd")"

  s_value="$(extract_switch_value "$load_cmd" 'S')"
  if [ -z "$s_value" ]; then
    s_value="$(extract_switch_value "$dump_cmd" 'S')"
  fi
  if [ -z "$s_value" ]; then
    s_value="$(extract_switch_value "$update_cmd" 'S')"
  fi

  if [ -n "$s_value" ]; then
    mapfile -t _server_ref < <(normalize_server_ref "$s_value")
    server="${_server_ref[0]:-}"
    ref="${_server_ref[1]:-}"
  fi

  file_path="$(extract_switch_value "$create_cmd" 'F')"
  user="$(extract_switch_value "$load_cmd" 'N')"
  if [ -z "$user" ]; then
    user="$(extract_switch_value "$dump_cmd" 'N')"
  fi
  if [ -z "$user" ]; then
    user="$(extract_switch_value "$update_cmd" 'N')"
  fi

  if [ -n "$user" ]; then
    auth_mode="user-password"
    password_env_json='"ONEC_IB_PASSWORD"'
  fi

  xunit_json="$(wrap_shell_command_json "$xunit_cmd")"
  bdd_json="$(wrap_shell_command_json "$bdd_cmd")"
  smoke_json="$(wrap_shell_command_json "$smoke_cmd")"
  publish_json="$(wrap_shell_command_json "$publish_cmd")"
  diff_json="$(wrap_shell_command_json "$diff_cmd")"

  jq -n \
    --arg profile_name "$profile_name" \
    --arg project_name "$project_name" \
    --arg project_slug "$project_slug" \
    --arg description "$description" \
    --arg runner_adapter "$runner_adapter" \
    --arg binary_path "$binary_path" \
    --arg server "$server" \
    --arg ref "$ref" \
    --arg file_path "$file_path" \
    --arg auth_mode "$auth_mode" \
    --arg user "$user" \
    --argjson password_env "$password_env_json" \
    --argjson notes "$notes_json" \
    --argjson diff_command "$diff_json" \
    --argjson xunit_command "$xunit_json" \
    --argjson bdd_command "$bdd_json" \
    --argjson smoke_command "$smoke_json" \
    --argjson publish_command "$publish_json" \
    '{
      schemaVersion: 2,
      profileName: $profile_name,
      projectName: (if $project_name == "" then null else $project_name end),
      projectSlug: (if $project_slug == "" then null else $project_slug end),
      description: (if $description == "" then null else $description end),
      runnerAdapter: (if $runner_adapter == "" then "direct-platform" else $runner_adapter end),
      notes: ($notes + ["Generated by migrate-runtime-profile-v2.sh. Review all fields before use."]),
      platform: {
        binaryPath: (if $binary_path == "" then "/opt/1cv8/1cv8" else $binary_path end)
      },
      infobase: (
        if $server != "" and $ref != "" then
          {
            mode: "client-server",
            server: $server,
            ref: $ref,
            connectionStringOverride: null,
            auth: {
              mode: $auth_mode,
              user: (if $user == "" then null else $user end),
              passwordEnv: $password_env
            }
          }
        else
          {
            mode: "file",
            filePath: (if $file_path == "" then "/var/tmp/" + (if $project_slug == "" then "project" else $project_slug end) else $file_path end),
            connectionStringOverride: null,
            auth: {
              mode: $auth_mode,
              user: (if $user == "" then null else $user end),
              passwordEnv: $password_env
            }
          }
        end
      ),
      capabilities: {
        dumpSrc: {
          outputDir: "./src/cf"
        },
        loadSrc: {
          sourceDir: "./src/cf"
        },
        diffSrc: (
          if $diff_command == null then
            { command: ["git", "diff", "--", "./src"] }
          else
            { command: $diff_command }
          end
        ),
        xunit: (
          if $xunit_command == null then
            { unsupportedReason: "xUnit contour is not wired yet; migrate it before treating this profile as green." }
          else
            { command: $xunit_command }
          end
        ),
        bdd: (
          if $bdd_command == null then
            { unsupportedReason: "BDD contour is not wired yet; migrate it before treating this profile as green." }
          else
            { command: $bdd_command }
          end
        ),
        smoke: (
          if $smoke_command == null then
            { unsupportedReason: "Smoke contour is not wired yet; migrate it before treating this profile as green." }
          else
            { command: $smoke_command }
          end
        ),
        publishHttp: (
          if $publish_command == null then
            { unsupportedReason: "Publish HTTP contour is not wired yet; migrate it before treating this profile as green." }
          else
            { command: $publish_command }
          end
        )
      }
    }'
}

main "$@"
