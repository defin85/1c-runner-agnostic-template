#!/usr/bin/env bash
set -euo pipefail

designer_diagnostic_severity() {
  local raw="$1"
  local exit_code="${2:-0}"

  case "$raw" in
    *"Handler missing:"*|*"Cannot find method "*)
      printf 'warning\n'
      ;;
    *"Variable is not defined"*|*"Procedure or function with the specified name is not defined"*|*"Method not found"*|*"Procedure or function is not defined"*)
      printf 'error\n'
      ;;
    *)
      if [ "$exit_code" -ne 0 ]; then
        printf 'error\n'
      else
        printf 'warning\n'
      fi
      ;;
  esac
}

designer_out_diagnostics_to_json_file() {
  local out_log="$1"
  local exit_code="${2:-0}"
  local output_json="$3"
  local diagnostics_tmp=""
  local raw=""
  local severity=""

  : >"$output_json"
  if [ ! -f "$out_log" ]; then
    printf '[]\n' >"$output_json"
    return 0
  fi

  diagnostics_tmp="$(mktemp "${TMPDIR:-/tmp}/designer-diagnostics.XXXXXX")"

  while IFS= read -r raw || [ -n "$raw" ]; do
    raw="${raw#$'\ufeff'}"
    raw="${raw%$'\r'}"
    [ -n "$raw" ] || continue
    case "$raw" in
      "No errors found"|"Ошибок не обнаружено")
        continue
        ;;
    esac

    severity="$(designer_diagnostic_severity "$raw" "$exit_code")"
    jq -cn \
      --arg severity "$severity" \
      --arg message "$raw" \
      --arg raw "$raw" \
      '{
        severity: $severity,
        message: $message,
        raw: $raw
      }' >>"$diagnostics_tmp"
  done <"$out_log"

  if [ ! -s "$diagnostics_tmp" ]; then
    rm -f "$diagnostics_tmp"
    printf '[]\n' >"$output_json"
    return 0
  fi

  jq -sc . "$diagnostics_tmp" >"$output_json"
  rm -f "$diagnostics_tmp"
}

designer_regex_escape_ere() {
  printf '%s' "$1" | sed 's/[][(){}.^$*+?|\\]/\\&/g'
}

designer_strip_extension_prefix_from_metadata_ref() {
  local metadata_ref="$1"
  local stripped="${metadata_ref#* }"

  case "$metadata_ref" in
    Документ.*|Справочник.*|ОбщаяФорма.*|Обработка.*|РегистрСведений.*)
      printf '%s\n' "$metadata_ref"
      return 0
      ;;
  esac

  case "$stripped" in
    Документ.*|Справочник.*|ОбщаяФорма.*|Обработка.*|РегистрСведений.*)
      printf '%s\n' "$stripped"
      return 0
      ;;
  esac

  printf '%s\n' "$metadata_ref"
}

designer_base_form_module_path_from_metadata_ref() {
  local project_root="$1"
  local metadata_ref="$2"
  local normalized=""

  normalized="$(designer_strip_extension_prefix_from_metadata_ref "$metadata_ref")"

  case "$normalized" in
    ОбщаяФорма.*.Форма)
      IFS='.' read -r _ object_name _ <<<"$normalized"
      printf '%s\n' "$project_root/src/cf/CommonForms/$object_name/Ext/Form/Module.bsl"
      ;;
    Документ.*.Форма.*.Форма)
      IFS='.' read -r _ object_name _ form_name _ <<<"$normalized"
      printf '%s\n' "$project_root/src/cf/Documents/$object_name/Forms/$form_name/Ext/Form/Module.bsl"
      ;;
    Справочник.*.Форма.*.Форма)
      IFS='.' read -r _ object_name _ form_name _ <<<"$normalized"
      printf '%s\n' "$project_root/src/cf/Catalogs/$object_name/Forms/$form_name/Ext/Form/Module.bsl"
      ;;
    Обработка.*.Форма.*.Форма)
      IFS='.' read -r _ object_name _ form_name _ <<<"$normalized"
      printf '%s\n' "$project_root/src/cf/DataProcessors/$object_name/Forms/$form_name/Ext/Form/Module.bsl"
      ;;
    РегистрСведений.*.Форма.*.Форма)
      IFS='.' read -r _ object_name _ form_name _ <<<"$normalized"
      printf '%s\n' "$project_root/src/cf/InformationRegisters/$object_name/Forms/$form_name/Ext/Form/Module.bsl"
      ;;
    *)
      printf '\n'
      ;;
  esac
}

designer_bsl_symbol_exists() {
  local module_path="$1"
  local symbol_name="$2"
  local escaped_symbol=""

  [ -f "$module_path" ] || return 1

  escaped_symbol="$(designer_regex_escape_ere "$symbol_name")"
  grep -Eq "^[[:space:]]*(Процедура|Функция)[[:space:]]+$escaped_symbol[[:space:]]*\\(" "$module_path"
}

classify_extension_config_diagnostics() {
  local project_root="$1"
  local input_json="$2"
  local classified_json="$3"
  local blocking_json="$4"
  local inherited_json="$5"
  local input_copy=""
  local diagnostics_tmp=""
  local diagnostic=""
  local raw=""
  local metadata_ref=""
  local handler_name=""
  local base_form_module=""
  local classification=""
  local resolution_kind=""

  if [ ! -f "$input_json" ]; then
    printf '[]\n' >"$classified_json"
    printf '[]\n' >"$blocking_json"
    printf '[]\n' >"$inherited_json"
    return 0
  fi

  input_copy="$(mktemp "${TMPDIR:-/tmp}/designer-input-diagnostics.XXXXXX")"
  cp "$input_json" "$input_copy"
  printf '[]\n' >"$classified_json"
  printf '[]\n' >"$blocking_json"
  printf '[]\n' >"$inherited_json"
  diagnostics_tmp="$(mktemp "${TMPDIR:-/tmp}/designer-classified-diagnostics.XXXXXX")"

  while IFS= read -r diagnostic; do
    [ -n "$diagnostic" ] || continue

    raw="$(jq -r '.raw' <<<"$diagnostic")"
    metadata_ref=""
    handler_name=""
    base_form_module=""
    classification="blocking"
    resolution_kind="blocking_diagnostic"

    if [[ "$raw" == *" Handler missing:"* ]]; then
      metadata_ref="${raw%% Handler missing:*}"
      handler_name="$(sed -n 's/.*"\([^"]*\)".*/\1/p' <<<"$raw")"
      base_form_module="$(designer_base_form_module_path_from_metadata_ref "$project_root" "$metadata_ref")"

      if [ -n "$handler_name" ] && [ -n "$base_form_module" ] && designer_bsl_symbol_exists "$base_form_module" "$handler_name"; then
        classification="inherited_handler"
        resolution_kind="resolved_in_base_form_module"
      else
        resolution_kind="unresolved_handler"
      fi
    fi

    jq -cn \
      --argjson diagnostic "$diagnostic" \
      --arg classification "$classification" \
      --arg metadata_ref "$(designer_strip_extension_prefix_from_metadata_ref "$metadata_ref")" \
      --arg handler_name "$handler_name" \
      --arg resolution_kind "$resolution_kind" \
      --arg base_form_module "${base_form_module#$project_root/}" \
      '$diagnostic + {
        classification: $classification,
        metadata_ref: (if $metadata_ref == "" then null else $metadata_ref end),
        handler_name: (if $handler_name == "" then null else $handler_name end),
        resolution: {
          kind: $resolution_kind,
          base_form_module: (if $base_form_module == "" then null else $base_form_module end)
        }
      }' >>"$diagnostics_tmp"
  done < <(jq -c '.[]' "$input_copy")

  if [ ! -s "$diagnostics_tmp" ]; then
    rm -f "$input_copy"
    rm -f "$diagnostics_tmp"
    return 0
  fi

  jq -sc . "$diagnostics_tmp" >"$classified_json"
  jq '[ .[] | select(.classification == "blocking") ]' "$classified_json" >"$blocking_json"
  jq '[ .[] | select(.classification == "inherited_handler") ]' "$classified_json" >"$inherited_json"
  rm -f "$input_copy"
  rm -f "$diagnostics_tmp"
}

json_array_length_from_file() {
  local json_file="$1"

  jq -r 'length' "$json_file"
}

summary_string_field_or_empty() {
  local summary_path="$1"
  local expr="$2"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r "$expr // empty" "$summary_path"
}

summary_number_field_or_empty() {
  local summary_path="$1"
  local expr="$2"

  if [ ! -f "$summary_path" ]; then
    printf '\n'
    return 0
  fi

  jq -r "($expr // empty)" "$summary_path"
}
