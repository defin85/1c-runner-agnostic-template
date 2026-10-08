from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import (
    PROJECT_ROOT,
    die,
    ensure_dir,
    read_json,
    read_text,
    repo_path,
    run_git,
    run_process,
    timestamp_utc,
    write_json,
    write_text,
)
from .runtime_profiles import RuntimeProfile, load_runtime_profile, resolve_runtime_profile_path

IMPORT_ROOT = repo_path("automation", "vendor", "cc-1c-skills")
IMPORT_SKILLS_ROOT = IMPORT_ROOT / "skills"
IMPORT_LICENSE = IMPORT_ROOT / "LICENSE"
IMPORT_MANIFEST = IMPORT_ROOT / "imported-skills.json"
UPSTREAM_METADATA = IMPORT_ROOT / "UPSTREAM.json"
OVERLAY_MANIFEST = repo_path("automation", "context", "template-managed-paths.txt")
SYNC_MARKER = "<!-- GENERATED: sync-imported-skills -->"
DISPATCHER_SHELL = "./scripts/skills/run-imported-skill.sh"
DISPATCHER_POWERSHELL = "./scripts/skills/run-imported-skill.ps1"
CANONICAL_READINESS_TARGET = "make imported-skills-readiness"
CANONICAL_READINESS_COMMAND = "./scripts/skills/run-imported-skill.sh --readiness"
WINDOWS_READINESS_COMMAND = "./scripts/skills/run-imported-skill.ps1 --readiness"
CANONICAL_READINESS_DOC = "docs/agent/generated-project-verification.md"
CANONICAL_ENV_DOC = "env/README.md"
FULL_SKILLS_CATALOG = ".agents/skills/README.md"
REPRESENTATIVE_PYTHON_SKILL = "cf-edit"
REPRESENTATIVE_NODE_SKILL = "web-test"
REPRESENTATIVE_REFERENCE_SKILL = "form-patterns"
REPRESENTATIVE_NATIVE_ALIAS_SKILL = "db-create"

REFERENCE_ONLY_SKILLS = {
    "db-list",
    "epf-bsp-add-command",
    "epf-bsp-init",
    "form-patterns",
}

PYTHON_ALIAS_SKILLS = {
    "erf-validate": "epf-validate",
}

# Replaced by the metadata CLI (`metadata-use`); upstream sync must not restore them.
RETIRED_METADATA_SKILLS = frozenset(
    {
        "meta-info",
        "meta-compile",
        "meta-edit",
        "meta-remove",
        "meta-validate",
        "form-info",
        "form-add",
        "form-compile",
        "form-edit",
        "form-remove",
        "form-validate",
        "cfe-borrow",
    }
)

# Imported platform operations run only through the runtime profile and ibcmd (no Designer fallback).
PROFILE_OPERATION_RUNTIME = "profile-ibcmd"
PROFILE_CONFIG_SKILLS = {
    # skill: (path option, ibcmd config command, path kind)
    "db-load-cf": ("-InputFile", "load", "input-file"),
    "db-dump-cf": ("-OutputFile", "save", "output-file"),
    "db-load-xml": ("-ConfigDir", "import", "input-dir"),
    "db-dump-xml": ("-ConfigDir", "export", "output-dir"),
}
EXTERNAL_ARTIFACT_SKILLS = {"epf-build", "erf-build", "epf-dump", "erf-dump"}
PROFILE_OPERATION_SKILLS = set(PROFILE_CONFIG_SKILLS) | EXTERNAL_ARTIFACT_SKILLS
# Native aliases that must use the ibcmd driver of the profile capability.
IBCMD_ALIAS_CAPABILITIES = {"db-create": "create-ib", "db-update": "update-db", "db-load-git": "load-src"}
PLATFORM_SKILLS = PROFILE_OPERATION_SKILLS | set(IBCMD_ALIAS_CAPABILITIES) | {"db-run"}
RUN_CLIENT_ACTIONS = {"start", "screenshot", "status", "stop", "key", "click"}
# Documentation hints; the execution contract is the dispatcher --help.
PROFILE_SKILL_HINTS = {
    "db-create": "[--profile <json>] [--run-root <dir>]",
    "db-update": "[--profile <json>] [--run-root <dir>]",
    "db-load-git": "[--profile <json>] [--run-root <dir>]",
    "db-run": "[start] [--profile <json>] [--run-root <dir>] | screenshot|status|stop|key|click --run-root <dir>",
    "db-load-cf": "[-Profile <json>] [-RunRoot <dir>] -InputFile <cf/cfe> [-Extension <name>]",
    "db-dump-cf": "[-Profile <json>] [-RunRoot <dir>] -OutputFile <cf/cfe> [-Extension <name>]",
    "db-load-xml": "[-Profile <json>] [-RunRoot <dir>] -ConfigDir <dir> [-Extension <name>]",
    "db-dump-xml": "[-Profile <json>] [-RunRoot <dir>] -ConfigDir <dir> [-Extension <name>]",
    **{
        name: "[-Profile <json>] [-RunRoot <dir>] -SourceFile <xml> -OutputFile <artifact>"
        for name in ("epf-build", "erf-build")
    },
    **{
        name: "[-Profile <json>] [-RunRoot <dir>] -InputFile <artifact> -OutputDir <dir>"
        for name in ("epf-dump", "erf-dump")
    },
}

NATIVE_ALIAS_SKILLS = {
    "db-create": {
        "shell": "./scripts/platform/create-ib.sh",
        "powershell": "./scripts/platform/create-ib.ps1",
        "preferred_native_skills": ["1c-create-ib"],
    },
    "db-update": {
        "shell": "./scripts/platform/update-db.sh",
        "powershell": "./scripts/platform/update-db.ps1",
        "preferred_native_skills": ["1c-update-db"],
    },
    "db-load-git": {
        "shell": "./scripts/platform/load-diff-src.sh",
        "powershell": "./scripts/platform/load-diff-src.ps1",
        "preferred_native_skills": ["1c-load-diff-src", "1c-load-task-src"],
    },
    "db-run": {
        "shell": "./scripts/platform/run-client.sh",
        "powershell": "./scripts/platform/run-client.ps1",
        "preferred_native_skills": ["1c-run-client"],
    },
    "web-publish": {
        "shell": "./scripts/platform/publish-http.sh",
        "powershell": "./scripts/platform/publish-http.ps1",
        "preferred_native_skills": ["1c-publish-http"],
    },
}

PREFERRED_NATIVE_SKILLS: dict[str, list[str]] = {}

REPO_SCRIPT_FORMAT = DISPATCHER_SHELL + " {skill}"


def _load_manifest() -> dict[str, object]:
    if not IMPORT_MANIFEST.is_file():
        die(f"imported skills manifest not found: {IMPORT_MANIFEST}")
    payload = read_json(IMPORT_MANIFEST)
    if not isinstance(payload, dict):
        die(f"unexpected manifest payload: {IMPORT_MANIFEST}")
    return payload


def _skill_entries() -> list[dict[str, object]]:
    payload = _load_manifest()
    skills = payload.get("skills")
    if not isinstance(skills, list):
        die(f"manifest does not contain skills[]: {IMPORT_MANIFEST}")
    return [entry for entry in skills if isinstance(entry, dict) and entry.get("name") not in RETIRED_METADATA_SKILLS]


def _find_entry(skill_name: str) -> dict[str, object]:
    for entry in _skill_entries():
        if entry.get("name") == skill_name:
            return entry
    die(f"imported skill not found in manifest: {skill_name}")


def _frontmatter_and_body(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    raw = parts[0].splitlines()[1:]
    body = parts[1]
    data: dict[str, object] = {}
    key = ""
    folded_key = ""
    for line in raw:
        if not line.strip():
            if folded_key:
                current = str(data.get(folded_key) or "")
                data[folded_key] = (current + " ").strip()
            continue
        if folded_key and line.startswith("  ") and not line.startswith("  - "):
            current = str(data.get(folded_key) or "")
            data[folded_key] = (current + " " + line.strip()).strip()
            continue
        if line.startswith("  - ") and key:
            current = data.setdefault(key, [])
            if isinstance(current, list):
                current.append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        folded_key = ""
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {">", "|"}:
            data[key] = ""
            folded_key = key
            continue
        if value in {"[]", ""}:
            data[key] = [] if value == "[]" else ""
            continue
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        data[key] = value
    return data, body


def _first_paragraph(body: str) -> str:
    cleaned: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("```"):
            if cleaned:
                break
            continue
        if not stripped:
            if cleaned:
                break
            continue
        cleaned.append(stripped)
    return " ".join(cleaned).strip()


def _short_text(value: str, limit: int = 92) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _yaml_scalar(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _skill_shell_command(skill_name: str) -> str:
    return REPO_SCRIPT_FORMAT.format(skill=skill_name)


def _skill_powershell_command(skill_name: str) -> str:
    return f"{DISPATCHER_POWERSHELL} {skill_name}"


def _preferred_native_hint(entry: dict[str, object]) -> str:
    preferred = [str(name) for name in entry.get("preferred_native_skills") or []]
    if not preferred:
        return ""
    names = ", ".join(preferred)
    return f"Prefer native {names}. "


def _discovery_description(entry: dict[str, object]) -> str:
    description = str(entry["description"]).strip()
    return (_preferred_native_hint(entry) + description).strip()


def _detect_git_metadata(source_root: Path) -> dict[str, str]:
    metadata = {
        "source_repo": str(source_root),
        "source_url": "",
        "source_commit": "",
        "synced_at_utc": timestamp_utc(),
    }
    if not (source_root / ".git").exists():
        return metadata
    metadata["source_commit"] = run_git(["rev-parse", "HEAD"], cwd=source_root, check=True).stdout.strip()
    remote = run_git(["remote", "get-url", "origin"], cwd=source_root, check=False).stdout.strip()
    if remote:
        metadata["source_url"] = remote
    return metadata


def _copy_skill_tree(source_root: Path) -> list[str]:
    source_skills = source_root / ".claude" / "skills"
    if not source_skills.is_dir():
        die(f"upstream skills directory not found: {source_skills}")
    license_file = source_root / "LICENSE"
    if not license_file.is_file():
        die(f"upstream license not found: {license_file}")

    if IMPORT_ROOT.exists():
        shutil.rmtree(IMPORT_ROOT)
    ensure_dir(IMPORT_SKILLS_ROOT)
    shutil.copy2(license_file, IMPORT_LICENSE)

    imported: list[str] = []
    for source_dir in sorted(source_skills.iterdir()):
        if not source_dir.is_dir() or not (source_dir / "SKILL.md").is_file():
            continue
        if source_dir.name in RETIRED_METADATA_SKILLS:
            continue
        shutil.copytree(
            source_dir,
            IMPORT_SKILLS_ROOT / source_dir.name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
        )
        imported.append(source_dir.name)
    return imported


def _preferred_native_skills(name: str) -> list[str]:
    native_alias = NATIVE_ALIAS_SKILLS.get(name)
    if native_alias:
        return list(native_alias.get("preferred_native_skills", []))
    return list(PREFERRED_NATIVE_SKILLS.get(name, []))


def _select_python_helper(skill_name: str, skill_dir: Path) -> tuple[str | None, str]:
    if skill_name in PROFILE_OPERATION_SKILLS:
        return None, PROFILE_OPERATION_RUNTIME
    if skill_name in NATIVE_ALIAS_SKILLS:
        return None, "native-alias"
    if skill_name in PYTHON_ALIAS_SKILLS:
        alias_skill = PYTHON_ALIAS_SKILLS[skill_name]
        return f"skills/{alias_skill}/scripts/{alias_skill}.py", "python"
    expected = skill_dir / "scripts" / f"{skill_name}.py"
    if expected.is_file():
        return f"skills/{skill_name}/scripts/{skill_name}.py", "python"
    python_candidates = sorted(skill_dir.glob("scripts/*.py"))
    if python_candidates:
        rel = python_candidates[0].relative_to(IMPORT_ROOT).as_posix()
        return rel, "python"
    run_mjs = skill_dir / "scripts" / "run.mjs"
    if run_mjs.is_file():
        return f"skills/{skill_name}/scripts/run.mjs", "node"
    if skill_name in REFERENCE_ONLY_SKILLS:
        return None, "reference"
    return None, "reference"


def _build_skill_manifest(imported_names: list[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for skill_name in sorted(imported_names):
        skill_dir = IMPORT_SKILLS_ROOT / skill_name
        frontmatter, body = _frontmatter_and_body(read_text(skill_dir / "SKILL.md"))
        description = str(frontmatter.get("description") or _first_paragraph(body) or skill_name)
        argument_hint = str(frontmatter.get("argument-hint") or "").strip()
        helper_path, runtime_kind = _select_python_helper(skill_name, skill_dir)
        reference_paths = [
            path.relative_to(IMPORT_ROOT).as_posix()
            for path in sorted(skill_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in {".md", ".json"} and path.name != "package-lock.json"
        ]
        native_alias = NATIVE_ALIAS_SKILLS.get(skill_name, {})
        result.append(
            {
                "name": skill_name,
                "description": description,
                "argument_hint": PROFILE_SKILL_HINTS.get(skill_name, argument_hint),
                "runtime_kind": runtime_kind,
                "helper_path": helper_path or "",
                "vendor_dir": f"skills/{skill_name}",
                "reference_paths": reference_paths,
                "preferred_native_skills": _preferred_native_skills(skill_name),
                "delegate_shell": str(native_alias.get("shell", "")),
                "delegate_powershell": str(native_alias.get("powershell", "")),
            }
        )
    return result


def _existing_skill_docs(skills_root: Path, imported_names: set[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in imported_names:
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        frontmatter, _ = _frontmatter_and_body(read_text(skill_file))
        repo_script = ""
        for line in read_text(skill_file).splitlines():
            if line.startswith("Repo script: `") and line.endswith("`"):
                repo_script = line[len("Repo script: `") : -1]
                break
        items.append(
            {
                "name": skill_dir.name,
                "description": str(frontmatter.get("description") or skill_dir.name),
                "repo_script": repo_script,
            }
        )
    return items


def _imported_repo_script(skill_name: str) -> str:
    return REPO_SCRIPT_FORMAT.format(skill=skill_name)


def _adaptation_notes(entry: dict[str, object]) -> list[str]:
    notes: list[str] = []
    runtime_kind = str(entry.get("runtime_kind") or "")
    preferred_value = entry.get("preferred_native_skills")
    preferred_native = [str(name) for name in preferred_value] if isinstance(preferred_value, list) else []
    if runtime_kind == "reference":
        notes.append(
            "Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы."
        )
    elif runtime_kind == "node":
        notes.append("Исполнение идёт через repo-owned dispatcher, который вызывает vendored Node/Playwright helper.")
    elif runtime_kind == "native-alias":
        notes.append(
            "Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона."
        )
    elif runtime_kind == PROFILE_OPERATION_RUNTIME:
        notes.append(
            "Dispatcher выполняет операцию через ibcmd по runtime profile (`-Profile`, по умолчанию `ONEC_PROFILE` "
            "или `env/local.json`); vendored helper и Designer не запускаются."
        )
    else:
        notes.append("Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.")
    skill_name = str(entry.get("name") or "")
    if skill_name in PROFILE_SKILL_HINTS:
        notes.append(
            f"Параметры: `{PROFILE_SKILL_HINTS[skill_name]}`. Точный контракт: `{_imported_repo_script(skill_name)} --help`."
        )
    if skill_name in IBCMD_ALIAS_CAPABILITIES:
        capability = IBCMD_ALIAS_CAPABILITIES[skill_name]
        notes.append(
            f"Запуск требует driver `ibcmd` для capability `{capability}` в runtime profile; перехода на Designer нет."
        )
    if skill_name in EXTERNAL_ARTIFACT_SKILLS:
        notes.append(
            "Сборка и выгрузка берут контекст метаданных из ИБ профиля; временная ИБ не создаётся, "
            "параметры `-V8Path` и `-InfoBase*` не поддерживаются."
        )
    if skill_name == "db-run":
        notes.append(
            "Вызов проксируется в `./scripts/platform/run-client.sh` (навык `1c-run-client`): подключение и пароль берутся "
            "из runtime profile. Прежняя форма с `-V8Path`/`-InfoBase*`/`-Password` отклоняется."
        )
    if preferred_native:
        notes.append(
            "Для native runner-agnostic workflow предпочитайте: "
            + ", ".join(f"`{name}`" for name in preferred_native)
            + "."
        )
    return notes


def _python_runtime_readiness() -> dict[str, object]:
    missing: list[str] = []
    bootstrap: list[str] = []
    try:
        import lxml.etree  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        missing.append("Python module `lxml`")
        bootstrap.append("python -m pip install lxml")
    return {
        "runtime_kind": "python",
        "ready": not missing,
        "missing_dependencies": missing,
        "bootstrap_commands": bootstrap,
        "representative_skill": REPRESENTATIVE_PYTHON_SKILL,
    }


def _node_runtime_readiness() -> dict[str, object]:
    missing: list[str] = []
    bootstrap: list[str] = []
    scripts_dir = IMPORT_ROOT / "skills" / REPRESENTATIVE_NODE_SKILL / "scripts"
    if shutil.which("node") is None:
        missing.append("Node.js runtime `node`")
    playwright_package = scripts_dir / "node_modules" / "playwright" / "package.json"
    if not playwright_package.is_file():
        missing.append("Node package `playwright` under `automation/vendor/cc-1c-skills/skills/web-test/scripts`")
        bootstrap.append("cd automation/vendor/cc-1c-skills/skills/web-test/scripts && npm install")
        bootstrap.append("cd automation/vendor/cc-1c-skills/skills/web-test/scripts && npx playwright install chromium")
    return {
        "runtime_kind": "node",
        "ready": not missing,
        "missing_dependencies": missing,
        "bootstrap_commands": bootstrap,
        "representative_skill": REPRESENTATIVE_NODE_SKILL,
    }


def imported_skill_readiness_payload() -> dict[str, object]:
    python_runtime = _python_runtime_readiness()
    node_runtime = _node_runtime_readiness()
    reference_entry = _find_entry(REPRESENTATIVE_REFERENCE_SKILL)
    native_alias_entry = _find_entry(REPRESENTATIVE_NATIVE_ALIAS_SKILL)
    return {
        "readinessRole": "template-managed-imported-skill-readiness",
        "canonicalTarget": CANONICAL_READINESS_TARGET,
        "canonicalCommand": CANONICAL_READINESS_COMMAND,
        "guidanceDocs": [CANONICAL_READINESS_DOC, CANONICAL_ENV_DOC],
        "fullCatalog": FULL_SKILLS_CATALOG,
        "representative": {
            "python": {
                **python_runtime,
                "entrypoint": _skill_shell_command(REPRESENTATIVE_PYTHON_SKILL),
            },
            "node": {
                **node_runtime,
                "entrypoint": _skill_shell_command(REPRESENTATIVE_NODE_SKILL),
            },
            "reference": {
                "runtime_kind": "reference",
                "ready": True,
                "missing_dependencies": [],
                "bootstrap_commands": [],
                "representative_skill": REPRESENTATIVE_REFERENCE_SKILL,
                "entrypoint": _skill_shell_command(REPRESENTATIVE_REFERENCE_SKILL),
                "notes": ["Vendored markdown only; no local runtime bootstrap is required."],
            },
            "nativeAlias": {
                "runtime_kind": "native-alias",
                "ready": True,
                "missing_dependencies": [],
                "bootstrap_commands": [],
                "representative_skill": REPRESENTATIVE_NATIVE_ALIAS_SKILL,
                "entrypoint": _skill_shell_command(REPRESENTATIVE_NATIVE_ALIAS_SKILL),
                "preferred_native_skills": [
                    str(name) for name in native_alias_entry.get("preferred_native_skills") or []
                ],
            },
        },
        "skills": {
            "reference": {
                "name": str(reference_entry["name"]),
                "description": str(reference_entry["description"]),
            },
            "nativeAlias": {
                "name": str(native_alias_entry["name"]),
                "description": str(native_alias_entry["description"]),
            },
        },
    }


def _readiness_lines(payload: dict[str, object]) -> list[str]:
    representative = dict(payload.get("representative") or {})
    lines = [
        "# Imported Skill Readiness",
        "",
        f"Canonical target: `{payload['canonicalTarget']}`",
        f"Direct entrypoint: `{payload['canonicalCommand']}`",
        "Guidance docs: " + ", ".join(f"`{item}`" for item in payload.get("guidanceDocs", [])),
        f"Full catalog: `{payload['fullCatalog']}`",
        "",
        "## Representative Runtimes",
        "",
    ]
    for key in ("python", "node", "reference", "nativeAlias"):
        item = representative.get(key) or {}
        skill_name = str(item.get("representative_skill") or key)
        runtime_kind = str(item.get("runtime_kind") or key)
        if item.get("ready"):
            line = f"- `{runtime_kind}` (`{skill_name}`): ready"
            preferred_native = [str(name) for name in item.get("preferred_native_skills") or []]
            if preferred_native:
                line += " via native workflow " + ", ".join(f"`{name}`" for name in preferred_native)
            lines.append(line)
            notes = [str(note) for note in item.get("notes") or []]
            for note in notes:
                lines.append(f"  note: {note}")
            continue
        missing = ", ".join(str(dep) for dep in item.get("missing_dependencies") or [])
        lines.append(f"- `{runtime_kind}` (`{skill_name}`): missing {missing}")
        for command in item.get("bootstrap_commands") or []:
            lines.append(f"  bootstrap: `{command}`")
    return lines


def render_imported_skill_readiness(json_mode: bool = False) -> str:
    payload = imported_skill_readiness_payload()
    if json_mode:
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return "\n".join(_readiness_lines(payload)) + "\n"


def _runtime_readiness_for_kind(runtime_kind: str) -> dict[str, object]:
    payload = imported_skill_readiness_payload()
    representative = dict(payload.get("representative") or {})
    if runtime_kind == "python":
        return dict(representative.get("python") or {})
    if runtime_kind == "node":
        return dict(representative.get("node") or {})
    if runtime_kind == "reference":
        return dict(representative.get("reference") or {})
    if runtime_kind == "native-alias":
        return dict(representative.get("nativeAlias") or {})
    return {
        "runtime_kind": runtime_kind,
        "ready": True,
        "missing_dependencies": [],
        "bootstrap_commands": [],
    }


def _print_runtime_not_ready(entry: dict[str, object], readiness: dict[str, object]) -> int:
    missing = [str(item) for item in readiness.get("missing_dependencies") or []]
    print(f"Imported skill `{entry['name']}` is not ready in this local contour.", file=sys.stderr)
    print(f"Runtime kind: {entry['runtime_kind']}", file=sys.stderr)
    if missing:
        print("Missing dependency class: " + ", ".join(missing), file=sys.stderr)
    print(f"Canonical readiness target: {CANONICAL_READINESS_TARGET}", file=sys.stderr)
    print(f"Direct readiness command: {CANONICAL_READINESS_COMMAND}", file=sys.stderr)
    print(f"Windows readiness command: {WINDOWS_READINESS_COMMAND}", file=sys.stderr)
    print(f"Guidance docs: {CANONICAL_READINESS_DOC}, {CANONICAL_ENV_DOC}", file=sys.stderr)
    bootstrap = [str(command) for command in readiness.get("bootstrap_commands") or []]
    if bootstrap:
        print("Bootstrap suggestions:", file=sys.stderr)
        for command in bootstrap:
            print(f"- {command}", file=sys.stderr)
    return 2


def _vendor_reference(entry: dict[str, object]) -> str:
    return f"automation/vendor/cc-1c-skills/{entry['vendor_dir']}/SKILL.md"


def _render_agents_skill(entry: dict[str, object]) -> str:
    description = str(entry["description"]).strip()
    discovery_description = _discovery_description(entry)
    short_description = _short_text(discovery_description, 72)
    skill_name = str(entry["name"])
    notes = _adaptation_notes(entry)
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: {_yaml_scalar(short_description)}",
        "metadata:",
        f"  short-description: {_yaml_scalar(short_description)}",
        "---",
        "",
        SYNC_MARKER,
        "",
        f"# Agent Skill: {skill_name}",
        "",
        f"Repo script: `{_imported_repo_script(skill_name)}`",
        f"Windows launcher: `{_skill_powershell_command(skill_name)}`",
        "",
        "## Use When",
        "",
        f"- {description}",
        "- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.",
        "",
        "## Usage",
        "",
        "```bash",
        f"{_imported_repo_script(skill_name)} --help",
        f"{_imported_repo_script(skill_name)} ...",
        "```",
        "",
        "```powershell",
        f"{_skill_powershell_command(skill_name)} --help",
        f"{_skill_powershell_command(skill_name)} ...",
        "```",
        "",
        "## Adaptation",
        "",
        f"- Vendored upstream source: `{_vendor_reference(entry)}`",
        f"- Runtime kind: `{entry['runtime_kind']}`",
        f"- Readiness target: `{CANONICAL_READINESS_TARGET}`",
        f"- Direct readiness command: `{CANONICAL_READINESS_COMMAND}`",
        f"- Windows readiness command: `{WINDOWS_READINESS_COMMAND}`",
    ]
    for note in notes:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.",
            (
                "- Параметры определяет `--help` repo-owned dispatcher; vendored upstream `SKILL.md` описывает исходный инструмент, а не текущий контракт."
                if skill_name in PLATFORM_SKILLS
                else "- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`."
            ),
            "- Если dispatcher сообщает о missing dependencies, сначала используйте canonical readiness path, а не helper traceback.",
            "- Не переносите upstream PowerShell snippets в новый automation contract шаблона.",
            "",
        ]
    )
    if skill_name in PLATFORM_SKILLS:
        lines.extend(
            [
                "## Наблюдение запуска",
                "",
                "Запуск ibcmd или клиента наблюдается общим адаптером: run-root содержит `observation.jsonl`, `summary.json`,",
                "`stdout.log` и `stderr.log`, пароли в них скрыты. Состояние долгого запуска смотрите через",
                "[1c-observe-run](../1c-observe-run/SKILL.md). Остановка при неизменном прогрессе включается",
                "только порогом `ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS` вызывающей обёртки.",
                "",
            ]
        )
    return "\n".join(lines)


def _mapping_row(
    intent: str, codex_skill: str, claude_skill: str, repo_entrypoint: str, extra: str | None = None
) -> str:
    details = extra or ""
    return f"| {intent} | `{codex_skill}` | `{claude_skill}` | `{repo_entrypoint}` | {details} |"


def _render_agents_readme(
    native_codex: list[dict[str, str]],
    native_claude: list[dict[str, str]],
    imported_entries: list[dict[str, object]],
    upstream: dict[str, str],
) -> str:
    claude_names = {entry["name"] for entry in native_claude}
    lines = [
        "# Project-Scoped Codex Skills",
        "",
        "Эти skills являются Codex-discoverable фасадом над versioned repo scripts.",
        "Claude-facing equivalents лежат в [.claude/skills/README.md](../../.claude/skills/README.md).",
        "`.agents/skills/<имя>` — единственный источник навыка; `.claude/skills/<имя>` — его зеркало. Правьте источник и выполняйте `make sync-claude-skills` (`./make.ps1 sync-claude-skills`).",
        "",
        "## Native Runner-Agnostic Skills",
        "",
        "| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in native_codex:
        lines.append(
            _mapping_row(
                entry["description"],
                entry["name"],
                entry["name"] if entry["name"] in claude_names else "-",
                entry["repo_script"],
                "native template capability",
            )
        )
    lines.extend(
        [
            "",
            "## Imported Compatibility Pack (`cc-1c-skills`)",
            "",
            f"- Upstream source: `{upstream.get('source_url') or upstream.get('source_repo') or 'unknown'}`",
            f"- Upstream commit: `{upstream.get('source_commit') or 'unknown'}`",
            "- Vendor root: [`automation/vendor/cc-1c-skills/README.md`](../../automation/vendor/cc-1c-skills/README.md)",
            f"- Canonical readiness target: `{CANONICAL_READINESS_TARGET}`",
            f"- Direct readiness command: `{CANONICAL_READINESS_COMMAND}`",
            f"- Windows readiness command: `{WINDOWS_READINESS_COMMAND}`",
            "",
            "| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for entry in imported_entries:
        preferred = list(entry.get("preferred_native_skills") or [])
        extra = str(entry["runtime_kind"])
        if preferred:
            extra += "; prefer " + ", ".join(preferred)
        lines.append(
            _mapping_row(
                str(entry["description"]),
                str(entry["name"]),
                str(entry["name"]),
                _imported_repo_script(str(entry["name"])),
                extra,
            )
        )
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Source of truth для выполнения находится в `scripts/`, а не в `SKILL.md`.",
            "- Если меняется runtime behavior imported skills, меняйте repo-owned dispatcher или vendored helper, а не generated skill markdown вручную.",
            "- Для baseline repo/doc/tooling changes начинайте с `repo-agent-verify`.",
            "- При missing dependencies сначала используйте canonical readiness path, затем запускайте executable imported skills.",
            "- Imported compatibility pack не заменяет native runner-agnostic skills: при совпадении intent предпочитайте native workflow шаблона.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_claude_readme(
    native_codex: list[dict[str, str]],
    native_claude: list[dict[str, str]],
    imported_entries: list[dict[str, object]],
    upstream: dict[str, str],
) -> str:
    codex_names = {entry["name"] for entry in native_codex}
    lines = [
        "# Project-Scoped 1C Skills",
        "",
        "Эти skills являются project-scoped фасадом над versioned repo scripts.",
        "Codex-facing equivalents лежат в [.agents/skills/README.md](../../.agents/skills/README.md).",
        "`.agents/skills/<имя>` — единственный источник навыка; `.claude/skills/<имя>` — его зеркало. Правьте источник и выполняйте `make sync-claude-skills` (`./make.ps1 sync-claude-skills`).",
        "",
        "## Native Runner-Agnostic Skills",
        "",
        "| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in native_claude:
        lines.append(
            _mapping_row(
                entry["description"],
                entry["name"] if entry["name"] in codex_names else "-",
                entry["name"],
                entry["repo_script"],
                "native template capability",
            )
        )
    lines.extend(
        [
            "",
            "## Imported Compatibility Pack (`cc-1c-skills`)",
            "",
            f"- Upstream source: `{upstream.get('source_url') or upstream.get('source_repo') or 'unknown'}`",
            f"- Upstream commit: `{upstream.get('source_commit') or 'unknown'}`",
            "- Vendor root: [`automation/vendor/cc-1c-skills/README.md`](../../automation/vendor/cc-1c-skills/README.md)",
            f"- Canonical readiness target: `{CANONICAL_READINESS_TARGET}`",
            f"- Direct readiness command: `{CANONICAL_READINESS_COMMAND}`",
            f"- Windows readiness command: `{WINDOWS_READINESS_COMMAND}`",
            "",
            "| User intent | Codex skill | Claude skill | Repo entrypoint | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for entry in imported_entries:
        preferred = list(entry.get("preferred_native_skills") or [])
        extra = str(entry["runtime_kind"])
        if preferred:
            extra += "; prefer " + ", ".join(preferred)
        lines.append(
            _mapping_row(
                str(entry["description"]),
                str(entry["name"]),
                str(entry["name"]),
                _imported_repo_script(str(entry["name"])),
                extra,
            )
        )
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Source of truth для выполнения находится в `scripts/`, а не в `SKILL.md`.",
            "- Если нужно поменять flags, artifact contract или adapter behavior imported skills, сначала меняйте repo-owned dispatcher или vendored helper.",
            "- При missing dependencies сначала используйте canonical readiness path, затем запускайте executable imported skills.",
            "- Native runner-agnostic skills остаются предпочтительным surface для template-owned runtime workflows.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_vendor_readme(imported_entries: list[dict[str, object]], upstream: dict[str, str]) -> str:
    lines = [
        "# Vendored `cc-1c-skills` Import",
        "",
        "Этот каталог содержит vendored upstream pack из `cc-1c-skills`, используемый для генерации `.agents/skills` и `.claude/skills` compatibility surface.",
        "",
        "## Provenance",
        "",
        f"- source: `{upstream.get('source_url') or upstream.get('source_repo') or 'unknown'}`",
        f"- commit: `{upstream.get('source_commit') or 'unknown'}`",
        f"- synced at: `{upstream.get('synced_at_utc') or 'unknown'}`",
        "- license: [`LICENSE`](LICENSE)",
        "",
        "## Layout",
        "",
        "- `skills/<name>/` — upstream skill directories from `.claude/skills/`",
        "- `imported-skills.json` — checked-in manifest for dispatch/generation",
        "",
        "## Refresh",
        "",
        "```bash",
        "python -m scripts.python.cli sync-imported-skills --source /path/to/cc-1c-skills",
        "./scripts/llm/export-context.sh --write",
        "```",
        "",
        "## Imported Skills",
        "",
        f"- count: `{len(imported_entries)}`",
        f"- dispatcher: `{DISPATCHER_SHELL} <skill>` / `{DISPATCHER_POWERSHELL} <skill>`",
        "",
        "Do not edit vendored generated skill facades manually; regenerate them from this vendor source instead.",
        "",
    ]
    return "\n".join(lines)


def _is_overlay_managed(rel: str) -> bool:
    excluded_exact = {
        "[[[ _copier_conf.answers_file ]]]",
        "[[[ _copier_conf.answers_file ]]].jinja",
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
        "copier.yml",
        ".codex/config.toml",
        "automation/context/template-source-project-map.md",
        "automation/context/template-source-metadata-index.json",
        "automation/context/template-source-source-files.txt",
        "automation/context/template-source-tree.txt",
        "automation/context/template-update-preserve-paths.txt",
        "docs/work-items/README.md",
        "docs/work-items/TEMPLATE.md",
        "tests/smoke/template-release-workflow.sh",
        "tests/golden/run.sh",
    }
    if rel.startswith("env/") and rel.endswith(".example.json.jinja"):
        return False
    if rel in excluded_exact:
        return False
    excluded_prefixes = (
        "openspec/",
        ".claude/commands/",
        "tooling/",
        ".githooks/",
        "scripts/release/",
        "analysis/testing/",
        ".claude/skills/openspec-",
        ".codex/skills/openspec-",
    )
    if rel.startswith(excluded_prefixes):
        return False
    if rel.startswith("src/"):
        if rel in {"src/AGENTS.md", "src/README.md"}:
            return True
        return (
            rel.startswith("src/epf/TemplateXUnitHarness/")
            or rel in {"src/epf/AGENT_TEMPLATES.md", "src/cfe/AGENT_TEMPLATES.md"}
            or rel.startswith("src/epf/_templates/")
            or rel.startswith("src/cfe/_templates/")
        )
    return True


def _refresh_overlay_manifest() -> None:
    tracked = run_git(
        ["ls-files", "--cached", "--others", "--exclude-standard"], cwd=PROJECT_ROOT, check=True
    ).stdout.splitlines()
    entries = sorted({rel.strip() for rel in tracked if rel.strip() and _is_overlay_managed(rel.strip())})
    write_text(OVERLAY_MANIFEST, "\n".join(entries) + "\n")


def _remove_previous_generated_surfaces(previous_names: list[str]) -> None:
    for skills_root in (repo_path(".agents", "skills"), repo_path(".claude", "skills")):
        for skill_name in sorted(set(previous_names) | RETIRED_METADATA_SKILLS):
            target = skills_root / skill_name
            if target.is_dir():
                shutil.rmtree(target)


def _write_generated_surfaces(
    imported_entries: list[dict[str, object]], upstream: dict[str, str], previous_names: list[str]
) -> None:
    _remove_previous_generated_surfaces(previous_names)

    agents_root = repo_path(".agents", "skills")
    ensure_dir(agents_root)

    for entry in imported_entries:
        skill_name = str(entry["name"])
        write_text(agents_root / skill_name / "SKILL.md", _render_agents_skill(entry))

    _mirror_claude_skills(repo_path(), check=False)
    _write_skill_readmes(imported_entries, upstream)


def _write_skill_readmes(imported_entries: list[dict[str, object]], upstream: dict[str, str]) -> None:
    imported_names = {str(entry["name"]) for entry in imported_entries}
    native = _existing_skill_docs(repo_path(".agents", "skills"), imported_names)
    write_text(
        repo_path(".agents", "skills", "README.md"), _render_agents_readme(native, native, imported_entries, upstream)
    )
    write_text(
        repo_path(".claude", "skills", "README.md"), _render_claude_readme(native, native, imported_entries, upstream)
    )


def _skill_tree(skill_dir: Path) -> dict[str, bytes]:
    return {
        path.relative_to(skill_dir).as_posix(): path.read_bytes()
        for path in sorted(skill_dir.rglob("*"))
        if path.is_file()
    }


def _mirror_claude_skills(root: Path, check: bool) -> list[str]:
    """Keep .claude/skills/<name> byte-identical to .agents/skills/<name>.

    README.md and OpenSpec-managed openspec-* skills are owned elsewhere and are left alone.
    """
    agents_root = root / ".agents" / "skills"
    claude_root = root / ".claude" / "skills"
    sources = {path.name: path for path in sorted(agents_root.iterdir()) if (path / "SKILL.md").is_file()}
    drift: list[str] = []
    for name, source in sources.items():
        target = claude_root / name
        if target.is_dir() and not target.is_symlink() and _skill_tree(target) == _skill_tree(source):
            continue
        drift.append(f".claude/skills/{name}")
        if not check:
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            ensure_dir(claude_root)
            shutil.copytree(source, target)
    if claude_root.is_dir():
        for target in sorted(claude_root.iterdir()):
            if target.name == "README.md" or target.name.startswith("openspec-") or target.name in sources:
                continue
            drift.append(f".claude/skills/{target.name}")
            if not check:
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
    return drift


def claude_skill_mirror_drift(root: Path) -> list[str]:
    return _mirror_claude_skills(root, check=True)


def sync_claude_skills(check: bool = False) -> int:
    drift = _mirror_claude_skills(repo_path(), check=check)
    if check:
        for rel in drift:
            print(f"stale Claude skill mirror: {rel}; run make sync-claude-skills", file=sys.stderr)
        return 1 if drift else 0
    print(f"[sync-claude-skills] updated {len(drift)} Claude skill mirror entries")
    return 0


def sync_imported_skills(source_root: Path) -> int:
    source_root = source_root.resolve()
    previous_names: list[str] = []
    if IMPORT_MANIFEST.is_file():
        previous_names = [str(entry.get("name")) for entry in _skill_entries() if entry.get("name")]

    imported_names = _copy_skill_tree(source_root)
    upstream = _detect_git_metadata(source_root)
    imported_entries = _build_skill_manifest(imported_names)
    write_json(UPSTREAM_METADATA, upstream)
    write_json(IMPORT_MANIFEST, {"upstream": upstream, "generated_at_utc": timestamp_utc(), "skills": imported_entries})
    write_text(IMPORT_ROOT / "README.md", _render_vendor_readme(imported_entries, upstream))
    _write_generated_surfaces(imported_entries, upstream, previous_names)
    _refresh_overlay_manifest()
    print(f"[sync-imported-skills] synced {len(imported_entries)} imported skills from {source_root}")
    return 0


def _run_native_alias(entry: dict[str, object], args: list[str]) -> int:
    delegate = str(entry.get("delegate_powershell") if sys.platform == "win32" else entry.get("delegate_shell") or "")
    if not delegate:
        die(f"native alias delegate is not configured for {entry['name']}")
    delegate_path = PROJECT_ROOT / delegate.lstrip("./")
    if not delegate_path.is_file():
        die(f"delegate script not found: {delegate_path}")
    if sys.platform == "win32":
        command = ["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(delegate_path), *args]
    else:
        command = ["bash", str(delegate_path), *args]
    result = run_process(command, cwd=PROJECT_ROOT, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def _run_python_helper(entry: dict[str, object], args: list[str]) -> int:
    readiness = _runtime_readiness_for_kind("python")
    if not readiness.get("ready"):
        return _print_runtime_not_ready(entry, readiness)
    helper = str(entry.get("helper_path") or "")
    if not helper:
        die(f"python helper is not configured for {entry['name']}")
    helper_path = IMPORT_ROOT / helper
    if not helper_path.is_file():
        die(f"helper script not found: {helper_path}")
    result = run_process([sys.executable, str(helper_path), *args], cwd=PROJECT_ROOT, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def _run_node_helper(entry: dict[str, object], args: list[str]) -> int:
    readiness = _runtime_readiness_for_kind("node")
    if not readiness.get("ready"):
        return _print_runtime_not_ready(entry, readiness)
    helper = str(entry.get("helper_path") or "")
    if not helper:
        die(f"node helper is not configured for {entry['name']}")
    helper_path = IMPORT_ROOT / helper
    if not helper_path.is_file():
        die(f"helper script not found: {helper_path}")
    result = run_process(["node", str(helper_path), *args], cwd=PROJECT_ROOT, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def _render_reference(entry: dict[str, object]) -> str:
    preferred_native = list(entry.get("preferred_native_skills") or [])
    lines = [
        f"Imported skill: {entry['name']}",
        f"Description: {entry['description']}",
        f"Vendor source: {_vendor_reference(entry)}",
        f"Runtime kind: {entry['runtime_kind']}",
    ]
    if preferred_native:
        lines.append("Preferred native skills: " + ", ".join(preferred_native))
    reference_paths = list(entry.get("reference_paths") or [])
    if reference_paths:
        lines.append("Reference files:")
        for rel in reference_paths[:12]:
            lines.append(f"- automation/vendor/cc-1c-skills/{rel}")
    lines.append("")
    lines.append(
        "Use the vendored upstream material as guidance; this imported skill is reference-only in the runner-agnostic template."
    )
    return "\n".join(lines) + "\n"


def _wants_help(args: list[str]) -> bool:
    return any(arg in {"--help", "-h"} for arg in args)


def _load_profile(profile_input: str) -> RuntimeProfile:
    profile = load_runtime_profile(resolve_runtime_profile_path(profile_input))
    if profile is None:
        die("imported platform skill requires a runtime profile; pass -Profile/--profile or create env/local.json")
    return profile


def _option_value(args: list[str], name: str) -> str:
    for index, value in enumerate(args[:-1]):
        if value == name:
            return args[index + 1]
    return ""


def _require_ibcmd_driver(skill_name: str, args: list[str]) -> None:
    from .runtime import resolve_capability_driver

    capability = IBCMD_ALIAS_CAPABILITIES[skill_name]
    profile = _load_profile(_option_value(args, "--profile"))
    if resolve_capability_driver(profile, capability) != "ibcmd":
        die(
            f"{skill_name} requires capabilities driver=ibcmd for {capability} in {profile.path}; Designer fallback is retired"
        )


def _reject_legacy_db_run(args: list[str]) -> None:
    legacy = sorted({arg for arg in args if arg.startswith("-") and not arg.startswith("--") and arg[1:2].isupper()})
    if legacy:
        die(
            "db-run no longer starts 1C from -V8Path/-InfoBase*/-Password arguments (" + ", ".join(legacy) + "); "
            "use --profile <json> with the runtime profile or a run-client action, see 1c-run-client"
        )


def _parse_operation_args(skill_name: str, args: list[str]) -> argparse.Namespace | int:
    parser = argparse.ArgumentParser(
        prog=f"{DISPATCHER_SHELL} {skill_name}",
        allow_abbrev=False,
        description="Runs the imported operation through ibcmd with the runtime profile; no Designer fallback.",
    )
    parser.add_argument("-Profile", default="", help="runtime profile JSON (default: ONEC_PROFILE or env/local.json)")
    parser.add_argument("-RunRoot", default="", help="evidence directory (default: new directory under .artifacts)")
    parser.add_argument("-DryRun", action="store_true", help="publish summary.json without starting ibcmd")
    if skill_name in PROFILE_CONFIG_SKILLS:
        option = PROFILE_CONFIG_SKILLS[skill_name][0]
        parser.add_argument(option, dest="path", required=True)
        parser.add_argument("-Extension", default="")
        if skill_name == "db-dump-xml":
            parser.add_argument("-Mode", choices=["Full"], default="Full")
            parser.add_argument("-Format", choices=["Hierarchical"], default="Hierarchical")
    elif skill_name.endswith("-build"):
        parser.add_argument("-SourceFile", dest="source", required=True, help="root XML of the external object")
        parser.add_argument("-OutputFile", dest="output", required=True)
    else:
        parser.add_argument("-InputFile", dest="source", required=True)
        parser.add_argument("-OutputDir", dest="output", required=True)
    try:
        return parser.parse_args(args)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2


def _operation_run_root(skill_name: str, requested: str) -> Path:
    if requested:
        return Path(requested).resolve()
    base = PROJECT_ROOT / ".artifacts" / "imported-skills"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{skill_name}-", dir=base))


def _copy_external_sources(root_xml: Path, destination: Path) -> Path:
    """Copy the root XML and its object tree; BSL modules get the UTF-8 BOM that ibcmd import expects."""
    object_root = root_xml.parent / root_xml.stem
    if not root_xml.is_file() or not object_root.is_dir():
        die(f"external artifact build requires a root XML with a matching object directory: {root_xml}")
    shutil.copy2(root_xml, destination / root_xml.name)
    shutil.copytree(object_root, destination / root_xml.stem)
    for module in (destination / root_xml.stem).rglob("*.bsl"):
        content = module.read_bytes()
        if content.startswith(b"\xef\xbb\xbf"):
            continue
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            die(f"BSL source is not UTF-8: {module.relative_to(destination)}")
        module.write_bytes(b"\xef\xbb\xbf" + content)
    return destination


def _run_profile_operation(skill_name: str, args: list[str]) -> int:
    from .cfe_runtime import execute_profile_operation, ibcmd_command, validate_extension_name

    parsed = _parse_operation_args(skill_name, args)
    if isinstance(parsed, int):
        return parsed
    profile = _load_profile(parsed.Profile)
    run_root = _operation_run_root(skill_name, parsed.RunRoot)
    context: dict[str, object] = {"imported_skill": skill_name}
    expected: Path | None = None
    with tempfile.TemporaryDirectory(prefix=f"{skill_name}-sources-") as temp:
        if skill_name in PROFILE_CONFIG_SKILLS:
            _option, verb, kind = PROFILE_CONFIG_SKILLS[skill_name]
            path = Path(parsed.path).resolve()
            if kind == "input-file" and not path.is_file():
                die(f"input file not found: {path}")
            if kind == "input-dir" and not (path / "Configuration.xml").is_file():
                die(f"configuration XML directory not found: {path}")
            if not parsed.DryRun and kind == "output-file":
                path.parent.mkdir(parents=True, exist_ok=True)
            if not parsed.DryRun and kind == "output-dir":
                path.mkdir(parents=True, exist_ok=True)
            command = ibcmd_command(profile, "config", verb, dry_run=parsed.DryRun)
            if parsed.Extension:
                command.append(f"--extension={validate_extension_name(parsed.Extension)}")
            command.append(str(path))
            context.update(path=str(path), extension_name=parsed.Extension or None)
            expected = path if kind == "output-file" else None
        else:
            source = Path(parsed.source).resolve()
            output = Path(parsed.output).resolve()
            if not source.is_file():
                die(f"input file not found: {source}")
            if skill_name.endswith("-build"):
                sources = _copy_external_sources(source, Path(temp))
                if not parsed.DryRun:
                    output.parent.mkdir(parents=True, exist_ok=True)
                command = [
                    *ibcmd_command(profile, "config", "import", dry_run=parsed.DryRun),
                    f"--out={output}",
                    str(sources),
                ]
                expected = output
            else:
                if not parsed.DryRun:
                    output.mkdir(parents=True, exist_ok=True)
                command = [
                    *ibcmd_command(profile, "config", "export", dry_run=parsed.DryRun),
                    f"--file={source}",
                    str(output),
                ]
            context.update(source=str(source), output=str(output))
        exit_code = execute_profile_operation(
            f"imported-{skill_name}",
            profile,
            [command],
            run_root,
            dry_run=parsed.DryRun,
            context=context,
            expected_result=expected,
        )
    print(f"[imported-skill] {skill_name} run_root={run_root}")
    print(f"[imported-skill] summary={run_root / 'summary.json'}")
    return exit_code


def _alias_entry(skill_name: str) -> dict[str, object]:
    alias = NATIVE_ALIAS_SKILLS[skill_name]
    return {"name": skill_name, "delegate_shell": alias["shell"], "delegate_powershell": alias["powershell"]}


def _run_streaming_delegate(entry: dict[str, object], args: list[str]) -> int:
    """Proxy a long interactive delegate without capturing its output."""
    delegate = str(entry.get("delegate_powershell") if sys.platform == "win32" else entry.get("delegate_shell") or "")
    delegate_path = PROJECT_ROOT / delegate.lstrip("./")
    if not delegate or not delegate_path.is_file():
        die(f"delegate script not found for {entry['name']}: {delegate}")
    if sys.platform == "win32":
        command = ["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(delegate_path), *args]
    else:
        command = ["bash", str(delegate_path), *args]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


def run_imported_skill(skill_name: str, args: list[str]) -> int:
    entry = _find_entry(skill_name)
    if skill_name in PROFILE_OPERATION_SKILLS:
        return _run_profile_operation(skill_name, args)
    if skill_name == "db-run":
        _reject_legacy_db_run(args)
        return _run_streaming_delegate(_alias_entry(skill_name), args)
    if skill_name in IBCMD_ALIAS_CAPABILITIES:
        if not _wants_help(args):
            _require_ibcmd_driver(skill_name, args)
        return _run_native_alias(_alias_entry(skill_name), args)
    runtime_kind = str(entry.get("runtime_kind") or "")
    if runtime_kind == "native-alias":
        return _run_native_alias(entry, args)
    if runtime_kind == "python":
        return _run_python_helper(entry, args)
    if runtime_kind == "node":
        return _run_node_helper(entry, args)
    print(_render_reference(entry), end="")
    return 0
