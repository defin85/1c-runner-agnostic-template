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
    if [ -S "${ONEC_DIRECT_PLATFORM_X11_TMP_ROOT:-/tmp}/.X11-unix/X${display_number}" ]; then
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

# An Xvfb killed with SIGKILL leaves .X<N>-lock and its socket behind; without cleanup the display
# range runs out. Only provably dead entries of the current user are removed
# (scripts/python/onec_xpra.py reap_dead_x_displays); a failed check removes nothing.
reap_dead_x_displays() {
  local owner_directory="$1"
  local min_display="${ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MIN:-120}"
  local max_display="${ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MAX:-179}"
  local min_age="${ONEC_DIRECT_PLATFORM_X11_REAP_MIN_AGE:-10}"
  local reaped=""
  local display_number=""

  case "$min_display:$max_display:$min_age" in *[!0-9:]*|:*|*::*|*:) return 0 ;; esac
  [ "$min_display" -le "$max_display" ] || return 0
  reaped="$(cd -- "$(project_root)" && "${ONEC_PYTHON:-python3}" -m scripts.python.onec_xpra reap-x-displays \
    "${ONEC_DIRECT_PLATFORM_X11_TMP_ROOT:-/tmp}" "$min_display" "$max_display" \
    "$owner_directory" "$min_age")" || {
    printf 'direct-platform: dead X display cleanup skipped\n' >&2
    return 0
  }
  for display_number in $reaped; do
    printf 'direct-platform removed dead X display entries: :%s\n' "$display_number" >&2
  done
}

cleanup_xpra_session_processes() {
  local xpra_session_token="$1"
  local baseline_file="${2:-}"
  local pid=""
  local comm=""
  local -a pids=()

  [ -n "$xpra_session_token" ] || return 0

  for environ_path in /proc/[0-9]*/environ; do
    [ -r "$environ_path" ] || continue
    pid="${environ_path#/proc/}"
    pid="${pid%/environ}"
    [ "$pid" != "$$" ] || continue
    if ! tr '\0' '\n' <"$environ_path" 2>/dev/null | grep -Fxq "ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN=$xpra_session_token"; then
      continue
    fi
    comm="$(cat "/proc/$pid/comm" 2>/dev/null || true)"
    case "$comm" in
      1cv8|1cv8c|dbus-daemon|gvfsd|gvfsd-*|xpra|Xvfb|openbox)
        pids+=("$pid")
        ;;
    esac
  done

  if [ -n "$baseline_file" ] && [ -f "$baseline_file" ]; then
    while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      if grep -Fxq "$pid" "$baseline_file"; then
        continue
      fi
      comm="$(cat "/proc/$pid/comm" 2>/dev/null || true)"
      case "$comm" in
        dbus-daemon|gvfsd)
          pids+=("$pid")
          ;;
      esac
    done < <(
      ps -u "$UID" -o pid=,ppid=,comm=,cmd= \
        | awk '$2 == 1 || $2 ~ /^[0-9]+$/ { if (($3 == "dbus-daemon" && /--session/ && /--print-address/) || ($3 == "gvfsd" && $0 ~ /\/usr\/libexec\/gvfsd$/)) print $1 }'
    )
  fi

  [ "${#pids[@]}" -eq 0 ] || kill -TERM "${pids[@]}" 2>/dev/null || true
  sleep 0.5
  [ "${#pids[@]}" -eq 0 ] || kill -KILL "${pids[@]}" 2>/dev/null || true
}

stop_xpra_session() {
  local display_value="$1"
  local xpra_session_token="$2"
  local baseline_file="${3:-}"

  [ -z "$display_value" ] || xpra stop "$display_value" >/dev/null 2>&1 || true
  cleanup_xpra_session_processes "$xpra_session_token" "$baseline_file"
}

# Записывает PID процесса платформы для наблюдения и run-client своего run-root.
write_command_pid_file() {
  local pid="$1"
  local pid_file="${ONEC_DIRECT_PLATFORM_COMMAND_PID_FILE:-}"

  [ -n "$pid_file" ] || return 0
  case "$pid_file" in
    /*) ;;
    *)
      printf 'ONEC_DIRECT_PLATFORM_COMMAND_PID_FILE must be absolute\n' >&2
      exit 1
      ;;
  esac
  if [ -L "$pid_file" ]; then
    printf 'ONEC_DIRECT_PLATFORM_COMMAND_PID_FILE must not be a symlink\n' >&2
    exit 1
  fi
  mkdir -p "$(dirname -- "$pid_file")"
  # Readers accept only a complete decimal PID, so a plain write is enough and needs no extra tools.
  printf '%s\n' "$pid" >"$pid_file"
}

# Модальное окно ошибки 1С (transient или _NET_WM_STATE_MODAL) на дисплее своего сеанса.
find_1c_modal_window() {
  local display_value="$1"
  local xauth_file="$2"
  local window_id=""
  local properties=""

  while IFS= read -r window_id; do
    properties="$(DISPLAY="$display_value" XAUTHORITY="$xauth_file" \
      xprop -id "$window_id" WM_TRANSIENT_FOR _NET_WM_STATE 2>/dev/null || true)"
    if printf '%s\n' "$properties" | grep -Eq \
      'WM_TRANSIENT_FOR.*window id # 0x[1-9a-fA-F]|_NET_WM_STATE.*_NET_WM_STATE_MODAL'; then
      printf '%s\n' "$window_id"
      return 0
    fi
  done < <(
    DISPLAY="$display_value" XAUTHORITY="$xauth_file" xwininfo -root -tree 2>/dev/null \
      | sed -nE 's/^[[:space:]]*(0x[[:xdigit:]]+)[[:space:]]+"(1C:Enterprise|1С:Предприятие)".*/\1/p'
  )
  return 1
}

# Фиксирует модальное окно в evidence; при политике fail завершает зависший процесс платформы.
handle_modal_window() {
  local display_value="$1"
  local xauth_file="$2"
  local xpra_root="$3"
  local command_pid="$4"
  local modal_policy="$5"
  local modal_window=""

  [ ! -f "$xpra_root/error-dialog.detected" ] || return 1
  modal_window="$(find_1c_modal_window "$display_value" "$xauth_file")" || return 1
  printf 'direct-platform detected a modal 1C dialog\n' >&2
  DISPLAY="$display_value" XAUTHORITY="$xauth_file" \
    xprop -id "$modal_window" >"$xpra_root/error-dialog-window-properties.txt" 2>&1 || true
  if command -v import >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    (umask 077; DISPLAY="$display_value" XAUTHORITY="$xauth_file" \
      timeout --kill-after=1s 3s import -window "$modal_window" "$xpra_root/error-dialog.png") >/dev/null 2>&1 \
      || rm -f -- "$xpra_root/error-dialog.png" 2>/dev/null || true
  fi
  printf 'modal-dialog windowId=%s policy=%s\n' "$modal_window" "$modal_policy" >"$xpra_root/error-dialog.detected"
  [ "$modal_policy" = "fail" ] || return 1
  kill -TERM "$command_pid" 2>/dev/null || true
  sleep 1
  kill -KILL "$command_pid" 2>/dev/null || true
  return 0
}

run_xpra_wrapped_command() {
  local display_number=""
  local display_value=""
  local run_root="${ONEC_CAPABILITY_RUN_ROOT:-${TMPDIR:-/tmp}}"
  local xpra_root=""
  local xpra_log=""
  local xpra_cleanup_baseline=""
  local xpra_lock_dir="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/$(basename "$(project_root)")-xpra"
  local xpra_lock_file=""
  local xpra_session_name="${ONEC_DIRECT_PLATFORM_XPRA_SESSION_NAME:-}"
  local xpra_session_token="${ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN:-onec-xpra-$$-$(date +%s%N)}"
  local xpra_xvfb_args="${ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS:-}"
  local xpra_start_child="${ONEC_DIRECT_PLATFORM_XPRA_START_CHILD:-openbox}"
  local modal_policy="${ONEC_DIRECT_PLATFORM_XPRA_MODAL_POLICY:-fail}"
  local modal_detection=0
  local command_pid=""
  local -a xpra_args=()
  local xauth_file=""
  local exit_code=0
  local waited=0

  case "$modal_policy" in
    fail|observe) ;;
    *)
      printf 'ONEC_DIRECT_PLATFORM_XPRA_MODAL_POLICY must be fail or observe\n' >&2
      exit 1
      ;;
  esac
  if command -v xwininfo >/dev/null 2>&1 && command -v xprop >/dev/null 2>&1; then
    modal_detection=1
  fi

  require_command xpra
  require_command flock
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
  xpra_cleanup_baseline="$xpra_root/process-cleanup-baseline.txt"
  ps -u "$UID" -o pid=,ppid=,comm=,cmd= \
    | awk '$2 == 1 || $2 ~ /^[0-9]+$/ { if (($3 == "dbus-daemon" && /--session/ && /--print-address/) || ($3 == "gvfsd" && $0 ~ /\/usr\/libexec\/gvfsd$/)) print $1 }' \
    >"$xpra_cleanup_baseline"
  xauth_file="$run_root/home/.Xauthority"
  mkdir -p "$(dirname -- "$xauth_file")"
  xpra_xvfb_args="${xpra_xvfb_args//\$\{XAUTHORITY\}/$xauth_file}"
  xpra_xvfb_args="${xpra_xvfb_args//\$XAUTHORITY/$xauth_file}"
  mkdir -p "$xpra_lock_dir"
  xpra_lock_file="$xpra_lock_dir/display.lock"
  (
    flock -x 9
    reap_dead_x_displays "$xpra_lock_dir"
    display_number="$(pick_unused_xpra_display_number)"
    display_value=":${display_number}"
    xpra_log="$xpra_root/xpra-${display_number}.log"
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

    XAUTHORITY="$xauth_file" ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN="$xpra_session_token" xpra "${xpra_args[@]}" 9>&- >&2

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
      stop_xpra_session "$display_value" "$xpra_session_token" "$xpra_cleanup_baseline"
      exit 1
    fi

    printf '%s\n%s\n' "$display_value" "$xpra_log" >"$xpra_root/active-display.env"
  ) 9>"$xpra_lock_file"
  display_value="$(sed -n '1p' "$xpra_root/active-display.env")"
  xpra_log="$(sed -n '2p' "$xpra_root/active-display.env")"
  trap 'stop_xpra_session "$display_value" "$xpra_session_token" "$xpra_cleanup_baseline"' EXIT INT TERM

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

  [ ! -e "$xpra_root/error-dialog.detected" ] || rm -f -- "$xpra_root/error-dialog.detected"
  set +e
  if [ -n "$ld_preload_value" ]; then
    DISPLAY="$display_value" XAUTHORITY="$xauth_file" ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN="$xpra_session_token" \
      env "LD_PRELOAD=$ld_preload_value" "$@" &
  else
    DISPLAY="$display_value" XAUTHORITY="$xauth_file" ONEC_DIRECT_PLATFORM_XPRA_SESSION_TOKEN="$xpra_session_token" "$@" &
  fi
  command_pid=$!
  write_command_pid_file "$command_pid"
  while kill -0 "$command_pid" 2>/dev/null; do
    if [ "$modal_detection" -eq 1 ] \
      && handle_modal_window "$display_value" "$xauth_file" "$xpra_root" "$command_pid" "$modal_policy"; then
      wait "$command_pid" 2>/dev/null
      exit_code=86
      break
    fi
    sleep 0.5
  done
  if [ "$exit_code" -eq 0 ]; then
    wait "$command_pid"
    exit_code=$?
  fi
  set -e

  stop_xpra_session "$display_value" "$xpra_session_token" "$xpra_cleanup_baseline"
  trap - EXIT INT TERM
  return "$exit_code"
}

command_name="${1##*/}"
apply_direct_platform_locale
# Клиент 1С сравнивает своё время со временем сервера кластера в системном часовом поясе.
# Унаследованный TZ даёт модальное окно о разнице времени, и автоматический запуск зависает.
unset TZ
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

case "$command_name" in
  1cv8|1cv8c)
    # После exec PID обёртки становится PID процесса платформы.
    write_command_pid_file "$$"
    ;;
esac

if [ -n "$ld_preload_value" ]; then
  exec env "LD_PRELOAD=$ld_preload_value" "$@"
fi

exec "$@"
