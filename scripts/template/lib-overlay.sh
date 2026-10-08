#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

overlay_manifest_relpath="automation/context/template-managed-paths.txt"
overlay_preserve_relpath="automation/context/template-update-preserve-paths.txt"
overlay_version_relpath=".template-overlay-version"
overlay_source_relpath=".template-overlay-source"

overlay_manifest_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_manifest_relpath"
}

overlay_preserve_manifest_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_preserve_relpath"
}

overlay_version_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_version_relpath"
}

overlay_source_file() {
  local root="$1"
  printf '%s/%s\n' "$root" "$overlay_source_relpath"
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
  local answers_file
  local source_file

  answers_file="$(copier_answers_file "$root")"
  if read_optional_answers_value "$answers_file" "_src_path" >/dev/null 2>&1; then
    read_optional_answers_value "$answers_file" "_src_path"
    return 0
  fi

  source_file="$(overlay_source_file "$root")"
  if [ -f "$source_file" ]; then
    sed -n '1p' "$source_file"
    return 0
  fi

  die "template source path not found in answers file or $source_file"
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

write_overlay_source() {
  local root="$1"
  local source="$2"

  printf '%s\n' "$source" >"$(overlay_source_file "$root")"
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

# Exact preserve entries match one path; entries ending with `/` match a whole project-owned directory.
preserve_manifest_has_entry() {
  local manifest_file="$1"
  local relpath="$2"
  local entry

  [ -f "$manifest_file" ] || return 1
  grep -Fqx -- "$relpath" "$manifest_file" && return 0
  while IFS= read -r entry; do
    case "$entry" in
      */)
        case "$relpath" in
          "$entry"*) return 0 ;;
        esac
        ;;
    esac
  done < <(manifest_entries "$manifest_file")
  return 1
}

# Keep in sync with scripts/python/project_extensions.py.
project_block_begin="# >>> project-owned block: template-update keeps the lines up to the closing marker >>>"
project_block_end="# <<< project-owned block <<<"

is_project_block_file() {
  case "$1" in
    .gitignore|.gitattributes|.contextignore) return 0 ;;
  esac
  return 1
}

# Prints "none", "ok" or "invalid" for the project-owned block markers in a file.
project_block_state() {
  local file="$1"
  awk -v begin="$project_block_begin" -v end="$project_block_end" '
    { sub(/\r$/, "") }
    $0 == begin { begins++; if (!first_begin) first_begin = NR }
    $0 == end { ends++; if (!first_end) first_end = NR }
    END {
      if (!begins && !ends) print "none"
      else if (begins == 1 && ends == 1 && first_begin < first_end) print "ok"
      else print "invalid"
    }
  ' "$file"
}

# Writes the template file with the project-owned block taken from the current project file.
merge_project_block_file() {
  local source_file="$1"
  local target_file="$2"
  local relpath="$3"
  local target_state source_state block_file merged_file

  target_state="$(project_block_state "$target_file")"
  source_state="$(project_block_state "$source_file")"
  [ "$target_state" != "invalid" ] || die "$relpath (project): project-owned block must have exactly one opening and one closing marker in this order"
  [ "$source_state" != "invalid" ] || die "$relpath (template release): project-owned block must have exactly one opening and one closing marker in this order"

  if [ "$target_state" = "none" ]; then
    return 1
  fi

  block_file="$(mktemp)"
  merged_file="$(mktemp)"
  awk -v begin="$project_block_begin" -v end="$project_block_end" '
    { line = $0; sub(/\r$/, "", line) }
    line == begin { inside = 1 }
    inside { print }
    line == end { inside = 0 }
  ' "$target_file" >"$block_file"

  if [ "$source_state" = "ok" ]; then
    awk -v begin="$project_block_begin" -v end="$project_block_end" -v block_file="$block_file" '
      { line = $0; sub(/\r$/, "", line) }
      line == begin {
        while ((getline block_line < block_file) > 0) print block_line
        skipping = 1
        next
      }
      skipping && line == end { skipping = 0; next }
      !skipping { print }
    ' "$source_file" >"$merged_file"
  else
    cat "$source_file" >"$merged_file"
    if [ -s "$merged_file" ] && [ -n "$(tail -c 1 "$merged_file")" ]; then
      printf '\n' >>"$merged_file"
    fi
    cat "$block_file" >>"$merged_file"
  fi

  install -m "$(stat -c '%a' "$source_file")" "$merged_file" "$target_file"
  rm -f "$block_file" "$merged_file"
  return 0
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

  if is_project_block_file "$relpath" && [ -f "$target_root/$relpath" ] \
    && merge_project_block_file "$source_file" "$target_root/$relpath" "$relpath"; then
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
  local preserve_manifest="${5:-}"
  local union_file relpath

  [ -f "$next_manifest" ] || die "overlay manifest is missing in release: $next_manifest"

  union_file="$(mktemp)"
  {
    manifest_entries "$previous_manifest"
    manifest_entries "$next_manifest"
  } | LC_ALL=C sort -u >"$union_file"

  while IFS= read -r relpath; do
    [ -n "$relpath" ] || continue

    # Project-owned paths win over the managed manifest: overlay sync never writes or removes them.
    if preserve_manifest_has_entry "$preserve_manifest" "$relpath"; then
      continue
    elif manifest_has_entry "$next_manifest" "$relpath"; then
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
