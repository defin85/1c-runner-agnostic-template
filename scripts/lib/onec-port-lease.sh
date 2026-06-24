#!/usr/bin/env bash

ONEC_PORT_LEASE_DEFAULT_HELPER="onec-test-port-lease"

onec_port_lease_helper_path() {
  local repo_helper=""
  local path_helper=""

  if [ -n "${ONEC_TEST_PORT_LEASE_HELPER:-}" ]; then
    printf '%s\n' "$ONEC_TEST_PORT_LEASE_HELPER"
    return 0
  fi

  path_helper="$(command -v "$ONEC_PORT_LEASE_DEFAULT_HELPER" 2>/dev/null || true)"
  if [ -n "$path_helper" ]; then
    printf '%s\n' "$path_helper"
    return 0
  fi

  repo_helper="$(project_root)/scripts/tools/onec-test-port-lease"
  printf '%s\n' "$repo_helper"
}

onec_port_lease_repo() {
  if [ -n "${ONEC_TEST_PORT_LEASE_REPO:-}" ]; then
    printf '%s\n' "$ONEC_TEST_PORT_LEASE_REPO"
    return 0
  fi

  basename -- "$(project_root)"
}

onec_port_lease_require_helper() {
  local helper_path=""

  helper_path="$(onec_port_lease_helper_path)"
  [ -x "$helper_path" ] || die "1C port lease helper is required for operator-local WSL contours: $helper_path"
}

onec_port_lease_acquire() {
  local service_id="$1"
  local role="$2"
  local range_value="$3"
  local size="${4:-1}"
  local pid="${5:-}"
  local helper_path=""
  local -a args=()

  require_command jq
  onec_port_lease_require_helper
  helper_path="$(onec_port_lease_helper_path)"
  args=(
    lease
    --service-id "$service_id"
    --repo "$(onec_port_lease_repo)"
    --role "$role"
    --range "$range_value"
    --size "$size"
  )
  if [ -n "$pid" ]; then
    args+=(--pid "$pid")
  fi

  "$helper_path" "${args[@]}"
}

onec_port_lease_release_by_id() {
  local lease_id="${1:-}"
  local helper_path=""

  [ -n "$lease_id" ] || return 0
  onec_port_lease_require_helper
  helper_path="$(onec_port_lease_helper_path)"
  "$helper_path" release --lease-id "$lease_id" >/dev/null
}

onec_port_lease_release_service_role() {
  local service_id="$1"
  local role="$2"
  local helper_path=""

  [ -n "$service_id" ] || return 0
  onec_port_lease_require_helper
  helper_path="$(onec_port_lease_helper_path)"
  "$helper_path" release --service-id "$service_id" --role "$role" >/dev/null
}

onec_port_lease_status_json() {
  local helper_path=""

  onec_port_lease_require_helper
  helper_path="$(onec_port_lease_helper_path)"
  "$helper_path" status
}

onec_port_lease_port_from_json() {
  jq -er '.ports[0] // .start'
}

onec_port_lease_id_from_json() {
  jq -er '.lease_id'
}
