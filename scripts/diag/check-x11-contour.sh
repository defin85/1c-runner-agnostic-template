#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../lib/capability.sh
source "$SCRIPT_DIR/../lib/capability.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/diag/check-x11-contour.sh [options]

Options:
  --run-root <dir>   Directory for summary.json and diagnostic artifacts
  --dry-run          Resolve static checks and write summary without probe execution
  -h, --help         Show this help
EOF
}

json_array_from_args() {
  require_command jq
  if [ "$#" -eq 0 ]; then
    printf '[]\n'
    return 0
  fi

  jq -cn '$ARGS.positional' --args -- "$@"
}

list_has_token() {
  local haystack="$1"
  local needle="$2"
  local token=""

  for token in $haystack; do
    if [ "$token" = "$needle" ]; then
      return 0
    fi
  done

  return 1
}

mark_failure() {
  local reason="$1"

  FAILURE_REASONS+=("$reason")
  printf 'check failed: %s\n' "$reason" >&2
}

CAPABILITY_ID="check-x11-contour"
CAPABILITY_LABEL="WSLg X11 contour check"
RUN_ROOT_INPUT=""
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-root)
      [ "$#" -ge 2 ] || die "--run-root requires a value"
      RUN_ROOT_INPUT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

require_command jq
require_command findmnt
require_command systemctl
require_command stat
require_command mktemp
require_command xvfb-run
require_command xauth
require_command xdpyinfo

RUN_ROOT="$(prepare_capability_run_root "$CAPABILITY_ID" "$RUN_ROOT_INPUT")"
SUMMARY_PATH="$(capability_summary_path "$RUN_ROOT")"
STDOUT_LOG="$RUN_ROOT/stdout.log"
STDERR_LOG="$RUN_ROOT/stderr.log"
WSLG_UNIT_FILE="$RUN_ROOT/wslg.service.txt"
FIX_UNIT_FILE="$RUN_ROOT/fix-x11-unix.service.txt"
FINDMNT_JSON="$RUN_ROOT/findmnt.json"
XVFB_PROBE_STDOUT="$RUN_ROOT/xvfb-probe.stdout.log"
XVFB_PROBE_STDERR="$RUN_ROOT/xvfb-probe.stderr.log"

: >"$STDOUT_LOG"
: >"$STDERR_LOG"
: >"$WSLG_UNIT_FILE"
: >"$FIX_UNIT_FILE"
: >"$FINDMNT_JSON"
: >"$XVFB_PROBE_STDOUT"
: >"$XVFB_PROBE_STDERR"

exec 3>&1 4>&2
exec > >(tee -a "$STDOUT_LOG" >&3) 2> >(tee -a "$STDERR_LOG" >&4)

declare -a FAILURE_REASONS=()
STATUS="success"
EXIT_CODE=0
STARTED_AT="$(timestamp_utc)"

WSLG_SERVICE_PRESENT=false
WSLG_EXECSTART=""
WSLG_RO_BIND=false
FIX_SERVICE_PRESENT=false
FIX_SERVICE_UNIT_STATE=""
FIX_SERVICE_ACTIVE_STATE=""
FIX_SERVICE_AFTER=""
FIX_SERVICE_WANTS=""
FIX_SERVICE_AFTER_WSLG=false
FIX_SERVICE_WANTS_WSLG=false
FIX_SERVICE_REQUIRED=false
TARGET_EXISTS=false
TARGET_MODE=""
TARGET_PERMS=""
TARGET_OWNER=""
MOUNTS_JSON='{"filesystems":[]}'
RW_MOUNT_PRESENT=false
WRITE_PROBE_STATUS="skipped"
WRITE_PROBE_PATH=""
WRITE_PROBE_REASON=""
XVFB_PROBE_STATUS="skipped"
XVFB_PROBE_DISPLAY=""
XVFB_PROBE_SOCKET_PRESENT=false
XVFB_PROBE_OK=false
XVFB_PROBE_REASON=""

log "$CAPABILITY_LABEL"
log "run_root=$RUN_ROOT"

if systemctl cat wslg.service >"$WSLG_UNIT_FILE" 2>>"$STDERR_LOG"; then
  WSLG_SERVICE_PRESENT=true
  WSLG_EXECSTART="$(sed -n 's/^ExecStart=//p' "$WSLG_UNIT_FILE" | head -n 1)"
  if [[ "$WSLG_EXECSTART" == *"bind,ro"* ]] && [[ "$WSLG_EXECSTART" == *"/tmp/.X11-unix"* ]]; then
    WSLG_RO_BIND=true
    FIX_SERVICE_REQUIRED=true
  fi
else
  printf 'wslg.service is not present in systemd\n' >>"$STDERR_LOG"
fi

if systemctl cat fix-x11-unix.service >"$FIX_UNIT_FILE" 2>>"$STDERR_LOG"; then
  FIX_SERVICE_PRESENT=true
  FIX_SERVICE_UNIT_STATE="$(systemctl show -P UnitFileState fix-x11-unix.service 2>>"$STDERR_LOG" || true)"
  FIX_SERVICE_ACTIVE_STATE="$(systemctl show -P ActiveState fix-x11-unix.service 2>>"$STDERR_LOG" || true)"
  FIX_SERVICE_AFTER="$(systemctl show -P After fix-x11-unix.service 2>>"$STDERR_LOG" || true)"
  FIX_SERVICE_WANTS="$(systemctl show -P Wants fix-x11-unix.service 2>>"$STDERR_LOG" || true)"
  if list_has_token "$FIX_SERVICE_AFTER" "wslg.service"; then
    FIX_SERVICE_AFTER_WSLG=true
  fi
  if list_has_token "$FIX_SERVICE_WANTS" "wslg.service"; then
    FIX_SERVICE_WANTS_WSLG=true
  fi
fi

if [ "$FIX_SERVICE_REQUIRED" = true ]; then
  if [ "$FIX_SERVICE_PRESENT" != true ]; then
    mark_failure "missing fix-x11-unix.service while wslg.service bind-mounts /tmp/.X11-unix as ro"
  fi
  if [ "$FIX_SERVICE_UNIT_STATE" != "enabled" ]; then
    mark_failure "fix-x11-unix.service must be enabled when wslg.service bind-mounts /tmp/.X11-unix as ro"
  fi
  if [ "$FIX_SERVICE_ACTIVE_STATE" != "active" ]; then
    mark_failure "fix-x11-unix.service must be active when wslg.service bind-mounts /tmp/.X11-unix as ro"
  fi
  if [ "$FIX_SERVICE_AFTER_WSLG" != true ]; then
    mark_failure "fix-x11-unix.service must start after wslg.service"
  fi
  if [ "$FIX_SERVICE_WANTS_WSLG" != true ]; then
    mark_failure "fix-x11-unix.service must want wslg.service"
  fi
fi

if [ -d /tmp/.X11-unix ]; then
  TARGET_EXISTS=true
  TARGET_MODE="$(stat -c '%a' /tmp/.X11-unix)"
  TARGET_PERMS="$(stat -c '%A' /tmp/.X11-unix)"
  TARGET_OWNER="$(stat -c '%U:%G' /tmp/.X11-unix)"
else
  mark_failure "/tmp/.X11-unix is missing"
fi

if [ "$TARGET_EXISTS" = true ] && [ "$TARGET_MODE" != "1777" ]; then
  mark_failure "/tmp/.X11-unix must have mode 1777, got $TARGET_MODE"
fi

if findmnt -R -J /tmp/.X11-unix -o TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION >"$FINDMNT_JSON" 2>>"$STDERR_LOG"; then
  MOUNTS_JSON="$(cat "$FINDMNT_JSON")"
  if jq -e '.filesystems | any(.options | split(",") | index("rw"))' "$FINDMNT_JSON" >/dev/null; then
    RW_MOUNT_PRESENT=true
  fi
else
  mark_failure "findmnt could not resolve /tmp/.X11-unix"
fi

if [ "$RW_MOUNT_PRESENT" != true ]; then
  mark_failure "/tmp/.X11-unix does not expose an rw mount layer"
fi

if [ "$DRY_RUN" = "1" ]; then
  STATUS="dry-run"
else
  set +e
  WRITE_PROBE_PATH="$(mktemp /tmp/.X11-unix/.codex-x11-probe.XXXXXX 2>>"$STDERR_LOG")"
  write_probe_exit=$?
  set -e
  if [ "$write_probe_exit" -eq 0 ]; then
    WRITE_PROBE_STATUS="success"
    rm -f "$WRITE_PROBE_PATH"
  else
    WRITE_PROBE_STATUS="failed"
    WRITE_PROBE_REASON="mktemp could not create a probe file inside /tmp/.X11-unix"
    mark_failure "$WRITE_PROBE_REASON"
  fi

  set +e
  xvfb-run -a --error-file="$XVFB_PROBE_STDERR" \
    bash -lc 'echo DISPLAY=$DISPLAY; display_number="${DISPLAY#:}"; test -S "/tmp/.X11-unix/X${display_number}" && echo socket_ok; xdpyinfo >/dev/null && echo xvfb_ok' \
    >"$XVFB_PROBE_STDOUT" 2>>"$XVFB_PROBE_STDERR"
  xvfb_probe_exit=$?
  set -e

  if [ "$xvfb_probe_exit" -eq 0 ]; then
    XVFB_PROBE_DISPLAY="$(sed -n 's/^DISPLAY=//p' "$XVFB_PROBE_STDOUT" | tail -n 1)"
    if grep -Fxq 'socket_ok' "$XVFB_PROBE_STDOUT"; then
      XVFB_PROBE_SOCKET_PRESENT=true
    fi
    if grep -Fxq 'xvfb_ok' "$XVFB_PROBE_STDOUT"; then
      XVFB_PROBE_OK=true
    fi

    if [ "$XVFB_PROBE_SOCKET_PRESENT" = true ] && [ "$XVFB_PROBE_OK" = true ]; then
      XVFB_PROBE_STATUS="success"
    else
      XVFB_PROBE_STATUS="failed"
      XVFB_PROBE_REASON="xvfb probe did not observe both socket_ok and xvfb_ok markers"
      mark_failure "$XVFB_PROBE_REASON"
    fi
  else
    XVFB_PROBE_STATUS="failed"
    XVFB_PROBE_REASON="xvfb-run probe exited with code $xvfb_probe_exit"
    mark_failure "$XVFB_PROBE_REASON"
  fi
fi

if [ "${#FAILURE_REASONS[@]}" -gt 0 ] && [ "$STATUS" != "dry-run" ]; then
  STATUS="failed"
  EXIT_CODE=65
fi

FAILURES_JSON="$(json_array_from_args "${FAILURE_REASONS[@]}")"
CONTEXT_JSON="$(jq -cn \
  --arg target_path "/tmp/.X11-unix" \
  --arg expected_mode "1777" \
  --arg x11_fix_service "fix-x11-unix.service" \
  --arg wslg_service "wslg.service" \
  --argjson wslg_service_present "$WSLG_SERVICE_PRESENT" \
  --arg wslg_execstart "$WSLG_EXECSTART" \
  --argjson wslg_ro_bind "$WSLG_RO_BIND" \
  --argjson fix_service_required "$FIX_SERVICE_REQUIRED" \
  --argjson fix_service_present "$FIX_SERVICE_PRESENT" \
  --arg fix_service_unit_state "$FIX_SERVICE_UNIT_STATE" \
  --arg fix_service_active_state "$FIX_SERVICE_ACTIVE_STATE" \
  --arg fix_service_after "$FIX_SERVICE_AFTER" \
  --arg fix_service_wants "$FIX_SERVICE_WANTS" \
  --argjson fix_service_after_wslg "$FIX_SERVICE_AFTER_WSLG" \
  --argjson fix_service_wants_wslg "$FIX_SERVICE_WANTS_WSLG" \
  --argjson target_exists "$TARGET_EXISTS" \
  --arg target_mode "$TARGET_MODE" \
  --arg target_perms "$TARGET_PERMS" \
  --arg target_owner "$TARGET_OWNER" \
  --argjson rw_mount_present "$RW_MOUNT_PRESENT" \
  --argjson mounts "$MOUNTS_JSON" \
  --arg write_probe_status "$WRITE_PROBE_STATUS" \
  --arg write_probe_path "$WRITE_PROBE_PATH" \
  --arg write_probe_reason "$WRITE_PROBE_REASON" \
  --arg xvfb_probe_status "$XVFB_PROBE_STATUS" \
  --arg xvfb_probe_display "$XVFB_PROBE_DISPLAY" \
  --arg xvfb_probe_reason "$XVFB_PROBE_REASON" \
  --argjson xvfb_probe_socket_present "$XVFB_PROBE_SOCKET_PRESENT" \
  --argjson xvfb_probe_ok "$XVFB_PROBE_OK" \
  --arg wslg_unit_file "$WSLG_UNIT_FILE" \
  --arg fix_unit_file "$FIX_UNIT_FILE" \
  --arg findmnt_json "$FINDMNT_JSON" \
  --arg xvfb_probe_stdout "$XVFB_PROBE_STDOUT" \
  --arg xvfb_probe_stderr "$XVFB_PROBE_STDERR" \
  --argjson failure_reasons "$FAILURES_JSON" \
  '{
    expected: {
      target_path: $target_path,
      target_mode: $expected_mode,
      fix_service: $x11_fix_service,
      wslg_service: $wslg_service
    },
    wslg: {
      service_present: $wslg_service_present,
      exec_start: (if $wslg_execstart == "" then null else $wslg_execstart end),
      bind_ro_x11_unix: $wslg_ro_bind
    },
    fix_service: {
      required: $fix_service_required,
      present: $fix_service_present,
      unit_file_state: (if $fix_service_unit_state == "" then null else $fix_service_unit_state end),
      active_state: (if $fix_service_active_state == "" then null else $fix_service_active_state end),
      after: (if $fix_service_after == "" then [] else ($fix_service_after | split(" ")) end),
      wants: (if $fix_service_wants == "" then [] else ($fix_service_wants | split(" ")) end),
      after_wslg: $fix_service_after_wslg,
      wants_wslg: $fix_service_wants_wslg
    },
    target: {
      exists: $target_exists,
      mode: (if $target_mode == "" then null else $target_mode end),
      perms: (if $target_perms == "" then null else $target_perms end),
      owner: (if $target_owner == "" then null else $target_owner end),
      rw_mount_present: $rw_mount_present,
      mounts: $mounts
    },
    probes: {
      write_probe: {
        status: $write_probe_status,
        path: (if $write_probe_path == "" then null else $write_probe_path end),
        reason: (if $write_probe_reason == "" then null else $write_probe_reason end)
      },
      xvfb_probe: {
        status: $xvfb_probe_status,
        display: (if $xvfb_probe_display == "" then null else $xvfb_probe_display end),
        socket_present: $xvfb_probe_socket_present,
        xdpyinfo_ok: $xvfb_probe_ok,
        reason: (if $xvfb_probe_reason == "" then null else $xvfb_probe_reason end)
      }
    },
    x11_artifacts: {
      wslg_unit_file: $wslg_unit_file,
      fix_unit_file: $fix_unit_file,
      findmnt_json: $findmnt_json,
      xvfb_probe_stdout_log: $xvfb_probe_stdout,
      xvfb_probe_stderr_log: $xvfb_probe_stderr
    },
    failure_reasons: $failure_reasons
  }')"

FINISHED_AT="$(timestamp_utc)"
write_capability_summary \
  "$SUMMARY_PATH" \
  "$STATUS" \
  "$CAPABILITY_ID" \
  "$CAPABILITY_LABEL" \
  "operator-local" \
  "" \
  "" \
  "$RUN_ROOT" \
  "$EXIT_CODE" \
  "$STARTED_AT" \
  "$FINISHED_AT" \
  "$STDOUT_LOG" \
  "$STDERR_LOG" \
  "$DRY_RUN" \
  "builtin-x11-check" \
  "direct" \
  "$CONTEXT_JSON"

log "summary_json=$SUMMARY_PATH"

if [ "$STATUS" = "failed" ]; then
  exit "$EXIT_CODE"
fi
