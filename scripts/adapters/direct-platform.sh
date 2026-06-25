#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

if [ "$#" -eq 0 ]; then
  printf 'usage: %s <command> [args...]\n' "$0" >&2
  exit 1
fi

apply_direct_platform_locale() {
  local locale_name="${ONEC_DIRECT_PLATFORM_LOCALE:-}"
  local language_chain="${ONEC_DIRECT_PLATFORM_LANGUAGE:-}"

  [ -n "$locale_name" ] || return 0

  export LANG="$locale_name"
  export LC_ALL="$locale_name"
  export LC_CTYPE="$locale_name"
  export LC_NUMERIC="$locale_name"
  export LC_TIME="$locale_name"
  export LC_COLLATE="$locale_name"
  export LC_MONETARY="$locale_name"
  export LC_MESSAGES="$locale_name"
  export LC_PAPER="$locale_name"
  export LC_NAME="$locale_name"
  export LC_ADDRESS="$locale_name"
  export LC_TELEPHONE="$locale_name"
  export LC_MEASUREMENT="$locale_name"
  export LC_IDENTIFICATION="$locale_name"

  if [ -n "$language_chain" ]; then
    export LANGUAGE="$language_chain"
  fi
}

build_ld_preload_value() {
  local library_path=""
  local ld_preload_value=""

  if [ "${ONEC_DIRECT_PLATFORM_LD_PRELOAD_ENABLED:-0}" != "1" ]; then
    printf '\n'
    return 0
  fi

  if [ -z "${ONEC_DIRECT_PLATFORM_LD_PRELOAD:-}" ]; then
    printf 'missing ONEC_DIRECT_PLATFORM_LD_PRELOAD for direct-platform ld-preload contour\n' >&2
    exit 1
  fi

  IFS=':' read -r -a ld_preload_libraries <<<"${ONEC_DIRECT_PLATFORM_LD_PRELOAD}"
  set -- "${ld_preload_libraries[@]}"
  if [ "$#" -eq 0 ]; then
    printf 'platform.ldPreload.libraries must not be empty for direct-platform ld-preload contour\n' >&2
    exit 1
  fi

  for library_path in "${ld_preload_libraries[@]}"; do
    case "$library_path" in
      /*)
        ;;
      *)
        printf 'direct-platform ld-preload library path must be absolute: %s\n' "$library_path" >&2
        exit 1
        ;;
    esac

    if [ ! -e "$library_path" ]; then
      printf 'missing direct-platform ld-preload library: %s\n' "$library_path" >&2
      exit 1
    fi
  done

  ld_preload_value="${ONEC_DIRECT_PLATFORM_LD_PRELOAD}"
  if [ -n "${LD_PRELOAD:-}" ]; then
    ld_preload_value+=":${LD_PRELOAD}"
  fi

  printf '%s\n' "$ld_preload_value"
}

pick_unused_xpra_display_number() {
  local min_display="${ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MIN:-120}"
  local max_display="${ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MAX:-179}"
  local display_number=""

  case "$min_display:$max_display" in
    *[!0-9:]*|:*)
      printf 'invalid xpra display range: %s..%s\n' "$min_display" "$max_display" >&2
      exit 1
      ;;
  esac
  if [ "$min_display" -gt "$max_display" ]; then
    printf 'invalid xpra display range: %s..%s\n' "$min_display" "$max_display" >&2
    exit 1
  fi

  for display_number in $(seq "$min_display" "$max_display"); do
    if [ -S "/tmp/.X11-unix/X${display_number}" ]; then
      continue
    fi
    if DISPLAY=":${display_number}" xdpyinfo >/dev/null 2>&1; then
      continue
    fi
    printf '%s\n' "$display_number"
    return 0
  done

  printf 'failed to pick a free xpra display in range %s..%s\n' "$min_display" "$max_display" >&2
  exit 1
}

run_xpra_wrapped_command() {
  local display_number=""
  local display_value=""
  local run_root="${ONEC_CAPABILITY_RUN_ROOT:-${TMPDIR:-/tmp}}"
  local xpra_root=""
  local xpra_log=""
  local xpra_session_name="${ONEC_DIRECT_PLATFORM_XPRA_SESSION_NAME:-}"
  local xpra_xvfb_args="${ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS:-}"
  local xpra_start_child="${ONEC_DIRECT_PLATFORM_XPRA_START_CHILD:-openbox}"
  local -a xpra_args=()
  local xauth_file=""
  local exit_code=0
  local waited=0

  require_command xpra
  require_command Xvfb
  require_command xdpyinfo
  if [ -n "$xpra_start_child" ]; then
    require_command "${xpra_start_child%% *}"
  fi
  if [ -z "$xpra_xvfb_args" ]; then
    printf 'missing ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS for direct-platform xpra contour\n' >&2
    exit 1
  fi

  mkdir -p "$run_root"
  xpra_root="$run_root/xpra"
  mkdir -p "$xpra_root"
  xauth_file="$run_root/home/.Xauthority"
  mkdir -p "$(dirname -- "$xauth_file")"
  xpra_xvfb_args="${xpra_xvfb_args//\$\{XAUTHORITY\}/$xauth_file}"
  xpra_xvfb_args="${xpra_xvfb_args//\$XAUTHORITY/$xauth_file}"
  display_number="$(pick_unused_xpra_display_number)"
  display_value=":${display_number}"
  xpra_log="$xpra_root/xpra-${display_number}.log"
  trap 'xpra stop "$display_value" >/dev/null 2>&1 || true' EXIT INT TERM

  xpra_args=(
    start-desktop "$display_value"
    --daemon=yes
    --attach=no
    --mdns=no
    --systemd-run=no
    --exit-with-children=no
    --html=off
    --xvfb="$xpra_xvfb_args"
    --log-file="$xpra_log"
  )
  [ -z "$xpra_session_name" ] || xpra_args+=(--session-name="$xpra_session_name")
  [ -z "$xpra_start_child" ] || xpra_args+=(--start-child="$xpra_start_child")

  XAUTHORITY="$xauth_file" xpra "${xpra_args[@]}" >&2

  while [ "$waited" -lt 100 ]; do
    if DISPLAY="$display_value" XAUTHORITY="$xauth_file" xdpyinfo >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
    waited=$((waited + 1))
  done

  if ! DISPLAY="$display_value" XAUTHORITY="$xauth_file" xdpyinfo >/dev/null 2>&1; then
    printf 'xpra display did not become ready: DISPLAY=%s log=%s\n' "$display_value" "$xpra_log" >&2
    if [ -f "$xpra_log" ]; then
      tail -80 "$xpra_log" >&2 || true
    fi
    xpra stop "$display_value" >/dev/null 2>&1 || true
    exit 1
  fi

  if [ -n "$xpra_start_child" ] && [ -f "$xpra_log" ]; then
    waited=0
    while [ "$waited" -lt 100 ]; do
      if grep -F "started command \`${xpra_start_child%% *}\`" "$xpra_log" >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
      waited=$((waited + 1))
    done
  fi

  printf 'direct-platform xpra display=%s log=%s\n' "$display_value" "$xpra_log" >&2

  set +e
  if [ -n "$ld_preload_value" ]; then
    DISPLAY="$display_value" XAUTHORITY="$xauth_file" env "LD_PRELOAD=$ld_preload_value" "$@"
  else
    DISPLAY="$display_value" XAUTHORITY="$xauth_file" "$@"
  fi
  exit_code=$?
  set -e

  xpra stop "$display_value" >/dev/null 2>&1 || true
  trap - EXIT INT TERM
  return "$exit_code"
}

command_name="${1##*/}"
apply_direct_platform_locale
ld_preload_value=""
if [ "$command_name" = "1cv8" ] || [ "$command_name" = "1cv8c" ]; then
  ld_preload_value="$(build_ld_preload_value)"
fi

if [ "${ONEC_DIRECT_PLATFORM_XPRA_ENABLED:-0}" = "1" ]; then
  case "$command_name" in
    1cv8|1cv8c)
      run_xpra_wrapped_command "$@"
      exit "$?"
      ;;
  esac
fi

if [ "${ONEC_DIRECT_PLATFORM_XVFB_ENABLED:-0}" = "1" ]; then
  case "$command_name" in
    1cv8|1cv8c)
      require_command xvfb-run
      require_command xauth
      if [ -n "${ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS:-}" ]; then
        if [ -n "$ld_preload_value" ]; then
          exec xvfb-run -a --error-file=/dev/stderr --server-args="${ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS}" env "LD_PRELOAD=$ld_preload_value" "$@"
        fi
        exec xvfb-run -a --error-file=/dev/stderr --server-args="${ONEC_DIRECT_PLATFORM_XVFB_SERVER_ARGS}" "$@"
      fi
      if [ -n "$ld_preload_value" ]; then
        exec xvfb-run -a --error-file=/dev/stderr env "LD_PRELOAD=$ld_preload_value" "$@"
      fi
      exec xvfb-run -a --error-file=/dev/stderr "$@"
      ;;
  esac
fi

if [ -n "$ld_preload_value" ]; then
  exec env "LD_PRELOAD=$ld_preload_value" "$@"
fi

exec "$@"
