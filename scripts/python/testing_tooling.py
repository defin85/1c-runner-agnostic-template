from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from .common import die, project_root


UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
CLASS_ID_RE = re.compile(r"<xr:ClassId>([0-9a-fA-F-]{36})</xr:ClassId>")
NAME_RE = re.compile(r"^[^\W\d]\w{0,79}$", re.UNICODE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dependencies(root: Path) -> dict:
    path = root / "automation" / "testing" / "dependencies.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        die(f"cannot read testing dependencies: {error}")


def _project_target(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        die("testing dependency installPath must be project-relative")
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        die("testing dependency installPath must be project-relative")
    target = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            die("symbolic links are not allowed in testing dependency installPath")
    return target


def _rewrite_project_template(root: Path, name: str) -> None:
    if not NAME_RE.fullmatch(name):
        die("--project-tests-name must be a valid 1C metadata name")
    replacements: dict[str, str] = {}
    protected = {
        value.lower()
        for path in root.rglob("*.xml")
        for value in CLASS_ID_RE.findall(path.read_text(encoding="utf-8-sig"))
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for old in UUID_RE.findall(text):
            if old.lower() not in protected:
                replacements.setdefault(old.lower(), str(uuid.uuid4()))
        text = text.replace("ProjectYAxUnitTests", name).replace("PYT_", name[:3].upper() + "_")
        text = UUID_RE.sub(lambda match: replacements.get(match.group(0).lower(), match.group(0)), text)
        path.write_text(text, encoding="utf-8", newline="\n")
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if "ProjectYAxUnitTests" in path.name:
            path.rename(path.with_name(path.name.replace("ProjectYAxUnitTests", name)))


def init_test_tooling(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="init-test-tooling")
    parser.add_argument("--project-tests-name", required=True)
    args = parser.parse_args(argv)
    root = project_root()
    sources = {
        "VATestContour": root / "automation" / "testing" / "templates" / "VATestContour",
        args.project_tests_name: root / "automation" / "testing" / "templates" / "ProjectYAxUnitTests",
        "YAxUnit": root / "automation" / "testing" / "vendor" / "YAxUnit",
        "VAExtension": root / "automation" / "testing" / "vendor" / "VAExtension",
    }
    target_root = root / "src" / "cfe"
    if not NAME_RE.fullmatch(args.project_tests_name):
        die("--project-tests-name must be a valid 1C metadata name")
    if args.project_tests_name.casefold() in {name.casefold() for name in ("VATestContour", "YAxUnit", "VAExtension")}:
        die("--project-tests-name conflicts with a fixed test-tooling extension name")
    if (root / "src").is_symlink() or target_root.is_symlink():
        die("symbolic links are not allowed in src/cfe")
    for name, source in sources.items():
        if not source.is_dir():
            die(f"test-tooling source is missing: {source}")
        target = target_root / name
        if target.exists() or target.is_symlink():
            die(f"target already exists: {target}")
    target_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".test-tooling.", dir=target_root))
    published: list[Path] = []
    try:
        for name, source in sources.items():
            shutil.copytree(source, staging / name)
        _rewrite_project_template(staging / args.project_tests_name, args.project_tests_name)
        for name in sources:
            target = target_root / name
            os.replace(staging / name, target)
            published.append(target)
    except BaseException:
        for target in published:
            shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


def _safe_epf(archive: Path, expected_name: str, output: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        matches: list[zipfile.ZipInfo] = []
        for info in bundle.infolist():
            path = PurePosixPath(info.filename.replace("\\", "/"))
            mode = info.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
                die("unsafe ZIP entry")
            if info.is_dir():
                continue
            if path.name != expected_name or len(path.parts) != 1:
                die("unexpected ZIP entry")
            matches.append(info)
        if len(matches) != 1:
            die("ZIP must contain exactly one expected EPF")
        with bundle.open(matches[0]) as source, output.open("wb") as target:
            shutil.copyfileobj(source, target)


def install_test_tooling(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="install-test-tooling")
    parser.add_argument("--archive")
    args = parser.parse_args(argv)
    root = project_root()
    dep = _dependencies(root)["vanessaAutomationSingle"]
    target = _project_target(root, dep["installPath"])
    if target.is_file() and _sha256(target) == dep["epfSha256"]:
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="test-tooling-") as temp_name:
        temp = Path(temp_name)
        archive = temp / dep["asset"]
        if args.archive:
            shutil.copyfile(Path(args.archive).resolve(strict=True), archive)
        else:
            try:
                urllib.request.urlretrieve(dep["url"], archive)
            except OSError as error:
                die(f"cannot download Vanessa Automation: {error}")
        if _sha256(archive) != dep["zipSha256"]:
            die("Vanessa Automation ZIP SHA-256 mismatch")
        epf = temp / dep["epfName"]
        _safe_epf(archive, dep["epfName"], epf)
        if _sha256(epf) != dep["epfSha256"]:
            die("Vanessa Automation EPF SHA-256 mismatch")
        fd, staged_name = tempfile.mkstemp(prefix=".vanessa-", dir=target.parent)
        os.close(fd)
        staged = Path(staged_name)
        try:
            shutil.copyfile(epf, staged)
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
    return 0
