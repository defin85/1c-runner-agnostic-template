#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
listener_pid=""
trap 'if [ -n "${listener_pid:-}" ]; then kill "$listener_pid" >/dev/null 2>&1 || true; wait "$listener_pid" 2>/dev/null || true; fi; rm -rf "$tmpdir"' EXIT

source "$SOURCE_ROOT/scripts/lib/common.sh"
source "$SOURCE_ROOT/scripts/lib/onec-port-lease.sh"

export ONEC_TEST_PORT_LEASE_ROOT="$tmpdir/leases"
export ONEC_TEST_PORT_LEASE_REPO="fixture-repo"
lease_helper="$tmpdir/onec-test-port-lease"
export ONEC_TEST_PORT_LEASE_HELPER="$lease_helper"

cat >"$lease_helper" <<'PY'
#!/usr/bin/env python3
import json
import os
import socket
import sys
import time
from pathlib import Path

root = Path(os.environ["ONEC_TEST_PORT_LEASE_ROOT"])
root.mkdir(parents=True, exist_ok=True)
state_path = root / "leases.json"

def load_state():
    if not state_path.exists():
        return {"leases": []}
    return json.loads(state_path.read_text(encoding="utf-8"))

def save_state(state):
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def parse_options(items):
    result = {}
    i = 0
    while i < len(items):
        key = items[i]
        if not key.startswith("--"):
            raise SystemExit(f"unexpected argument: {key}")
        if i + 1 >= len(items):
            raise SystemExit(f"missing value for {key}")
        result[key[2:].replace("-", "_")] = items[i + 1]
        i += 2
    return result

def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True

def cmd_lease(args):
    options = parse_options(args)
    start, end = [int(part) for part in options["range"].split("-", 1)]
    size = int(options.get("size", "1"))
    state = load_state()
    used = {port for lease in state["leases"] for port in lease["ports"]}
    for port in range(start, end + 1):
        ports = list(range(port, port + size))
        if ports[-1] > end:
            break
        if any(candidate in used or not port_is_free(candidate) for candidate in ports):
            continue
        lease = {
            "lease_id": f"lease-{int(time.time() * 1000000)}-{port}",
            "service_id": options["service_id"],
            "repo": options["repo"],
            "role": options["role"],
            "range": options["range"],
            "start": port,
            "ports": ports,
            "pid": int(options["pid"]) if options.get("pid") else None,
        }
        state["leases"].append(lease)
        save_state(state)
        print(json.dumps(lease, ensure_ascii=False))
        return
    raise SystemExit("no free ports")

def cmd_release(args):
    options = parse_options(args)
    state = load_state()
    leases = state["leases"]
    if "lease_id" in options:
        leases = [lease for lease in leases if lease["lease_id"] != options["lease_id"]]
    else:
        leases = [
            lease for lease in leases
            if not (lease["service_id"] == options.get("service_id") and lease["role"] == options.get("role"))
        ]
    state["leases"] = leases
    save_state(state)

def main():
    if len(sys.argv) < 2:
        raise SystemExit("command is required")
    command = sys.argv[1]
    if command == "lease":
        cmd_lease(sys.argv[2:])
    elif command == "release":
        cmd_release(sys.argv[2:])
    elif command == "status":
        print(json.dumps(load_state(), ensure_ascii=False))
    else:
        raise SystemExit(f"unknown command: {command}")

if __name__ == "__main__":
    main()
PY
chmod +x "$lease_helper"

launcher_files=()
for candidate in \
  "$SOURCE_ROOT/tooling/vanessa/run-bdd.sh" \
  "$SOURCE_ROOT/scripts/test/run-bdd-service.sh"; do
  [ -f "$candidate" ] && launcher_files+=("$candidate")
done

if [ "${#launcher_files[@]}" -gt 0 ] && grep -Eq '47000[[:space:]]+47999|48000[[:space:]]+48999|48100[[:space:]]+48999' "${launcher_files[@]}"; then
  printf '1C launchers must not use legacy broad local-snapshot port ranges\n' >&2
  exit 1
fi

assert_jq() {
  local json_text="$1"
  local expr="$2"
  local label="$3"

  if ! printf '%s\n' "$json_text" | jq -e "$expr" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    printf '%s\n' "$json_text" >&2
    exit 1
  fi
}

port_from_lease() {
  printf '%s\n' "$1" | onec_port_lease_port_from_json
}

id_from_lease() {
  printf '%s\n' "$1" | onec_port_lease_id_from_json
}

lease_a="$(onec_port_lease_acquire contract-a testclient 48100-48105 1)"
lease_b="$(onec_port_lease_acquire contract-b testclient 48100-48105 1)"
port_a="$(port_from_lease "$lease_a")"
port_b="$(port_from_lease "$lease_b")"

if [ "$port_a" = "$port_b" ]; then
  printf 'simultaneous leases must not receive the same port: %s\n' "$port_a" >&2
  exit 1
fi
assert_jq "$lease_a" '.repo == "fixture-repo" and .role == "testclient"' "lease-a-metadata"
assert_jq "$lease_b" '.repo == "fixture-repo" and .role == "testclient"' "lease-b-metadata"

onec_port_lease_release_service_role contract-a testclient
onec_port_lease_release_by_id "$(id_from_lease "$lease_b")"

listener_port_file="$tmpdir/foreign-listener.port"
python3 - "$listener_port_file" <<'PY' &
import pathlib
import socket
import sys
import time

ready_path = pathlib.Path(sys.argv[1])
sock = None
for candidate in range(48100, 48106):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", candidate))
        sock.listen(1)
        ready_path.write_text(f"{candidate}\n", encoding="utf-8")
        break
    except OSError:
        if sock is not None:
            sock.close()
        sock = None
else:
    ready_path.write_text("ERROR\n", encoding="utf-8")
    sys.exit(3)

try:
    while True:
        time.sleep(1)
finally:
    if sock is not None:
        sock.close()
PY
listener_pid="$!"

for _ in $(seq 1 50); do
  [ -s "$listener_port_file" ] && break
  sleep 0.1
done

foreign_port="$(cat "$listener_port_file")"
case "$foreign_port" in
  ERROR|"")
    printf 'failed to start foreign listener in 48100-48105\n' >&2
    exit 1
    ;;
esac

lease_skip="$(onec_port_lease_acquire foreign-skip testclient 48100-48105 1)"
skip_port="$(port_from_lease "$lease_skip")"
if [ "$skip_port" = "$foreign_port" ]; then
  printf 'lease helper selected a live foreign listener port: %s\n' "$foreign_port" >&2
  exit 1
fi

onec_port_lease_release_by_id "$(id_from_lease "$lease_skip")"
status_json="$(onec_port_lease_status_json)"
assert_jq "$status_json" '.leases == []' "all-leases-released"
