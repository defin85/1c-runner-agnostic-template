from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .common import die, project_root


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
STATUSES = ("pending", "running", "done", "failed_retry", "blocked", "skipped_by_policy")
TRANSITIONS = {
    "pending": {"running", "blocked", "skipped_by_policy"},
    "running": {"done", "failed_retry", "blocked"},
    "failed_retry": {"running", "blocked", "skipped_by_policy"},
    "done": set(),
    "blocked": set(),
    "skipped_by_policy": set(),
}
PRIORITY = ("failed_retry", "running", "pending")
CAMPAIGN_KEYS = {"schemaVersion", "id", "createdAt", "entrypoints"}
ENTRYPOINT_KEYS = {"prepareGolden", "startWarmService", "runJob"}
JOB_KEYS = {"id", "kind", "status", "selector", "resultDir"}
FILTER_KEYS = {"extensions", "modules", "tests", "tags", "paths"}


def _object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        die(f"{name} must be a JSON object")
    return value


def _exact_keys(value: dict, allowed: set[str], required: set[str], name: str) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        die(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        die(f"{name} is missing fields: {', '.join(sorted(missing))}")


def _valid_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        die(f"invalid {name}")
    return value


def _relative_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        die(f"{name} must be a non-empty project-relative path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or normalized != path.as_posix():
        die(f"{name} must be a normalized project-relative path")
    current = project_root()
    for part in path.parts:
        current /= part
        if current.is_symlink():
            die(f"symbolic links are not allowed in {name}")
    return value


def _validate_campaign(raw: object, expected_id: str | None = None) -> dict:
    data = _object(raw, "campaign")
    _exact_keys(data, CAMPAIGN_KEYS, CAMPAIGN_KEYS, "campaign")
    if data["schemaVersion"] != 1:
        die("unsupported campaign schemaVersion")
    campaign_id = _valid_id(data["id"], "campaign id")
    if expected_id is not None and campaign_id != expected_id:
        die("campaign id does not match directory name")
    if not isinstance(data["createdAt"], str) or not UTC_RE.fullmatch(data["createdAt"]):
        die("createdAt must be UTC RFC 3339")
    try:
        parsed = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
    except ValueError:
        die("createdAt must be UTC RFC 3339")
    if parsed.tzinfo != timezone.utc or not data["createdAt"].endswith("Z"):
        die("createdAt must be UTC RFC 3339")
    entrypoints = _object(data["entrypoints"], "entrypoints")
    _exact_keys(entrypoints, ENTRYPOINT_KEYS, ENTRYPOINT_KEYS, "entrypoints")
    if any(not isinstance(value, str) or not value.strip() for value in entrypoints.values()):
        die("entrypoint values must be non-empty strings")
    return data


def _validate_job(raw: object) -> dict:
    job = _object(raw, "job")
    _exact_keys(job, JOB_KEYS, JOB_KEYS - {"resultDir"}, "job")
    _valid_id(job["id"], "job id")
    if job["status"] not in STATUSES:
        die("invalid job status")
    if job["kind"] == "vanessa-bdd":
        selector = _object(job["selector"], "selector")
        _exact_keys(selector, {"featurePath"}, {"featurePath"}, "vanessa-bdd selector")
        _relative_path(selector["featurePath"], "featurePath")
    elif job["kind"] == "yaxunit":
        selector = _object(job["selector"], "selector")
        _exact_keys(selector, {"filters"}, {"filters"}, "yaxunit selector")
        filters = _object(selector["filters"], "filters")
        _exact_keys(filters, FILTER_KEYS, set(), "filters")
        if not filters:
            die("filters must contain at least one filter")
        for key, values in filters.items():
            if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item for item in values):
                die(f"filters.{key} must be a non-empty string array")
            if key == "paths":
                for value in values:
                    _relative_path(value, "filters.paths item")
    else:
        die("invalid job kind")
    result_dir = job.get("resultDir")
    if job["status"] == "done":
        _relative_path(result_dir, "resultDir")
    elif result_dir is not None:
        die("resultDir is allowed only for done jobs")
    return job


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        die(f"cannot read valid JSON from {path}: {error}")


def _load_queue(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        die(f"cannot read queue: {error}")
    try:
        jobs = [_validate_job(json.loads(line)) for line in lines if line.strip()]
    except json.JSONDecodeError as error:
        die(f"queue contains invalid JSON: {error}")
    ids = [job["id"] for job in jobs]
    if not jobs:
        die("queue must contain at least one job")
    if len(ids) != len(set(ids)):
        die("job ids must be unique")
    return jobs


def _safe_existing(path: Path, root: Path, kind: str) -> Path:
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            die(f"symbolic links are not allowed in {kind}")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        die(f"{kind} is outside the project or missing")
    return resolved


def _state_root(root: Path) -> Path:
    base = root / "analysis" / "testing"
    if (root / "analysis").is_symlink() or base.is_symlink():
        die("symbolic links are not allowed in testing state")
    if base.exists():
        _safe_existing(base, root, "testing state")
    return base


def _atomic_text(path: Path, text: str) -> None:
    if path.is_symlink():
        die(f"symbolic links are not allowed in state file: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _active(root: Path) -> tuple[str, Path, list[dict]]:
    base = _state_root(root)
    pointer = _safe_existing(base / "active-campaign.txt", root, "active campaign pointer")
    campaign_id = pointer.read_text(encoding="utf-8").strip()
    _valid_id(campaign_id, "active campaign id")
    campaign_dir = _safe_existing(base / "campaigns" / campaign_id, root, "campaign directory")
    _validate_campaign(_load_json(_safe_existing(campaign_dir / "campaign.json", root, "campaign file")), campaign_id)
    queue_path = _safe_existing(campaign_dir / "queue.jsonl", root, "queue file")
    return campaign_id, queue_path, _load_queue(queue_path)


def _write_queue(path: Path, jobs: list[dict]) -> None:
    _atomic_text(path, "".join(json.dumps(job, ensure_ascii=False, separators=(",", ":")) + "\n" for job in jobs))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testing-campaign")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--id", required=True)
    init.add_argument("--queue", required=True)
    init.add_argument("--entrypoints", required=True)
    use = sub.add_parser("use")
    use.add_argument("id")
    sub.add_parser("next")
    set_parser = sub.add_parser("set")
    set_parser.add_argument("id")
    set_parser.add_argument("status", choices=STATUSES)
    set_parser.add_argument("--result-dir")
    sub.add_parser("status")
    return parser


def run_testing_campaign(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    root = project_root()
    base = _state_root(root)
    if args.action == "init":
        campaign_id = _valid_id(args.id, "campaign id")
        queue_source = Path(args.queue).resolve(strict=True)
        entrypoints = _object(_load_json(Path(args.entrypoints).resolve(strict=True)), "entrypoints")
        _exact_keys(entrypoints, ENTRYPOINT_KEYS, ENTRYPOINT_KEYS, "entrypoints")
        campaign = _validate_campaign({
            "schemaVersion": 1,
            "id": campaign_id,
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "entrypoints": entrypoints,
        }, campaign_id)
        jobs = _load_queue(queue_source)
        campaigns = base / "campaigns"
        if campaigns.is_symlink():
            die("symbolic links are not allowed in campaigns")
        target = campaigns / campaign_id
        if target.exists() or target.is_symlink():
            die(f"campaign already exists: {campaign_id}")
        campaigns.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=f".{campaign_id}.", dir=campaigns))
        try:
            (temp / "campaign.json").write_text(json.dumps(campaign, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _write_queue(temp / "queue.jsonl", jobs)
            os.replace(temp, target)
            _atomic_text(base / "active-campaign.txt", campaign_id + "\n")
        except BaseException:
            shutil.rmtree(temp, ignore_errors=True)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            raise
        return 0
    if args.action == "use":
        campaign_id = _valid_id(args.id, "campaign id")
        campaign_dir = _safe_existing(base / "campaigns" / campaign_id, root, "campaign directory")
        _validate_campaign(_load_json(_safe_existing(campaign_dir / "campaign.json", root, "campaign file")), campaign_id)
        _load_queue(_safe_existing(campaign_dir / "queue.jsonl", root, "queue file"))
        _atomic_text(base / "active-campaign.txt", campaign_id + "\n")
        return 0
    campaign_id, queue_path, jobs = _active(root)
    if args.action == "next":
        job = next((job for status in PRIORITY for job in jobs if job["status"] == status), None)
        print(json.dumps({"campaignId": campaign_id, "job": job}, ensure_ascii=False, separators=(",", ":")))
        return 0
    if args.action == "status":
        counts = Counter(job["status"] for job in jobs)
        print(json.dumps({"campaignId": campaign_id, "schemaVersion": 1, "counts": {status: counts[status] for status in STATUSES}}, ensure_ascii=False, separators=(",", ":")))
        return 0
    job = next((job for job in jobs if job["id"] == args.id), None)
    if job is None:
        die(f"unknown job id: {args.id}")
    if args.status not in TRANSITIONS[job["status"]]:
        die(f"transition is not allowed: {job['status']} -> {args.status}")
    if args.status == "done":
        job["resultDir"] = _relative_path(args.result_dir, "resultDir")
    elif args.result_dir is not None:
        die("--result-dir is allowed only for done")
    job["status"] = args.status
    _write_queue(queue_path, jobs)
    return 0
