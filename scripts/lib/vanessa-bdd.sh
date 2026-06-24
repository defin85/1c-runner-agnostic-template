#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"
# shellcheck source=./runtime-profile.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-profile.sh"

VANESSA_BDD_TARGETS_RELPATH="automation/context/operator-local-targets.json"

vanessa_bdd_targets_path() {
  printf '%s/%s\n' "$1" "$VANESSA_BDD_TARGETS_RELPATH"
}

vanessa_bdd_append_missing() {
  local array_name="$1"
  local message="$2"
  local -n out_ref="$array_name"

  out_ref+=("$message")
}

vanessa_bdd_profile_array() {
  local expr="$1"
  local array_name="$2"
  local value=""
  local -n out_ref="$array_name"

  out_ref=()
  while IFS= read -r value; do
    [ -n "$value" ] || continue
    out_ref+=("$value")
  done < <(profile_jq_raw "$expr | if type == \"array\" then .[] else empty end")
}

vanessa_bdd_validate_target_binding() {
  local root="$1"
  local array_name="$2"
  local targets_path=""
  local target_id=""
  local expected_target_id=""
  local expected_mode=""
  local profile_mode=""
  local expected_file_path=""
  local profile_file_path=""
  local expected_server=""
  local profile_server=""
  local expected_ref=""
  local profile_ref=""

  targets_path="$(vanessa_bdd_targets_path "$root")"
  if [ ! -f "$targets_path" ]; then
    vanessa_bdd_append_missing "$array_name" "$VANESSA_BDD_TARGETS_RELPATH"
    return 0
  fi

  require_command jq
  jq -e '.operatorLocalTargets.vanessaBdd | type == "object"' "$targets_path" >/dev/null \
    || die "invalid Vanessa BDD target contract: $VANESSA_BDD_TARGETS_RELPATH"

  target_id="$(profile_string '.target.id // empty')"
  expected_target_id="$(jq -r '.operatorLocalTargets.vanessaBdd.targetId // empty' "$targets_path")"
  if [ -z "$target_id" ] || [ -z "$expected_target_id" ] || [ "$target_id" != "$expected_target_id" ]; then
    vanessa_bdd_append_missing "$array_name" "operatorLocalTargets.vanessaBdd.targetId match"
  fi

  expected_mode="$(jq -r '.operatorLocalTargets.vanessaBdd.infobase.mode // empty' "$targets_path")"
  profile_mode="$(profile_string '.infobase.mode // empty')"
  if [ -z "$expected_mode" ] || [ "$profile_mode" != "$expected_mode" ]; then
    vanessa_bdd_append_missing "$array_name" "operatorLocalTargets.vanessaBdd.infobase.mode match"
    return 0
  fi

  case "$expected_mode" in
    file)
      expected_file_path="$(jq -r '.operatorLocalTargets.vanessaBdd.infobase.filePath // empty' "$targets_path")"
      profile_file_path="$(profile_string '.infobase.filePath // empty')"
      if [ -z "$expected_file_path" ] || [ "$profile_file_path" != "$expected_file_path" ]; then
        vanessa_bdd_append_missing "$array_name" "operatorLocalTargets.vanessaBdd.infobase.filePath match"
      fi
      ;;
    client-server)
      expected_server="$(jq -r '.operatorLocalTargets.vanessaBdd.infobase.server // empty' "$targets_path")"
      profile_server="$(profile_string '.infobase.server // empty')"
      expected_ref="$(jq -r '.operatorLocalTargets.vanessaBdd.infobase.ref // empty' "$targets_path")"
      profile_ref="$(profile_string '.infobase.ref // empty')"
      if [ -z "$expected_server" ] || [ "$profile_server" != "$expected_server" ]; then
        vanessa_bdd_append_missing "$array_name" "operatorLocalTargets.vanessaBdd.infobase.server match"
      fi
      if [ -z "$expected_ref" ] || [ "$profile_ref" != "$expected_ref" ]; then
        vanessa_bdd_append_missing "$array_name" "operatorLocalTargets.vanessaBdd.infobase.ref match"
      fi
      ;;
    *)
      vanessa_bdd_append_missing "$array_name" "supported operatorLocalTargets.vanessaBdd.infobase.mode"
      ;;
  esac
}
