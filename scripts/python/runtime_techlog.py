"""Bounded technological log for exactly one observed 1C launch.

The session temporarily installs a bounded ``logcfg.xml`` (EXCP, TDEADLOCK,
TTIMEOUT, long TLOCK only), opens an operation cursor over the log location and
restores the original ``logcfg.xml`` byte for byte when the launch finishes or
fails. It is enabled only when the operator sets ``TECHLOG_CONFIG_PATH``.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

from .runtime_errors import CommandError
from .runtime_lock import ResourceLock
from .runtime_os import process_is_alive

CONFIG_MARKER = "onec-observation: temporary bounded technological log"
STATE_FILE = "technological-log-cursor.json"
RESTORE_FILE = "technological-log-restore.json"
SNAPSHOT_FILE = "logcfg.xml.snapshot"
BOUNDED_EVENTS = ("EXCP", "TDEADLOCK", "TTIMEOUT", "TLOCK")
# Never enabled by this module: they are high-volume or carry query text and parameters.
FORBIDDEN_EVENTS = ("CALL", "SCALL", "SDBL", "DBMSSQL", "DBPOSTGRS", "DBORACLE", "DB2", "DBV8DBENG", "SYSTEM")
MAX_FINGERPRINTS = 4096
LOG_FILE_PATTERN = re.compile(r"\.log(?:\.[0-9]+)?$")


def bounded_logcfg(log_root: Path, *, history_hours: int = 1, rotation_mb: int = 10) -> bytes:
    location = quoteattr(str(log_root))
    text = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- {CONFIG_MARKER} -->
<config xmlns="http://v8.1c.ru/v8/tech-log">
  <log location={location} history="{history_hours}" rotation="size" rotationsize="{rotation_mb}" format="text">
    <event><eq property="name" value="excp"/></event>
    <event><eq property="name" value="tdeadlock"/></event>
    <event><eq property="name" value="ttimeout"/></event>
    <event><eq property="name" value="tlock"/><gt property="duration" value="100000"/></event>
    <property name="all"/>
  </log>
</config>
"""
    return text.encode("utf-8")


@dataclass(slots=True)
class TechlogPlan:
    config_path: Path
    log_root: Path
    processes: list[str] = field(default_factory=list)
    process_name: str = ""
    process_id_file: Path | None = None
    privileged: list[str] = field(default_factory=list)


def plan_from_env(
    run_root: Path,
    *,
    infobase_mode: str = "",
    infobase_ref: str = "",
    process_id_file: Path | None = None,
) -> TechlogPlan | None:
    """Return a plan only when the operator configured ``TECHLOG_CONFIG_PATH``."""
    config_value = os.environ.get("TECHLOG_CONFIG_PATH", "").strip()
    if not config_value:
        return None
    root_value = os.environ.get("TECHLOG_ROOT", "").strip()
    if infobase_mode == "client-server" and os.environ.get("TECHLOG_SERVER_ROOT", "").strip():
        root_value = os.environ["TECHLOG_SERVER_ROOT"].strip()
    log_root = Path(root_value) if root_value else run_root / "techlog"
    if infobase_mode == "client-server" and infobase_ref:
        processes, process_name, pid_file = ["rphost"], infobase_ref, None
    else:
        processes, process_name, pid_file = ["1cv8", "1cv8c"], "", process_id_file
    privileged_value = os.environ.get("TECHLOG_PRIVILEGED_COMMAND", "none").strip()
    privileged = [] if privileged_value in {"", "none"} else privileged_value.split()
    return TechlogPlan(
        config_path=Path(config_value).resolve(),
        log_root=log_root.resolve(),
        processes=processes,
        process_name=process_name,
        process_id_file=pid_file,
        privileged=privileged,
    )


def _lock_paths(config_path: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(str(config_path).encode("utf-8")).hexdigest()[:16]
    base = Path(tempfile.gettempdir()) / f"onec-techlog-{digest}"
    return base.with_suffix(".lock"), base.with_suffix(".owner.json")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


class ConfigStore:
    """Reads and writes ``logcfg.xml`` directly or through an operator-configured privileged helper."""

    def __init__(self, path: Path, privileged: list[str]) -> None:
        self.path = path
        self.privileged = privileged

    def _run(self, command: list[str], data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([*self.privileged, *command], input=data, capture_output=True, check=False, timeout=30)

    def read(self) -> bytes | None:
        if not self.privileged:
            try:
                return self.path.read_bytes()
            except FileNotFoundError:
                return None
        if self._run(["test", "-f", str(self.path)]).returncode != 0:
            return None
        result = self._run(["cat", str(self.path)])
        if result.returncode != 0:
            raise OSError(f"cannot read {self.path}")
        return result.stdout

    def write(self, data: bytes, scratch: Path) -> None:
        if not self.privileged:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("wb") as stream:
                stream.write(data)
            return
        scratch.write_bytes(data)
        try:
            for command in (
                ["install", "-d", "-m", "0755", str(self.path.parent)],
                ["install", "-m", "0644", str(scratch), str(self.path)],
            ):
                if self._run(command).returncode != 0:
                    raise OSError(f"cannot write {self.path}")
        finally:
            scratch.unlink(missing_ok=True)

    def remove(self) -> None:
        if not self.privileged:
            self.path.unlink(missing_ok=True)
            return
        if self._run(["rm", "-f", str(self.path)]).returncode != 0:
            raise OSError(f"cannot remove {self.path}")


def restore_from_record(record_path: Path) -> dict[str, Any]:
    """Restore ``logcfg.xml`` from a run's restore record; idempotent."""
    record = _read_json(record_path)
    if record is None:
        raise CommandError(f"technological log restore record not found: {record_path}")
    if record.get("restored"):
        return {"status": "restored", "configPath": record.get("configPath")}
    store = ConfigStore(Path(str(record["configPath"])), [str(item) for item in record.get("privileged", [])])
    snapshot = record_path.parent / SNAPSHOT_FILE
    if record.get("existed"):
        original = snapshot.read_bytes()
        if hashlib.sha256(original).hexdigest() != record.get("sha256"):
            raise CommandError(f"technological log snapshot is corrupted: {snapshot}")
        store.write(original, record_path.parent / ".logcfg.restore.tmp")
        if store.read() != original:
            raise CommandError(f"logcfg.xml differs after restore: {store.path}")
    else:
        store.remove()
        if store.read() is not None:
            raise CommandError(f"logcfg.xml still exists after restore: {store.path}")
    record["restored"] = True
    _write_json(record_path, record)
    _, owner_path = _lock_paths(store.path)
    owner = _read_json(owner_path)
    if owner is not None and owner.get("restoreRecord") == str(record_path):
        owner_path.unlink(missing_ok=True)
    return {"status": "restored", "configPath": str(store.path)}


def _configured_location(data: bytes | None) -> Path | None:
    if not data:
        return None
    # logcfg.xml is an operator-owned local file; expat does not resolve external entities.
    try:
        tree = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return None
    locations = {node.get("location", "") for node in tree if node.tag.rsplit("}", 1)[-1] == "log"}
    if len(locations) != 1:
        return None
    location = locations.pop()
    return Path(location) if location and Path(location).is_absolute() else None


class TechlogSession:
    """Temporary bounded config plus operation cursor of one run-root."""

    def __init__(self, plan: TechlogPlan, run_root: Path) -> None:
        self.plan = plan
        self.run_root = run_root
        self.state_path = run_root / STATE_FILE
        self.restore_path = run_root / RESTORE_FILE
        self.store = ConfigStore(plan.config_path, plan.privileged)
        self.owner = False
        self.status: dict[str, Any] = {"status": "not-started"}

    def _lock(self) -> ResourceLock:
        lock_path, _ = _lock_paths(self.plan.config_path)
        return ResourceLock(lock_path, {"pid": os.getpid(), "operation": "technological-log"}, timeout=60)

    def start(self) -> dict[str, Any]:
        log_root = self.plan.log_root
        try:
            with self._lock():
                _, owner_path = _lock_paths(self.plan.config_path)
                owner = _read_json(owner_path)
                if owner is not None and not process_is_alive(int(owner.get("pid", 0) or 0)):
                    # A previous observer died before restoring: put its original back first.
                    restore_from_record(Path(str(owner.get("restoreRecord", ""))))
                    owner_path.unlink(missing_ok=True)
                    owner = None
                current = self.store.read()
                if owner is not None:
                    joined_root = _configured_location(current)
                    if joined_root is None:
                        return self._unavailable("config-unreadable")
                    log_root = joined_root
                    self.status = {"status": "joined", "configPath": str(self.plan.config_path)}
                else:
                    self.run_root.mkdir(parents=True, exist_ok=True)
                    if current is not None:
                        (self.run_root / SNAPSHOT_FILE).write_bytes(current)
                    _write_json(
                        self.restore_path,
                        {
                            "schemaVersion": 1,
                            "configPath": str(self.plan.config_path),
                            "existed": current is not None,
                            "sha256": hashlib.sha256(current).hexdigest() if current is not None else None,
                            "privileged": self.plan.privileged,
                            "restored": False,
                        },
                    )
                    _write_json(owner_path, {"pid": os.getpid(), "restoreRecord": str(self.restore_path)})
                    self.owner = True
                    log_root.mkdir(parents=True, exist_ok=True)
                    try:
                        self.store.write(bounded_logcfg(log_root), self.run_root / ".logcfg.install.tmp")
                    except OSError:
                        self._restore()
                        return self._unavailable("config-access")
                    self.status = {"status": "enabled", "configPath": str(self.plan.config_path)}
        except (OSError, CommandError, ValueError):
            try:
                self._restore()
            except (OSError, CommandError):
                self.status["restoreRecord"] = str(self.restore_path)
            return self._unavailable("config-access")
        try:
            files, _ = _scan(self._cursor_payload(log_root), baseline=True)
        except OSError:
            files = {}
        state = self._cursor_payload(log_root)
        state.update(baseline=files, files=files)
        _write_json(self.state_path, state)
        self.status.update(logRoot=str(log_root), cursor=str(self.state_path))
        return dict(self.status)

    def _cursor_payload(self, log_root: Path) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "available": True,
            "logRoot": str(log_root),
            "processes": self.plan.processes,
            "processName": self.plan.process_name,
            "processIdFile": str(self.plan.process_id_file) if self.plan.process_id_file else None,
            "baseline": {},
            "files": {},
            "end": None,
            "fingerprints": [],
        }

    def _unavailable(self, reason: str) -> dict[str, Any]:
        self.status = {**self.status, "status": "not-available", "reason": reason}
        _write_json(self.state_path, {"schemaVersion": 1, "available": False, "notAvailableReason": reason})
        return dict(self.status)

    def read_events(self) -> list[dict[str, Any]]:
        if self.status.get("status") not in {"enabled", "joined"}:
            return []
        try:
            return cursor_read(self.state_path)
        except (OSError, CommandError):
            self.status.update(status="degraded", reason="cursor-read")
            return []

    def _restore(self) -> None:
        if not self.owner:
            return
        restore_from_record(self.restore_path)
        self.owner = False

    def finish(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        events = self.read_events()
        if self.state_path.is_file():
            try:
                cursor_close(self.state_path)
            except (OSError, CommandError):
                self.status.setdefault("reason", "cursor-close")
        if self.owner:
            try:
                with self._lock():
                    self._restore()
                self.status["restored"] = True
            except (OSError, CommandError) as error:
                self.status.update(restored=False, restoreError=str(error)[:300], restoreRecord=str(self.restore_path))
        return events, dict(self.status)


def _split_complete_records(data: bytes) -> tuple[list[bytes], bytes]:
    records: list[bytes] = []
    start = 0
    quote: int | None = None
    index = 0
    while index < len(data):
        value = data[index]
        if quote is None:
            if value in (ord("'"), ord('"')):
                quote = value
        elif value == quote:
            if index + 1 < len(data) and data[index + 1] == quote:
                index += 1
            else:
                quote = None
        if value == ord("\n") and quote is None:
            record = data[start:index].rstrip(b"\r")
            if record:
                records.append(record)
            start = index + 1
        index += 1
    return records, data[start:]


def _process_directory(payload: dict[str, Any]) -> tuple[list[str], str | None]:
    prefixes = [f"{name}_" for name in payload.get("processes", [])]
    pid_file = payload.get("processIdFile")
    if not pid_file:
        return prefixes, None
    try:
        pid = Path(pid_file).read_text(encoding="ascii").strip()
    except OSError:
        return prefixes, None
    if not pid.isdigit():
        return prefixes, None
    return prefixes, pid


def _scan(
    payload: dict[str, Any],
    *,
    baseline: bool,
    starts: dict[str, Any] | None = None,
    ends: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[bytes]]:
    root = Path(payload["logRoot"])
    if not root.is_dir():
        return {}, []
    prefixes, pid = _process_directory(payload)
    previous = payload.get("files", {}) if starts is None else starts
    current: dict[str, Any] = {}
    records: list[bytes] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink() or not candidate.is_file() or not LOG_FILE_PATTERN.search(candidate.name):
            continue
        directory = candidate.parent.name
        if prefixes and not any(directory.startswith(prefix) for prefix in prefixes):
            continue
        if pid and not directory.endswith(f"_{pid}"):
            continue
        key = str(candidate)
        old = previous.get(key, {})
        with candidate.open("rb") as stream:
            info = os.fstat(stream.fileno())
            same = old.get("inode") == info.st_ino and info.st_size >= int(old.get("offset", 0))
            start = int(old.get("offset", 0)) if same else 0
            tail = base64.b64decode(old.get("tail", "")) if same else b""
            if baseline:
                end, tail, data = info.st_size, b"", b""
            else:
                limit = None
                if ends is not None and key in ends and ends[key].get("inode") == info.st_ino:
                    limit = int(ends[key]["offset"]) - start
                elif ends is not None:
                    limit = 0 if key not in ends else None
                stream.seek(start)
                data = stream.read() if limit is None else stream.read(max(limit, 0))
                end = start + len(data)
        if not baseline:
            complete, tail = _split_complete_records(tail + data)
            records.extend(complete)
        current[key] = {"inode": info.st_ino, "offset": end, "tail": base64.b64encode(tail).decode("ascii")}
    return current, records


def _safe_event(record: bytes, payload: dict[str, Any]) -> dict[str, Any] | None:
    text = record.decode("utf-8", errors="replace").lstrip("﻿")
    header = text.splitlines()[0] if text else ""
    try:
        fields = next(csv.reader([header], strict=True))
    except (csv.Error, StopIteration):
        return None
    if len(fields) < 4 or "-" not in fields[0]:
        return None
    properties: dict[str, str] = {}
    for item in fields[3:]:
        if "=" in item:
            key, value = item.split("=", 1)
            properties[key] = value
    processes = payload.get("processes") or []
    if processes and properties.get("process") not in processes:
        return None
    if payload.get("processName") and properties.get("p:processName") != payload["processName"]:
        return None
    event: dict[str, Any] = {
        "techlog": "event",
        "event": fields[1],
        "level": properties.get("level", ""),
        "duration": fields[0].rsplit("-", 1)[1],
        "process": properties.get("process", ""),
        "processName": properties.get("p:processName", ""),
    }
    if event["level"].lower() == "error" or fields[1].upper() == "EXCP":
        marker = ",Descr="
        description = text.split(marker, 1)[1].strip() if marker in text else ""
        if len(description) >= 2 and description[0] in "'\"" and description[-1] == description[0]:
            description = description[1:-1].replace(description[0] * 2, description[0])
        event["description"] = description[:1000]
    return event


def cursor_read(state_path: Path, *, whole_run: bool = False) -> list[dict[str, Any]]:
    """Return new events since the last read, or every event of the run with ``whole_run``."""
    payload = _read_json(state_path)
    if payload is None:
        raise CommandError(f"cannot read technological log cursor: {state_path}")
    if not payload.get("available"):
        return [{"techlog": "not-available", "reason": payload.get("notAvailableReason", "unknown")}]
    if whole_run:
        _, records = _scan(payload, baseline=False, starts=payload.get("baseline", {}), ends=payload.get("end"))
        events = [event for event in (_safe_event(record, payload) for record in records) if event is not None]
        return events
    files, records = _scan(payload, baseline=False)
    fingerprints = list(payload.get("fingerprints", []))
    known = set(fingerprints)
    events: list[dict[str, Any]] = []
    for record in records:
        event = _safe_event(record, payload)
        if event is None:
            continue
        fingerprint = hashlib.sha256(record).hexdigest()
        if fingerprint in known:
            continue
        known.add(fingerprint)
        fingerprints.append(fingerprint)
        events.append(event)
    payload["files"] = files
    payload["fingerprints"] = fingerprints[-MAX_FINGERPRINTS:]
    _write_json(state_path, payload)
    return events


def cursor_close(state_path: Path) -> None:
    """Freeze the end of the run interval so later whole-run reads stay inside it."""
    payload = _read_json(state_path)
    if payload is None or not payload.get("available") or payload.get("end") is not None:
        return
    files, _ = _scan(payload, baseline=True)
    payload["end"] = files
    _write_json(state_path, payload)


USAGE = """Usage:
  technological-log status
  technological-log cursor read --state <run-root>/technological-log-cursor.json [--all]
  technological-log restore --run-root <run-root>

The observation adapter enables the bounded log only while one launch runs (TECHLOG_CONFIG_PATH).
cursor read --all prints every event between the start and the end of that run.
restore puts back the original logcfg.xml of a run whose observer was killed.
"""


def technological_log_cli(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(USAGE, end="")
        return 0
    action, rest = argv[0], argv[1:]
    if action == "status":
        config_value = os.environ.get("TECHLOG_CONFIG_PATH", "").strip()
        if not config_value:
            print(json.dumps({"status": "not-configured", "reason": "TECHLOG_CONFIG_PATH is not set"}))
            return 0
        privileged_value = os.environ.get("TECHLOG_PRIVILEGED_COMMAND", "none").strip()
        store = ConfigStore(Path(config_value), [] if privileged_value in {"", "none"} else privileged_value.split())
        try:
            current = store.read()
        except OSError:
            print(json.dumps({"status": "config-unreadable", "configPath": config_value}))
            return 1
        _, owner_path = _lock_paths(Path(config_value).resolve())
        print(
            json.dumps(
                {
                    "status": "configured" if current is not None else "absent",
                    "configPath": config_value,
                    "temporary": bool(current and CONFIG_MARKER.encode("utf-8") in current),
                    "activeRun": owner_path.is_file(),
                }
            )
        )
        return 0
    if action == "cursor" and rest[:1] == ["read"]:
        state = ""
        whole_run = False
        index = 1
        while index < len(rest):
            if rest[index] == "--state" and index + 1 < len(rest):
                state = rest[index + 1]
                index += 2
            elif rest[index] == "--all":
                whole_run = True
                index += 1
            else:
                raise CommandError(f"unknown argument: {rest[index]}", 2)
        if not state:
            raise CommandError("--state is required", 2)
        for event in cursor_read(Path(state).resolve(), whole_run=whole_run):
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        return 0
    if action == "restore":
        if len(rest) != 2 or rest[0] != "--run-root":
            raise CommandError("Usage: technological-log restore --run-root <dir>", 2)
        print(json.dumps(restore_from_record(Path(rest[1]).resolve() / RESTORE_FILE)))
        return 0
    print(USAGE, end="", file=sys.stderr)
    return 2
