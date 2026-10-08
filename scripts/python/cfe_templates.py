from __future__ import annotations

import argparse
import re
import shutil
import uuid
from pathlib import Path

from .common import die, repo_path

TEMPLATE_ALIASES = {
    "patch": "TemplatePatchExtension",
    "fix": "TemplatePatchExtension",
    "TemplatePatchExtension": "TemplatePatchExtension",
    "customization": "TemplateCustomizationExtension",
    "custom": "TemplateCustomizationExtension",
    "TemplateCustomizationExtension": "TemplateCustomizationExtension",
}

DEFAULT_SYNONYMS = {
    "TemplatePatchExtension": "Шаблон расширения-исправления",
    "TemplateCustomizationExtension": "Шаблон расширения-доработки",
}

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
CFE_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="init-cfe-from-template",
        description="Create src/cfe/<name> from a source-only CFE template.",
    )
    parser.add_argument("--template", default="customization", help="customization, patch, or template directory name")
    parser.add_argument("--name", required=True, help="New configuration extension metadata name")
    parser.add_argument("--synonym", default="", help="Extension synonym")
    parser.add_argument("--version", default="", help="Extension version value")
    parser.add_argument("--language-uuid", default="", help="Extended configuration UUID for Language.Русский")
    parser.add_argument("--output-root", default="", help=argparse.SUPPRESS)
    return parser


def _resolve_template(value: str) -> str:
    template_name = TEMPLATE_ALIASES.get(value)
    if template_name is None:
        allowed = ", ".join(sorted(TEMPLATE_ALIASES))
        die(f"unknown CFE template '{value}'. Allowed values: {allowed}")
    return template_name


def _validate_name(name: str) -> None:
    if not CFE_NAME_RE.match(name):
        die(f"invalid CFE name '{name}'. Use letters, digits, and underscore; first character must not be a digit")


def _validate_uuid(value: str, label: str) -> None:
    if value and not UUID_RE.fullmatch(value):
        die(f"invalid {label}: {value}")


def _replace_uuids(text: str, replacements: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if text[max(0, match.start() - len("<xr:ClassId>")) : match.start()] == "<xr:ClassId>":
            return value
        if value == "00000000-0000-0000-0000-000000000000":
            return value
        if value not in replacements:
            replacements[value] = str(uuid.uuid4())
        return replacements[value]

    return UUID_RE.sub(replace, text)


def _rewrite_file(
    path: Path,
    template_name: str,
    new_name: str,
    synonym: str,
    version: str,
    language_uuid: str,
    uuids: dict[str, str],
) -> None:
    raw = path.read_text(encoding="utf-8-sig")
    text = raw.replace(template_name, new_name)
    if synonym:
        text = text.replace(DEFAULT_SYNONYMS[template_name], synonym)
    if version:
        text = re.sub(r"<Version>[^<]*</Version>", f"<Version>{version}</Version>", text)
        text = text.replace('Возврат "1.0.0.0";', f'Возврат "{version}";')
    text = _replace_uuids(text, uuids)
    if language_uuid:
        text = re.sub(
            r"<ExtendedConfigurationObject>[^<]*</ExtendedConfigurationObject>",
            f"<ExtendedConfigurationObject>{language_uuid}</ExtendedConfigurationObject>",
            text,
        )
    path.write_text(text, encoding="utf-8", newline="\n")


def _rewrite_tree(
    target: Path, template_name: str, new_name: str, synonym: str, version: str, language_uuid: str
) -> None:
    uuids: dict[str, str] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            _rewrite_file(path, template_name, new_name, synonym, version, language_uuid, uuids)


def _move_template_paths(target: Path, template_name: str, new_name: str) -> None:
    old_role = target / "Roles" / f"{template_name}_ОсновнаяРоль.xml"
    if not old_role.exists():
        die(f"template role XML was not found after copy: {old_role}")
    old_role.rename(target / "Roles" / f"{new_name}_ОсновнаяРоль.xml")

    old_update_module = target / "CommonModules" / f"ОбновлениеИнформационнойБазы{template_name}.xml"
    if not old_update_module.exists():
        die(f"template update module XML was not found after copy: {old_update_module}")
    old_update_module.rename(target / "CommonModules" / f"ОбновлениеИнформационнойБазы{new_name}.xml")

    old_update_module_dir = target / "CommonModules" / f"ОбновлениеИнформационнойБазы{template_name}"
    if not old_update_module_dir.is_dir():
        die(f"template update module directory was not found after copy: {old_update_module_dir}")
    old_update_module_dir.rename(target / "CommonModules" / f"ОбновлениеИнформационнойБазы{new_name}")


def init_cfe_from_template(argv: list[str]) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    new_name = args.name.strip()
    _validate_name(new_name)
    language_uuid = args.language_uuid.strip()
    _validate_uuid(language_uuid, "language UUID")
    template_name = _resolve_template(args.template)

    templates_root = repo_path("src", "cfe", "_templates")
    source = templates_root / template_name
    if not source.is_dir():
        die(f"template directory does not exist: {source}")

    output_root = (
        Path(args.output_root).expanduser().resolve(strict=False) if args.output_root else repo_path("src", "cfe")
    )
    target = output_root / new_name
    if target.exists():
        die(f"target CFE already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target)
        _move_template_paths(target, template_name, new_name)
        _rewrite_tree(target, template_name, new_name, args.synonym.strip(), args.version.strip(), language_uuid)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        raise

    rel_target = target
    try:
        rel_target = target.relative_to(repo_path())
    except ValueError:
        pass

    print(f"Created CFE source: {rel_target}")
    print(f"Template: {template_name}")
    print("Validate next:")
    print(f"  ./scripts/skills/run-imported-skill.sh cfe-validate -ExtensionPath src/cfe/{new_name} -Detailed")
    return 0
