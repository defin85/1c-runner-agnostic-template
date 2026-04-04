from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .common import PROJECT_ROOT, die, ensure_dir, read_json, read_text, repo_path, run_git, run_process, timestamp_utc, write_json, write_text


IMPORT_ROOT = repo_path("automation", "vendor", "cc-1c-skills")
IMPORT_SKILLS_ROOT = IMPORT_ROOT / "skills"
IMPORT_LICENSE = IMPORT_ROOT / "LICENSE"
IMPORT_MANIFEST = IMPORT_ROOT / "imported-skills.json"
UPSTREAM_METADATA = IMPORT_ROOT / "UPSTREAM.json"
OVERLAY_MANIFEST = repo_path("automation", "context", "template-managed-paths.txt")
SYNC_MARKER = "<!-- GENERATED: sync-imported-skills -->"
DISPATCHER_SHELL = "./scripts/skills/run-imported-skill.sh"
DISPATCHER_POWERSHELL = "./scripts/skills/run-imported-skill.ps1"

REFERENCE_ONLY_SKILLS = {
    "db-list",
    "epf-bsp-add-command",
    "epf-bsp-init",
    "form-patterns",
}

PYTHON_ALIAS_SKILLS = {
    "erf-build": "epf-build",
    "erf-dump": "epf-dump",
    "erf-validate": "epf-validate",
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
    "web-publish": {
        "shell": "./scripts/platform/publish-http.sh",
        "powershell": "./scripts/platform/publish-http.ps1",
        "preferred_native_skills": ["1c-publish-http"],
    },
}

PREFERRED_NATIVE_SKILLS = {
    "db-load-git": ["1c-load-diff-src", "1c-load-task-src"],
}

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
    return [entry for entry in skills if isinstance(entry, dict)]


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
                "argument_hint": argument_hint,
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
    preferred_native = list(entry.get("preferred_native_skills") or [])
    if runtime_kind == "reference":
        notes.append("Это reference-only импорт: repo script печатает адаптированную сводку и указывает на vendored upstream материалы.")
    elif runtime_kind == "node":
        notes.append("Исполнение идёт через repo-owned dispatcher, который вызывает vendored Node/Playwright helper.")
    elif runtime_kind == "native-alias":
        notes.append("Это compatibility alias: dispatcher проксирует вызов в native runner-agnostic capability шаблона.")
    else:
        notes.append("Исполнение идёт через repo-owned dispatcher, который вызывает vendored Python helper.")
    if preferred_native:
        notes.append("Для native runner-agnostic workflow предпочитайте: " + ", ".join(f"`{name}`" for name in preferred_native) + ".")
    return notes


def _vendor_reference(entry: dict[str, object]) -> str:
    return f"automation/vendor/cc-1c-skills/{entry['vendor_dir']}/SKILL.md"


def _render_agents_skill(entry: dict[str, object]) -> str:
    description = str(entry["description"]).strip()
    short_description = _short_text(description, 72)
    skill_name = str(entry["name"])
    notes = _adaptation_notes(entry)
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: Импортированный compatibility skill из `cc-1c-skills`: {description}",
        "metadata:",
        f"  short-description: {short_description}",
        "---",
        "",
        SYNC_MARKER,
        "",
        f"# Agent Skill: {skill_name}",
        "",
        f"Repo script: `{_imported_repo_script(skill_name)}`",
        "",
        "## Use When",
        f"",
        f"- {description}",
        f"- Нужно использовать template-managed импортированный workflow без копирования inline логики из upstream `SKILL.md`.",
        "",
        "## Usage",
        "",
        "```bash",
        f"{_imported_repo_script(skill_name)} --help",
        f"{_imported_repo_script(skill_name)} ...",
        "```",
        "",
        "## Adaptation",
        "",
        f"- Vendored upstream source: `{_vendor_reference(entry)}`",
        f"- Runtime kind: `{entry['runtime_kind']}`",
    ]
    for note in notes:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Публичный contract для этого skill находится в repo-owned dispatcher, а не в vendored markdown.",
            "- Если нужны детали параметров, сначала читайте vendored upstream `SKILL.md`, затем helper-скрипты из `automation/vendor/cc-1c-skills/`.",
            "- Не переносите upstream PowerShell snippets в новый automation contract шаблона.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_claude_skill(entry: dict[str, object]) -> str:
    skill_name = str(entry["name"])
    description = str(entry["description"]).strip()
    argument_hint = str(entry.get("argument_hint") or "[args...]").strip() or "[args...]"
    notes = _adaptation_notes(entry)
    lines = [
        "---",
        f"name: {skill_name}",
        f"description: Импортированный compatibility skill из cc-1c-skills. {description}",
        f"argument-hint: {argument_hint}",
        "allowed-tools:",
        "  - Bash",
        "  - Read",
        "  - Glob",
        "---",
        "",
        SYNC_MARKER,
        "",
        f"# /{skill_name}",
        "",
        f"Repo script: `{_imported_repo_script(skill_name)}`",
        "",
        "## Use When",
        "",
        f"- {description}",
        "- Нужно использовать template-managed импорт, а не копировать upstream PowerShell/CLI команды вручную.",
        "",
        "## Usage",
        "",
        "```bash",
        f"{_imported_repo_script(skill_name)} --help",
        f"{_imported_repo_script(skill_name)} ...",
        "```",
        "",
        "## Adaptation",
        "",
        f"- Vendored upstream source: `{_vendor_reference(entry)}`",
        f"- Runtime kind: `{entry['runtime_kind']}`",
    ]
    for note in notes:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Repo-owned dispatcher является source of truth для вызова skill в этом шаблоне.",
            "- Vendored upstream `SKILL.md` остаётся источником intent/examples, но не публичным execution contract.",
            "",
        ]
    )
    return "\n".join(lines)


def _mapping_row(intent: str, codex_skill: str, claude_skill: str, repo_entrypoint: str, extra: str | None = None) -> str:
    details = extra or ""
    return f"| {intent} | `{codex_skill}` | `{claude_skill}` | `{repo_entrypoint}` | {details} |"


def _render_agents_readme(native_codex: list[dict[str, str]], native_claude: list[dict[str, str]], imported_entries: list[dict[str, object]], upstream: dict[str, str]) -> str:
    claude_names = {entry["name"] for entry in native_claude}
    lines = [
        "# Project-Scoped Codex Skills",
        "",
        "Эти skills являются Codex-discoverable фасадом над versioned repo scripts.",
        "Claude-facing equivalents лежат в [.claude/skills/README.md](../../.claude/skills/README.md).",
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
            "- Imported compatibility pack не заменяет native runner-agnostic skills: при совпадении intent предпочитайте native workflow шаблона.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_claude_readme(native_codex: list[dict[str, str]], native_claude: list[dict[str, str]], imported_entries: list[dict[str, object]], upstream: dict[str, str]) -> str:
    codex_names = {entry["name"] for entry in native_codex}
    lines = [
        "# Project-Scoped 1C Skills",
        "",
        "Эти skills являются project-scoped фасадом над versioned repo scripts.",
        "Codex-facing equivalents лежат в [.agents/skills/README.md](../../.agents/skills/README.md).",
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
    }
    if rel in excluded_exact:
        return False
    excluded_prefixes = (
        "openspec/",
        ".claude/commands/",
        "tooling/",
        ".githooks/",
        "scripts/release/",
    )
    if rel.startswith(excluded_prefixes):
        return False
    if rel.startswith("src/"):
        if rel in {"src/AGENTS.md", "src/README.md"}:
            return True
        return rel.startswith("src/epf/TemplateXUnitHarness/")
    return True


def _refresh_overlay_manifest() -> None:
    tracked = run_git(["ls-files", "--cached", "--others", "--exclude-standard"], cwd=PROJECT_ROOT, check=True).stdout.splitlines()
    entries = sorted({rel.strip() for rel in tracked if rel.strip() and _is_overlay_managed(rel.strip())})
    write_text(OVERLAY_MANIFEST, "\n".join(entries) + "\n")


def _remove_previous_generated_surfaces(previous_names: list[str]) -> None:
    for skills_root in (repo_path(".agents", "skills"), repo_path(".claude", "skills")):
        for skill_name in previous_names:
            target = skills_root / skill_name
            if target.is_dir():
                shutil.rmtree(target)


def _write_generated_surfaces(imported_entries: list[dict[str, object]], upstream: dict[str, str], previous_names: list[str]) -> None:
    imported_names = {str(entry["name"]) for entry in imported_entries}
    _remove_previous_generated_surfaces(previous_names)

    agents_root = repo_path(".agents", "skills")
    claude_root = repo_path(".claude", "skills")
    ensure_dir(agents_root)
    ensure_dir(claude_root)

    native_codex = _existing_skill_docs(agents_root, imported_names)
    native_claude = _existing_skill_docs(claude_root, imported_names)

    for entry in imported_entries:
        skill_name = str(entry["name"])
        write_text(agents_root / skill_name / "SKILL.md", _render_agents_skill(entry))
        write_text(claude_root / skill_name / "SKILL.md", _render_claude_skill(entry))

    write_text(agents_root / "README.md", _render_agents_readme(native_codex, native_claude, imported_entries, upstream))
    write_text(claude_root / "README.md", _render_claude_readme(native_codex, native_claude, imported_entries, upstream))


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
    lines.append("Use the vendored upstream material as guidance; this imported skill is reference-only in the runner-agnostic template.")
    return "\n".join(lines) + "\n"


def run_imported_skill(skill_name: str, args: list[str]) -> int:
    entry = _find_entry(skill_name)
    runtime_kind = str(entry.get("runtime_kind") or "")
    if runtime_kind == "native-alias":
        return _run_native_alias(entry, args)
    if runtime_kind == "python":
        return _run_python_helper(entry, args)
    if runtime_kind == "node":
        return _run_node_helper(entry, args)
    print(_render_reference(entry), end="")
    return 0
