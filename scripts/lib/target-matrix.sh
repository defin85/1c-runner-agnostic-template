#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

TARGET_MATRIX_RELPATH="automation/context/target-matrix.json"

target_matrix_path() {
  printf '%s/%s\n' "$1" "$TARGET_MATRIX_RELPATH"
}

target_matrix_present() {
  [ -f "$(target_matrix_path "$1")" ]
}

target_matrix_enabled() {
  local root="$1"
  local matrix=""

  target_matrix_present "$root" || return 1
  require_command jq
  matrix="$(target_matrix_path "$root")"
  [ "$(jq -r '(.targets // []) | length' "$matrix")" -gt 0 ]
}

target_profile_id() {
  local value=""

  if ! runtime_profile_loaded; then
    printf '\n'
    return 0
  fi

  value="$(profile_string '.target.id // empty')"
  printf '%s\n' "$value"
}

target_require_requested() {
  local root="$1"
  local requested="${2:-}"
  local profile_target=""
  local matrix=""

  target_matrix_enabled "$root" || return 0
  matrix="$(target_matrix_path "$root")"

  [ -n "$requested" ] || die "multi-target workspace requires --target <id>"
  jq -e --arg id "$requested" '.targets[]? | select(.id == $id)' "$matrix" >/dev/null \
    || die "target not found in $TARGET_MATRIX_RELPATH: $requested"

  profile_target="$(target_profile_id)"
  [ -n "$profile_target" ] || die "runtime profile target.id is required for multi-target workspace"
  if [ "$profile_target" != "$requested" ]; then
    die "runtime profile target '$profile_target' does not match requested target '$requested'"
  fi
}

target_source_dir_or_default() {
  local root="$1"
  local requested="${2:-}"
  local default_source="$3"
  local matrix=""
  local source_path=""

  if ! target_matrix_enabled "$root"; then
    printf '%s\n' "$default_source"
    return 0
  fi

  target_require_requested "$root" "$requested"
  matrix="$(target_matrix_path "$root")"
  source_path="$(jq -r --arg id "$requested" '.targets[] | select(.id == $id) | .sourcePath // empty' "$matrix")"
  [ -n "$source_path" ] || source_path="src/cf/$requested"
  [ -d "$root/$source_path" ] || die "target source path not found: $source_path"
  printf '%s\n' "$source_path"
}

target_extensions_json() {
  local root="$1"
  local requested="$2"
  local matrix=""

  matrix="$(target_matrix_path "$root")"
  jq -c --arg id "$requested" '.extensionMatrix[$id] // []' "$matrix"
}

target_fill_extensions_array() {
  local root="$1"
  local requested="${2:-}"
  local array_name="$3"
  local matrix=""
  local extension_name=""
  local -n out_ref="$array_name"

  out_ref=()
  target_matrix_enabled "$root" || return 1
  target_require_requested "$root" "$requested"
  matrix="$(target_matrix_path "$root")"

  while IFS= read -r extension_name; do
    [ -n "$extension_name" ] || continue
    [ -d "$root/src/cfe/$extension_name" ] || die "target matrix extension not found under src/cfe: $extension_name"
    out_ref+=("$extension_name")
  done < <(jq -r --arg id "$requested" '.extensionMatrix[$id][]? // empty' "$matrix")

  return 0
}

target_validate_matrix() {
  local root="$1"
  local matrix=""

  target_matrix_present "$root" || return 0
  require_command jq
  matrix="$(target_matrix_path "$root")"

  jq -e '
    .schemaVersion == 1
    and (.targets | type == "array")
    and (.extensionMatrix | type == "object")
    and all(.targets[]; (.id | type == "string" and length > 0))
  ' "$matrix" >/dev/null || die "invalid target metadata schema: $TARGET_MATRIX_RELPATH"

  while IFS= read -r source_path; do
    [ -n "$source_path" ] || continue
    [ -d "$root/$source_path" ] || die "target source path not found: $source_path"
  done < <(jq -r '.targets[] | .sourcePath // ("src/cf/" + .id)' "$matrix")

  while IFS= read -r target_id; do
    [ -n "$target_id" ] || continue
    jq -e --arg id "$target_id" '.targets[]? | select(.id == $id)' "$matrix" >/dev/null \
      || die "extension matrix references unknown target: $target_id"
  done < <(jq -r '.extensionMatrix | keys[]' "$matrix")

  while IFS= read -r extension_name; do
    [ -n "$extension_name" ] || continue
    [ -d "$root/src/cfe/$extension_name" ] || die "target matrix extension not found under src/cfe: $extension_name"
  done < <(jq -r '.extensionMatrix[]?[]? // empty' "$matrix" | LC_ALL=C sort -u)
}

target_validate_runtime_support_matrix() {
  local root="$1"
  local support_matrix="$root/automation/context/runtime-support-matrix.json"
  local target_matrix=""
  local target_id=""
  local extension_name=""

  target_matrix_present "$root" || return 0
  [ -f "$support_matrix" ] || return 0
  require_command jq
  target_matrix="$(target_matrix_path "$root")"

  while IFS= read -r target_id; do
    [ -n "$target_id" ] || continue
    jq -e --arg id "$target_id" '.targets[]? | select(.id == $id)' "$target_matrix" >/dev/null \
      || die "runtime support matrix references unknown target: $target_id"
  done < <(jq -r '.contours[]? | .targets[]? // empty' "$support_matrix")

  while IFS= read -r target_id; do
    [ -n "$target_id" ] || continue
    jq -e --arg id "$target_id" '.targets[]? | select(.id == $id)' "$target_matrix" >/dev/null \
      || die "runtime support matrix extensionMatrix references unknown target: $target_id"
  done < <(jq -r '.contours[]? | .extensionMatrix? // {} | keys[]' "$support_matrix")

  while IFS= read -r extension_name; do
    [ -n "$extension_name" ] || continue
    [ -d "$root/src/cfe/$extension_name" ] \
      || die "runtime support matrix references missing extension under src/cfe: $extension_name"
  done < <(jq -r '.contours[]? | .extensionMatrix? // {} | .[]?[]? // empty' "$support_matrix" | LC_ALL=C sort -u)
}
