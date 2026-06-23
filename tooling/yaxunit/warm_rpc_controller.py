#!/usr/bin/env python3
"""Small stdlib WebSocket controller for the YAxUnit warm RPC contour."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import signal
import struct
import time
from pathlib import Path
from typing import Any

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("__REDACTED_SECRET__" if key.lower() in {"key", "password", "pwd"} else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


async def read_ws_message(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> str | None:
    chunks: list[bytes] = []
    while True:
        header = await reader.readexactly(2)
        first, second = header
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", await reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await reader.readexactly(8))[0]

        mask = await reader.readexactly(4) if masked else b""
        payload = await reader.readexactly(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

        if opcode == 0x8:
            return None
        if opcode == 0x9:
            writer.write(bytes([0x8A, len(payload)]) + payload)
            await writer.drain()
            continue
        if opcode == 0xA:
            continue
        if opcode == 0x1:
            chunks = [payload]
        elif opcode == 0x0 and chunks:
            chunks.append(payload)
        else:
            continue

        if fin and chunks:
            return b"".join(chunks).decode("utf-8")


async def write_ws_text(writer: asyncio.StreamWriter, message: str) -> None:
    payload = message.encode("utf-8")
    # Keep server-to-client frames small for the 1C platform WebSocket client.
    # The protocol supports fragmentation, and this avoids relying on extended
    # payload-length handling in the live thin client.
    chunk_size = 120
    chunks = [payload[index : index + chunk_size] for index in range(0, len(payload), chunk_size)] or [b""]
    if len(chunks) > 1:
        for index, chunk in enumerate(chunks):
            opcode = 0x1 if index == 0 else 0x0
            fin = 0x80 if index == len(chunks) - 1 else 0x00
            header = bytearray([fin | opcode, len(chunk)])
            writer.write(bytes(header) + chunk)
        await writer.drain()
        return

    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    writer.write(bytes(header) + payload)
    await writer.drain()


async def websocket_handshake(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    request = await reader.readuntil(b"\r\n\r\n")
    headers: dict[str, str] = {}
    for raw_line in request.decode("iso-8859-1").split("\r\n")[1:]:
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    ws_key = headers.get("sec-websocket-key")
    if not ws_key:
        raise RuntimeError("missing Sec-WebSocket-Key")
    accept = base64.b64encode(hashlib.sha1((ws_key + WS_GUID).encode("ascii")).digest()).decode("ascii")
    writer.write(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    await writer.drain()


class Controller:
    def __init__(self, args: argparse.Namespace) -> None:
        self.host = args.host
        self.port = args.port
        self.key = args.key
        self.ready_file = Path(args.ready_file)
        self.command_dir = Path(args.command_dir)
        self.shutdown_file = Path(args.shutdown_file)
        self.events_jsonl = Path(args.events_jsonl)
        self.command_dir.mkdir(parents=True, exist_ok=True)
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.writer: asyncio.StreamWriter | None = None
        self.authenticated = asyncio.Event()
        self.shutdown = asyncio.Event()
        self.next_message_id = 1

    def event(self, event_type: str, **payload: Any) -> None:
        append_jsonl(self.events_jsonl, {"at": utc_now(), "event": event_type, **redact(payload)})

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        self.event("client-connected", peer=str(peer))
        try:
            await websocket_handshake(reader, writer)
            self.writer = writer
            while not self.shutdown.is_set():
                text = await read_ws_message(reader, writer)
                if text is None:
                    break
                if not text:
                    continue
                self.event("client-message", message=json.loads(text))
                await self.handle_message(json.loads(text))
        except Exception as exc:  # noqa: BLE001 - controller must record protocol failures.
            self.event("client-error", error=str(exc))
        finally:
            if self.writer is writer:
                self.writer = None
                self.authenticated.clear()
            writer.close()
            await writer.wait_closed()
            self.event("client-disconnected")

    async def handle_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        message_id = message.get("id")
        if message_type == "hello":
            data = message.get("data") if isinstance(message.get("data"), dict) else {}
            if data.get("key") != self.key:
                self.event("hello-rejected")
                if self.writer is not None:
                    self.writer.close()
                return
            self.ready_file.parent.mkdir(parents=True, exist_ok=True)
            self.ready_file.write_text("READY\n", encoding="utf-8")
            self.authenticated.set()
            self.event("hello-accepted", protocol_version=data.get("protocolVersion"))
            return

        if message_type == "report" and isinstance(message_id, int) and message_id in self.pending:
            future = self.pending.pop(message_id)
            if not future.done():
                future.set_result(message)
            return

        if message_type == "reportFile":
            self.event("report-file", message=message)

    async def command_loop(self) -> None:
        while not self.shutdown.is_set():
            if self.shutdown_file.exists() and self.shutdown_file.read_text(encoding="utf-8").strip():
                self.event("shutdown-file-seen")
                self.shutdown.set()
                break

            for request_path in sorted(self.command_dir.glob("*.request.json")):
                await self.process_request(request_path)
            await asyncio.sleep(0.2)

    async def process_request(self, request_path: Path) -> None:
        processing_path = request_path.with_suffix(".processing.json")
        try:
            request_path.replace(processing_path)
            request = json.loads(processing_path.read_text(encoding="utf-8"))
            if request.get("type") == "shutdown":
                self.shutdown.set()
                write_json(Path(request["result_path"]), {"status": "success", "classification": "success", "finished_at": utc_now()})
                processing_path.unlink(missing_ok=True)
                return
            if request.get("type") != "run":
                raise RuntimeError(f"unsupported command type: {request.get('type')}")
            await self.run_test(request)
        except Exception as exc:  # noqa: BLE001 - command failures are reported as artifacts.
            result_path = None
            try:
                request = json.loads(processing_path.read_text(encoding="utf-8"))
                result_path = Path(request["result_path"])
            except Exception:
                pass
            if result_path is not None:
                write_json(result_path, {"status": "failed", "classification": "protocol failed", "message": str(exc), "finished_at": utc_now()})
            self.event("command-error", request_path=str(request_path), error=str(exc))
        finally:
            processing_path.unlink(missing_ok=True)

    async def run_test(self, request: dict[str, Any]) -> None:
        result_path = Path(request["result_path"])
        raw_request_path = Path(request["raw_request_path"])
        raw_response_path = Path(request["raw_response_path"])
        timeout_seconds = int(request.get("timeout_seconds") or 300)

        if not self.authenticated.is_set() or self.writer is None:
            write_json(result_path, {"status": "failed", "classification": "handshake failed", "message": "YAxUnit client is not connected", "finished_at": utc_now()})
            return

        message_id = self.next_message_id
        self.next_message_id += 1
        message = {
            "type": "runTest",
            "id": message_id,
            "data": {
                "module": request["module"],
                "moduleName": request["moduleName"],
                "methods": request["methods"],
                "client": bool(request.get("client")),
                "ordinaryClient": bool(request.get("ordinaryClient")),
                "server": bool(request.get("server")),
            },
        }
        write_json(raw_request_path, redact(message))

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[message_id] = future
        await write_ws_text(self.writer, json.dumps(message, ensure_ascii=False, separators=(",", ":")))
        self.event("run-test-sent", id=message_id, module_name=request["moduleName"], methods=request["methods"])

        try:
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.pending.pop(message_id, None)
            write_json(result_path, {"status": "failed", "classification": "timeout", "message": "Timed out waiting for YAxUnit report", "finished_at": utc_now()})
            return

        write_json(raw_response_path, redact(response))
        write_json(result_path, {"status": "success", "classification": "success", "message": "YAxUnit report received", "report": response.get("data"), "finished_at": utc_now()})

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.shutdown.set)
            except NotImplementedError:
                pass

        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        self.event("listening", host=self.host, port=self.port)
        async with server:
            command_task = asyncio.create_task(self.command_loop())
            await self.shutdown.wait()
            command_task.cancel()
            if self.writer is not None:
                self.writer.close()
            server.close()
            await server.wait_closed()
        self.event("stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--key", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--command-dir", required=True)
    parser.add_argument("--shutdown-file", required=True)
    parser.add_argument("--events-jsonl", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(Controller(args).run())


if __name__ == "__main__":
    main()
