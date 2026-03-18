#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"

if [ "$#" -eq 0 ]; then
  printf 'usage: %s <command> [args...]\n' "$0" >&2
  exit 1
fi

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

command_name="${1##*/}"
ld_preload_value=""
if [ "$command_name" = "1cv8" ] || [ "$command_name" = "1cv8c" ]; then
  ld_preload_value="$(build_ld_preload_value)"
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
