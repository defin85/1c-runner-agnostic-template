from __future__ import annotations

import argparse
import re
import shutil
import uuid
from pathlib import Path

from .common import CommandError, die, repo_path


TEMPLATE_ALIASES = {
    "sync": "TemplateSyncProcessor",
    "sync-async": "TemplateSyncAsyncProcessor",
    "async": "TemplateSyncAsyncProcessor",
    "TemplateSyncProcessor": "TemplateSyncProcessor",
    "TemplateSyncAsyncProcessor": "TemplateSyncAsyncProcessor",
}

DEFAULT_INFO = {
    "TemplateSyncProcessor": "Шаблон синхронной внешней обработки",
    "TemplateSyncAsyncProcessor": "Шаблон синхронной и фоновой внешней обработки",
}

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EPF_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="init-epf-from-template",
        description="Create src/epf/<name> from a source-only EPF template.",
    )
    parser.add_argument("--template", default="sync-async", help="sync, sync-async, async, or template directory name")
    parser.add_argument("--name", required=True, help="New external data processor metadata name")
    parser.add_argument("--info", default="", help="Registration info/title for BSP and form caption")
    parser.add_argument("--version", default="", help="Registration version value")
    parser.add_argument("--output-root", default="", help=argparse.SUPPRESS)
    return parser


def _resolve_template(value: str) -> str:
    template_name = TEMPLATE_ALIASES.get(value)
    if template_name is None:
        allowed = ", ".join(sorted(TEMPLATE_ALIASES))
        die(f"unknown EPF template '{value}'. Allowed values: {allowed}")
    return template_name


def _validate_name(name: str) -> None:
    if not EPF_NAME_RE.match(name):
        die(f"invalid EPF name '{name}'. Use letters, digits, and underscore; first character must not be a digit")


def _replace_uuids(text: str, replacements: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if value not in replacements:
            replacements[value] = str(uuid.uuid4())
        return replacements[value]

    return UUID_RE.sub(replace, text)


def _rewrite_file(path: Path, template_name: str, new_name: str, info: str, version: str, uuids: dict[str, str]) -> None:
    raw = path.read_text(encoding="utf-8-sig")
    text = raw.replace(template_name, new_name)
    if info:
        text = text.replace(DEFAULT_INFO[template_name], info)
    if version:
        text = re.sub(
            r'РегистрационныеДанные\.Вставить\("Версия",\s*"[^"]*"\);',
            f'РегистрационныеДанные.Вставить("Версия", "{version}");',
            text,
        )
    text = _replace_uuids(text, uuids)
    path.write_text(text, encoding="utf-8", newline="\n")


def _rewrite_tree(target: Path, template_name: str, new_name: str, info: str, version: str) -> None:
    uuids: dict[str, str] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            _rewrite_file(path, template_name, new_name, info, version, uuids)


def _move_template_paths(target: Path, template_name: str, new_name: str) -> None:
    root_xml = target / f"{template_name}.xml"
    if not root_xml.exists():
        die(f"template root XML was not found after copy: {root_xml}")
    root_xml.rename(target / f"{new_name}.xml")

    inner_dir = target / template_name
    if not inner_dir.is_dir():
        die(f"template inner directory was not found after copy: {inner_dir}")
    inner_dir.rename(target / new_name)


def init_epf_from_template(argv: list[str]) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    new_name = args.name.strip()
    _validate_name(new_name)
    template_name = _resolve_template(args.template)

    templates_root = repo_path("src", "epf", "_templates")
    source = templates_root / template_name
    if not source.is_dir():
        die(f"template directory does not exist: {source}")

    output_root = Path(args.output_root).expanduser().resolve(strict=False) if args.output_root else repo_path("src", "epf")
    target = output_root / new_name
    if target.exists():
        die(f"target EPF already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target)
        _move_template_paths(target, template_name, new_name)
        _rewrite_tree(target, template_name, new_name, args.info.strip(), args.version.strip())
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        raise

    rel_target = target
    try:
        rel_target = target.relative_to(repo_path())
    except ValueError:
        pass

    print(f"Created EPF source: {rel_target}")
    print(f"Template: {template_name}")
    print("Validate next:")
    print(f"  ./scripts/skills/run-imported-skill.sh epf-validate src/epf/{new_name}")
    print(f"  ./scripts/skills/run-imported-skill.sh form-validate src/epf/{new_name}/{new_name}/Forms/Форма")
    return 0

