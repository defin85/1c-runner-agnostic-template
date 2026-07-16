#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
cleanup() {
  local status=$?
  if [ "$status" -ne 0 ]; then
    find "$tmpdir" -name summary.json -o -name service-state.json -o -name '*.stderr.log' -o -name '*.stdout.log' -o -name events.jsonl 2>/dev/null | sort >&2 || true
  else
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT

fixture_root="$tmpdir/repo"
fake_bin="$tmpdir/bin"
fake_sleep_bin="$tmpdir/bin-sleep"
state_root="$tmpdir/state"
invocation_log="$tmpdir/stage-invocations.log"
profile_path="$fixture_root/env/local.json"
sleep_profile_path="$fixture_root/env/sleep.json"
sync_run_root="$tmpdir/sync-run"
up_run_root="$tmpdir/up-run"
run_root="$tmpdir/warm-run"
failed_run_root="$tmpdir/failed-run"
timeout_run_root="$tmpdir/timeout-run"
status_run_root="$tmpdir/status-run"
post_sync_run_root="$tmpdir/post-sync-run"
stale_run_root="$tmpdir/stale-run"
input_fail_run_root="$tmpdir/input-fail-run"
startup_fail_run_root="$tmpdir/startup-fail-run"
handshake_fail_run_root="$tmpdir/handshake-fail-run"
down_run_root="$tmpdir/down-run"

mkdir -p "$fixture_root" "$fake_bin" "$fake_sleep_bin" "$state_root"
cp -R "$SOURCE_ROOT/scripts" "$fixture_root/scripts"
cp -R "$SOURCE_ROOT/tooling" "$fixture_root/tooling"
mkdir -p \
  "$fixture_root/env" \
  "$(dirname -- "$fixture_root/$module_rel")" \
  "$tmpdir/file-ib"

cat >"$fixture_root/$module_rel" <<'EOF'
Процедура ИсполняемыеСценарии() Экспорт
КонецПроцедуры

Процедура ОткрытьФорму_ЗащитаПерсональныхДанных_Основная() Экспорт
КонецПроцедуры
EOF

cat >"$fake_bin/1cv8" <<'EOF'
#!/usr/bin/env bash
printf '1cv8 should not be used directly\n' >&2
exit 99
EOF

cat >"$fake_bin/1cv8c" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

config=""
out=""
read_next_c_payload=0
for arg in "$@"; do
  if [ "$read_next_c_payload" = "1" ]; then
    case "$arg" in
      RunUnitTests=*)
        config="${arg#RunUnitTests=}"
        ;;
    esac
    read_next_c_payload=0
    continue
  fi
  case "$arg" in
    /CRunUnitTests=*)
      config="${arg#/CRunUnitTests=}"
      ;;
    /C)
      read_next_c_payload=1
      ;;
    /out*)
      out="${arg#/out}"
      ;;
  esac
done

[ -n "$config" ] || { printf 'missing RunUnitTests config\n' >&2; exit 41; }
[ -f "$config" ] || { printf 'config not found: %s\n' "$config" >&2; exit 42; }
if [ -n "$out" ]; then
  mkdir -p "$(dirname -- "$out")"
  printf 'fake warm 1cv8c run\n' >"$out"
fi

python3 - "$config" <<'PY'
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time

config = json.load(open(sys.argv[1], encoding="utf-8"))
assert config["ВыполнятьМодульноеТестирование"] is True
assert config["rpc"]["enable"] is True
assert config["rpc"]["transport"] == "ws"
assert config["closeAfterTests"] is False
assert config["showReport"] is True
port = int(config["rpc"]["port"])
key = config["rpc"]["key"]


def read_frame(sock):
    message = b""
    while True:
        header = sock.recv(2)
        if not header:
            return None
        first, second = header
        fin = bool(first & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", sock.recv(8))[0]
        payload = b""
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                return None
            payload += chunk
        opcode = first & 0x0F
        if opcode == 0x8:
            return None
        if opcode in (0x1, 0x0):
            message += payload
        if fin:
            return message.decode("utf-8")


def write_frame(sock, message):
    payload = message.encode("utf-8")
    mask = os.urandom(4)
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(bytes(header) + mask + masked)


sock = socket.create_connection(("127.0.0.1", port), timeout=10)
ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
request = (
    "GET / HTTP/1.1\r\n"
    f"Host: 127.0.0.1:{port}\r\n"
    "Upgrade: websocket\r\n"
    "Connection: Upgrade\r\n"
    f"Sec-WebSocket-Key: {ws_key}\r\n"
    "Sec-WebSocket-Version: 13\r\n"
    "\r\n"
)
sock.sendall(request.encode("ascii"))
response = sock.recv(4096)
if b"101 Switching Protocols" not in response:
    raise SystemExit("websocket handshake failed")

write_frame(sock, json.dumps({"type": "hello", "id": 0, "data": {"protocolVersion": "1.0.0", "key": key}}, ensure_ascii=False))
while True:
    text = read_frame(sock)
    if text is None:
        break
    message = json.loads(text)
    if message.get("type") != "runTest":
        continue
    data = message["data"]
    method = data["methods"][0]
    if method.endswith(".NoReport"):
        continue
    if method.endswith(".FailingMethod"):
        report = [{"name": "Fixture", "tests": 1, "errors": 1, "failures": 0, "testcase": [{"name": method, "error": [{"message": "fixture failure"}]}]}]
    else:
        report = [{"НаборыТестов": [{"Тесты": [{"Имя": method, "Статус": "Passed"}]}]}]
    write_frame(sock, json.dumps({"type": "report", "id": message["id"], "data": report}, ensure_ascii=False))
    time.sleep(0.1)
PY
EOF

cat >"$fake_bin/ibcmd" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

chmod +x "$fake_bin/1cv8" "$fake_bin/1cv8c" "$fake_bin/ibcmd"

cat >"$fake_sleep_bin/1cv8" <<'EOF'
#!/usr/bin/env bash
printf '1cv8 should not be used directly\n' >&2
exit 99
EOF

cat >"$fake_sleep_bin/1cv8c" <<'EOF'
#!/usr/bin/env bash
sleep 30
EOF

cat >"$fake_sleep_bin/ibcmd" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

chmod +x "$fake_sleep_bin/1cv8" "$fake_sleep_bin/1cv8c" "$fake_sleep_bin/ibcmd"

write_stage_stub() {
  local path="$1"
  cat >"$path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

run_root=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-root)
      run_root="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

[ -n "$run_root" ] || { printf 'missing --run-root\n' >&2; exit 64; }
mkdir -p "$run_root"
jq -n --arg status success --arg stage "$(basename -- "$0")" '{
  status: $status,
  stage: $stage,
  failure: null
}' >"$run_root/summary.json"
EOF
  chmod +x "$path"
}

write_stage_stub "$fixture_root/scripts/platform/load-cfe.sh"
write_stage_stub "$fixture_root/scripts/platform/configure-cfe-runtime-flags.sh"
write_stage_stub "$fixture_root/scripts/platform/check-cfe-applicability.sh"
write_stage_stub "$fixture_root/scripts/platform/check-cfe-config.sh"
write_stage_stub "$fixture_root/scripts/platform/update-db.sh"

cat >"$profile_path" <<EOF
{
  "schemaVersion": 2,
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_bin/1cv8",
    "ibcmdPath": "$fake_bin/ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/file-ib",
    "auth": {
      "mode": "os"
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/ibcmd-data"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/file-ib"
    }
  },
  "capabilities": {
    "updateDb": {
      "driver": "ibcmd"
    }
  }
}
EOF

cat >"$sleep_profile_path" <<EOF
{
  "schemaVersion": 2,
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_sleep_bin/1cv8",
    "ibcmdPath": "$fake_sleep_bin/ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "$tmpdir/file-ib",
    "auth": {
      "mode": "os"
    }
  },
  "ibcmd": {
    "runtimeMode": "file-infobase",
    "serverAccess": {
      "mode": "data-dir",
      "dataDir": "$tmpdir/ibcmd-data-sleep"
    },
    "fileInfobase": {
      "databasePath": "$tmpdir/file-ib"
    }
  },
  "capabilities": {
    "updateDb": {
      "driver": "ibcmd"
    }
  }
}
EOF

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"

  if grep -Fq -- "$unexpected" "$file"; then
    printf 'unexpected text found: %s\n' "$unexpected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"

  if ! jq -e "$expr" "$file" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

: >"$invocation_log"
(
  cd "$fixture_root"
)

(
  cd "$fixture_root"
)

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 65 ]; then
  printf 'unexpected startup failure exit code: %s\n' "$status" >&2
  exit 1
fi
assert_jq "$startup_fail_run_root/summary.json" '.status == "failed" and .classification == "startup failed"' "startup-fail"

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 65 ]; then
  printf 'unexpected handshake failure exit code: %s\n' "$status" >&2
  exit 1
fi
assert_jq "$handshake_fail_run_root/summary.json" '.status == "failed" and .classification == "handshake failed"' "handshake-fail"

(
  cd "$fixture_root"
)

assert_jq "$up_run_root/summary.json" '.status == "success" and .classification == "success"' "up-summary"
state_path="$(jq -r '.service.state_json' "$up_run_root/summary.json")"
warm_config="$(jq -r '.service.warm_config' "$up_run_root/summary.json")"
assert_jq "$state_path" '.state == "ready" and .rpc.host == "127.0.0.1" and .rpc.key == "__REDACTED_SECRET__"' "state-ready"

(
  cd "$fixture_root"
    --profile "$profile_path" \
    --run-root "$run_root" \
    --module-file "$module_rel" \
    --method "ОткрытьФорму_ЗащитаПерсональныхДанных_Основная" \
    --client \
    --timeout 20 >/dev/null
)

assert_jq "$run_root/summary.json" '.status == "success" and .classification == "success"' "run-summary"
history_bundle="$(jq -r '.history_bundle' "$run_root/summary.json")"
assert_jq "$history_bundle/normalized-report.json" '.test_count == 1 and .failed_count == 0' "normalized-report"
assert_contains "$history_bundle/raw-rpc-request.json" "runTest"
assert_not_contains "$history_bundle/raw-rpc-request.json" "__SECRET_SEEN__"

set +e
(
  cd "$fixture_root"
    --profile "$profile_path" \
    --run-root "$failed_run_root" \
    --module-file "$module_rel" \
    --method "FailingMethod" \
    --client \
    --timeout 20 >/dev/null 2>"$tmpdir/failed.stderr"
)
status=$?
set -e

if [ "$status" -ne 1 ]; then
  printf 'unexpected tests-failed exit code: %s\n' "$status" >&2
  exit 1
fi
assert_jq "$failed_run_root/summary.json" '.status == "failed" and .classification == "tests failed"' "tests-failed"

set +e
(
  cd "$fixture_root"
    --profile "$profile_path" \
    --run-root "$timeout_run_root" \
    --module-file "$module_rel" \
    --method "NoReport" \
    --client \
    --timeout 2 >/dev/null 2>"$tmpdir/timeout.stderr"
)
status=$?
set -e

if [ "$status" -ne 66 ]; then
  printf 'unexpected timeout exit code: %s\n' "$status" >&2
  exit 1
fi
assert_jq "$timeout_run_root/summary.json" '.status == "failed" and .classification == "timeout"' "timeout"

set +e
(
  cd "$fixture_root"
)
status=$?
set -e

if [ "$status" -ne 66 ]; then
  printf 'unexpected input failure exit code: %s\n' "$status" >&2
  exit 1
fi
assert_jq "$input_fail_run_root/summary.json" '.status == "failed" and .classification == "protocol failed"' "input-fail"
assert_contains "$input_fail_run_root/summary.json" "temporary module payloads"

(
  cd "$fixture_root"
)
assert_jq "$status_run_root/summary.json" '.status == "success" and .service.state == "ready"' "status-summary"

sleep 1
(
  cd "$fixture_root"
)

set +e
(
  cd "$fixture_root"
    --profile "$profile_path" \
    --run-root "$stale_run_root" \
    --module-file "$module_rel" \
    --method "ОткрытьФорму_ЗащитаПерсональныхДанных_Основная" \
    --client \
    --timeout 20 >/dev/null 2>"$tmpdir/stale.stderr"
)
status=$?
set -e

if [ "$status" -ne 66 ]; then
  printf 'unexpected stale-run exit code: %s\n' "$status" >&2
  exit 1
fi
assert_contains "$stale_run_root/summary.json" "refreshed after service startup"

(
  cd "$fixture_root"
)
assert_jq "$down_run_root/summary.json" '.status == "success" and .service.state == "stopped"' "down-summary"
