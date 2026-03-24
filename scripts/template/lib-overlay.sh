#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

overlay_manifest_relpath="automation/context/template-managed-paths.txt"
overlay_version_relpath=".template-overlay-version"

overlay_manifest_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_manifest_relpath"
}

overlay_version_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_version_relpath"
}

copier_answers_file() {
  local root="$1"
  printf '%s/.copier-answers.yml\n' "$root"
}

strip_wrapping_quotes() {
  local value="$1"

  case "$value" in
    \"*\")
      value="${value#\"}"
      value="${value%\"}"
      ;;
    \'*\')
      value="${value#\'}"
      value="${value%\'}"
      ;;
  esac

  printf '%s\n' "$value"
}

read_answers_value() {
  local answers_file="$1"
  local key="$2"
  local value

  [ -f "$answers_file" ] || die "answers file not found: $answers_file"

  value="$(sed -n "s/^${key}:[[:space:]]*//p" "$answers_file" | head -n 1)"
  [ -n "$value" ] || die "answers file does not contain ${key}: $answers_file"
  strip_wrapping_quotes "$value"
}

read_optional_answers_value() {
  local answers_file="$1"
  local key="$2"
  local value

  [ -f "$answers_file" ] || return 1
  value="$(sed -n "s/^${key}:[[:space:]]*//p" "$answers_file" | head -n 1)"
  [ -n "$value" ] || return 1
  strip_wrapping_quotes "$value"
}

template_source_path() {
  local root="$1"
  read_answers_value "$(copier_answers_file "$root")" "_src_path"
}

bootstrap_template_ref() {
  local root="$1"
  read_answers_value "$(copier_answers_file "$root")" "_commit"
}

bootstrap_template_ref_or_fallback() {
  local root="$1"
  local template_source="$2"
  local answers_file

  answers_file="$(copier_answers_file "$root")"
  if read_optional_answers_value "$answers_file" "_commit" >/dev/null 2>&1; then
    read_optional_answers_value "$answers_file" "_commit"
    return 0
  fi

  if is_local_git_source "$template_source"; then
    git -C "$template_source" describe --tags --always
    return 0
  fi

  printf 'unknown\n'
}

project_answer_value() {
  local root="$1"
  local key="$2"
  read_answers_value "$(copier_answers_file "$root")" "$key"
}

project_answer_value_or_default() {
  local root="$1"
  local key="$2"
  local default_value="$3"
  local answers_file

  answers_file="$(copier_answers_file "$root")"
  if read_optional_answers_value "$answers_file" "$key" >/dev/null 2>&1; then
    read_optional_answers_value "$answers_file" "$key"
    return 0
  fi

  printf '%s\n' "$default_value"
}

current_overlay_version() {
  local root="$1"
  local version_file

  version_file="$(overlay_version_file "$root")"
  if [ -f "$version_file" ]; then
    sed -n '1p' "$version_file"
    return 0
  fi

  bootstrap_template_ref "$root"
}

write_overlay_version() {
  local root="$1"
  local version="$2"

  printf '%s\n' "$version" >"$(overlay_version_file "$root")"
}

manifest_entries() {
  local manifest_file="$1"

  [ -f "$manifest_file" ] || return 0
  sed \
    -e '/^[[:space:]]*#/d' \
    -e '/^[[:space:]]*$/d' \
    "$manifest_file"
}

manifest_has_entry() {
  local manifest_file="$1"
  local relpath="$2"

  [ -f "$manifest_file" ] || return 1
  grep -Fqx -- "$relpath" "$manifest_file"
}

prune_empty_parent_dirs() {
  local root="$1"
  local current="$2"

  while [ "$current" != "$root" ] && [ "$current" != "/" ] && [ "$current" != "." ]; do
    rmdir "$current" 2>/dev/null || break
    current="$(dirname "$current")"
  done
}

remove_manifest_entry_target() {
  local root="$1"
  local relpath="$2"
  local target="$root/$relpath"

  [ -e "$target" ] || return 0

  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf 'remove %s\n' "$relpath"
    return 0
  fi

  rm -f -- "$target"
  prune_empty_parent_dirs "$root" "$(dirname "$target")"
}

copy_manifest_entry_from_source() {
  local source_root="$1"
  local target_root="$2"
  local relpath="$3"
  local source_file="$source_root/$relpath"
  local mode

  [ -f "$source_file" ] || die "overlay entry is missing in source release: $relpath"

  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf 'sync %s\n' "$relpath"
    return 0
  fi

  mode="$(stat -c '%a' "$source_file")"
  install -D -m "$mode" "$source_file" "$target_root/$relpath"
}

sync_overlay_manifests() {
  local source_root="$1"
  local target_root="$2"
  local previous_manifest="$3"
  local next_manifest="$4"
  local union_file relpath

  [ -f "$next_manifest" ] || die "overlay manifest is missing in release: $next_manifest"

  union_file="$(mktemp)"
  {
    manifest_entries "$previous_manifest"
    manifest_entries "$next_manifest"
  } | LC_ALL=C sort -u >"$union_file"

  while IFS= read -r relpath; do
    [ -n "$relpath" ] || continue

    if manifest_has_entry "$next_manifest" "$relpath"; then
      copy_manifest_entry_from_source "$source_root" "$target_root" "$relpath"
    else
      remove_manifest_entry_target "$target_root" "$relpath"
    fi
  done <"$union_file"

  rm -f "$union_file"
}

is_local_git_source() {
  local source="$1"
  git -C "$source" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

list_overlay_release_tags() {
  local source="$1"

  if is_local_git_source "$source"; then
    git -C "$source" tag --list | LC_ALL=C sort -Vr
    return 0
  fi

  git ls-remote --tags --refs "$source" \
    | awk '{sub("refs/tags/", "", $2); print $2}' \
    | LC_ALL=C sort -Vr
}

resolve_target_overlay_ref() {
  local source="$1"
  local requested_ref="${2:-}"
  local latest_tag

  if [ -n "$requested_ref" ]; then
    printf '%s\n' "$requested_ref"
    return 0
  fi

  latest_tag="$(list_overlay_release_tags "$source" | sed -n '1p')"
  [ -n "$latest_tag" ] || die "no tagged overlay releases found for template source: $source"
  printf '%s\n' "$latest_tag"
}

materialize_overlay_source() {
  local source="$1"
  local ref="$2"
  local destination="$3"

  git -C "$destination" init -q
  git -C "$destination" remote add origin "$source"
  git -C "$destination" fetch -q --depth 1 origin "$ref"
  git -C "$destination" checkout -q FETCH_HEAD
}
