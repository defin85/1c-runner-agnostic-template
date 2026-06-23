#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

YAXUNIT_CONTOUR_ID="yaxunit-light-contour"
YAXUNIT_WARM_RPC_CONTOUR_ID="yaxunit-warm-rpc-contour"

json_array_from_lines() {
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  printf '%s\n' "$@" | jq -R . | jq -s .
}

yaxunit_project_slug() {
  basename -- "$(project_root)"
}

yaxunit_state_root() {
  local override="${ONEC_YAXUNIT_STATE_ROOT:-}"

  if [ -n "$override" ]; then
    printf '%s\n' "$(canonical_path "$override")"
    return 0
  fi

  if [ -n "${XDG_STATE_HOME:-}" ]; then
    printf '%s/%s/yaxunit\n' "$(canonical_path "$XDG_STATE_HOME")" "$(yaxunit_project_slug)"
    return 0
  fi

  printf '%s/.local/state/%s/yaxunit\n' "$(canonical_path "$HOME")" "$(yaxunit_project_slug)"
}

yaxunit_warm_rpc_state_root() {
  local override="${ONEC_YAXUNIT_WARM_RPC_STATE_ROOT:-}"

  if [ -n "$override" ]; then
    printf '%s\n' "$(canonical_path "$override")"
    return 0
  fi

  if [ -n "${XDG_STATE_HOME:-}" ]; then
    printf '%s/%s/yaxunit-warm-rpc\n' "$(canonical_path "$XDG_STATE_HOME")" "$(yaxunit_project_slug)"
    return 0
  fi

  printf '%s/.local/state/%s/yaxunit-warm-rpc\n' "$(canonical_path "$HOME")" "$(yaxunit_project_slug)"
}

yaxunit_warm_rpc_sessions_dir() {
  printf '%s/sessions\n' "$(yaxunit_warm_rpc_state_root)"
}

yaxunit_warm_rpc_current_link() {
  printf '%s/current\n' "$(yaxunit_warm_rpc_state_root)"
}

yaxunit_sync_dir() {
  printf '%s/sync\n' "$(yaxunit_state_root)"
}

yaxunit_runtime_extension_name() {
  case "$1" in
    YAxUnit)
      printf 'YAXUNIT\n'
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

yaxunit_source_extension_name() {
  case "$1" in
    YAXUNIT|YAxUnit)
      printf 'YAxUnit\n'
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

yaxunit_profile_identity_json() {
  local profile_path="$1"

  require_command jq
  jq -c \
    --arg profile_path "$(canonical_path "$profile_path")" \
    '{
      profile_path: $profile_path,
      profile_name: (.profileName // null),
      infobase: {
        mode: (.infobase.mode // null),
        server: (.infobase.server // null),
        ref: (.infobase.ref // null),
        file_path: (.infobase.filePath // null),
        auth_mode: (.infobase.auth.mode // null),
        user: (.infobase.auth.user // null)
      }
    }' \
    "$profile_path"
}

yaxunit_profile_key() {
  local profile_path="$1"
  local identity_json=""

  require_command sha256sum
  identity_json="$(yaxunit_profile_identity_json "$profile_path")"
  printf '%s' "$identity_json" | sha256sum | awk '{print $1}'
}

yaxunit_sync_evidence_path() {
  local profile_path="$1"

  printf '%s/%s.json\n' "$(yaxunit_sync_dir)" "$(yaxunit_profile_key "$profile_path")"
}

yaxunit_sync_command() {
  local profile_path="$1"
  local array_name="$2"
  local extension_name=""
  local command="./scripts/test/sync-yaxunit-runtime.sh --profile $profile_path --run-root /tmp/yaxunit-sync-run"
  local -n extensions_ref="$array_name"

  for extension_name in "${extensions_ref[@]}"; do
    command+=" --extension $extension_name"
  done

  printf '%s\n' "$command"
}

yaxunit_collect_contract_files() {
  local root="$1"
  local array_name="$2"
  local extension_name=""
  local rel=""
  local rel_path=""
  local -n extensions_ref="$array_name"
  local -n out_ref="$3"

  root="$(canonical_path "$root")"
  out_ref=()

  for extension_name in "${extensions_ref[@]}"; do
    rel="src/cfe/$extension_name"
    [ -d "$root/$rel" ] || continue

    while IFS= read -r -d '' rel_path; do
      out_ref+=("${rel_path#"$root/"}")
    done < <(find "$root/$rel" -type f -print0 | sort -z)
  done
}

yaxunit_contract_files_json() {
  local root="$1"
  local array_name="$2"
  local -a files=()

  require_command jq
  yaxunit_collect_contract_files "$root" "$array_name" files
  set -- "${files[@]}"
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  printf '%s\n' "${files[@]}" | jq -R . | jq -s .
}

yaxunit_contract_hash() {
  local root="$1"
  local array_name="$2"
  local hash_input=""
  local rel=""
  local content_hash=""
  local -a files=()

  require_command sha256sum
  root="$(canonical_path "$root")"
  yaxunit_collect_contract_files "$root" "$array_name" files
  if [ "${#files[@]}" -eq 0 ]; then
    printf 'no-contract-files\n' | sha256sum | awk '{print $1}'
    return 0
  fi

  hash_input="$(mktemp)"
  trap 'rm -f "$hash_input"' RETURN

  for rel in "${files[@]}"; do
    content_hash="$(sha256sum "$root/$rel" | awk '{print $1}')"
    printf '%s  %s\n' "$content_hash" "$rel" >>"$hash_input"
  done

  sha256sum "$hash_input" | awk '{print $1}'
}

yaxunit_write_sync_evidence() {
  local root="$1"
  local profile_path="$2"
  local source_run_root="$3"
  local sync_label="$4"
  local source_extensions_array="$5"
  local runtime_extensions_array="$6"
  local evidence_path=""
  local contract_hash=""
  local profile_identity_json=""
  local contract_files_json=""
  local source_extensions_json=""
  local runtime_extensions_json=""
  local -n source_extensions_ref="$source_extensions_array"
  local -n runtime_extensions_ref="$runtime_extensions_array"

  require_command jq
  evidence_path="$(yaxunit_sync_evidence_path "$profile_path")"
  ensure_dir "$(dirname -- "$evidence_path")"
  contract_hash="$(yaxunit_contract_hash "$root" "$source_extensions_array")"
  profile_identity_json="$(yaxunit_profile_identity_json "$profile_path")"
  contract_files_json="$(yaxunit_contract_files_json "$root" "$source_extensions_array")"
  source_extensions_json="$(json_array_from_lines "${source_extensions_ref[@]}")"
  runtime_extensions_json="$(json_array_from_lines "${runtime_extensions_ref[@]}")"

  jq -n \
    --arg contour_id "$YAXUNIT_CONTOUR_ID" \
    --arg prepared_at "$(timestamp_utc)" \
    --arg repo_root "$(canonical_path "$root")" \
    --arg source_run_root "$(canonical_path "$source_run_root")" \
    --arg sync_label "$sync_label" \
    --arg sync_command "$(yaxunit_sync_command "$profile_path" "$source_extensions_array")" \
    --arg contract_hash "$contract_hash" \
    --argjson profile_identity "$profile_identity_json" \
    --argjson contract_files "$contract_files_json" \
    --argjson selected_source_extensions "$source_extensions_json" \
    --argjson runtime_flag_extensions "$runtime_extensions_json" \
    '{
      contour_id: $contour_id,
      status: "success",
      prepared_at: $prepared_at,
      repo_root: $repo_root,
      source_run_root: $source_run_root,
      sync_label: (if $sync_label == "" then null else $sync_label end),
      sync_command: $sync_command,
      contract_hash: $contract_hash,
      profile_identity: $profile_identity,
      selected_source_extensions: $selected_source_extensions,
      runtime_flag_extensions: $runtime_flag_extensions,
      contract_files: $contract_files
    }' >"$evidence_path"

  printf '%s\n' "$evidence_path"
}
