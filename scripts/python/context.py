from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .common import canonical_path, die, ensure_dir, project_root, write_text


def is_source_repo(root: Path | None = None) -> bool:
    repo_root = root or project_root()
    required = [
        repo_root / "openspec" / "specs" / "agent-runtime-toolkit" / "spec.md",
        repo_root / "openspec" / "specs" / "project-scoped-skills" / "spec.md",
        repo_root / "openspec" / "specs" / "template-ci-contours" / "spec.md",
    ]
    return all(path.is_file() for path in required)


def _repo_rel(path: Path, root: Path) -> str:
    return f"./{path.relative_to(root).as_posix()}"


def _iter_files(root: Path, rel: str) -> list[Path]:
    base = root / rel
    if base.is_file():
        return [base]
    if not base.is_dir():
        return []
    return sorted(path for path in base.rglob("*") if path.is_file())


def render_source_tree(root: Path) -> str:
    roots = [
        "AGENTS.md",
        "README.md",
        "Makefile",
        "copier.yml",
        ".agents",
        ".claude",
        ".codex",
        ".github",
        "automation",
        "docs",
        "env",
        "features",
        "openspec",
        "scripts",
        "src",
        "tests",
    ]
    entries = {"."}
    for rel in roots:
        for path in _iter_files(root, rel):
            parent = path.parent
            while parent != root:
                rel_parent = _repo_rel(parent, root)
                if rel_parent.count("/") <= 3:
                    entries.add(rel_parent)
                parent = parent.parent
    entries.update({"./.githooks", "./src/cf", "./tooling"})
    return "# Template Source Tree\n\n" + "\n".join(sorted(entries)) + "\n"


def render_source_files(root: Path) -> str:
    roots = [
        "AGENTS.md",
        "README.md",
        "Makefile",
        "copier.yml",
        ".agents",
        ".claude",
        ".codex",
        ".github",
        "automation",
        "docs",
        "env",
        "features",
        "openspec",
        "scripts",
        "src",
        "tests",
    ]
    files: list[str] = []
    for rel in roots:
        files.extend(_repo_rel(path, root) for path in _iter_files(root, rel))
    return "# Template Source Files\n\n" + "\n".join(sorted(set(files))) + "\n"


def _is_generated_private(rel: str) -> bool:
    return rel in {
        "./env/local.json",
        "./env/wsl.json",
        "./env/ci.json",
        "./env/windows-executor.json",
        "./env/windows-local.json",
    } or rel.startswith("./env/.local/")


def render_generated_tree(root: Path) -> str:
    ignored = {
        ".git",
        ".beads",
        ".agent-browser",
    }
    lines = ["# Generated Project Tree", ""]
    for path in sorted(root.rglob("*")):
        rel = _repo_rel(path, root)
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        if rel in {
            "./automation/context/source-tree.generated.txt",
            "./automation/context/metadata-index.generated.json",
            "./automation/context/hotspots-summary.generated.md",
            "./automation/context/project-delta-hotspots.generated.md",
        }:
            continue
        if _is_generated_private(rel):
            continue
        if rel.startswith("./.codex/") and rel not in {
            "./.codex/.gitkeep",
            "./.codex/README.md",
            "./.codex/config.toml",
        }:
            continue
        lines.append(rel)
    return "\n".join(lines) + "\n"


def _list_top_level(root: Path, rel: str) -> list[str]:
    base = root / rel
    if not base.is_dir():
        return []
    return sorted(child.name for child in base.iterdir())


def _list_inventory(root: Path, rel: str) -> list[str]:
    base = root / rel
    if not base.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in base.iterdir())


def _configuration_name(root: Path) -> str:
    config = root / "src" / "cf" / "Configuration.xml"
    if not config.is_file():
        return ""
    text = config.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'name="([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"<Name>([^<]+)</Name>", text)
    return match.group(1) if match else ""


def _configuration_uuid(root: Path) -> str:
    config = root / "src" / "cf" / "Configuration.xml"
    if not config.is_file():
        return ""
    text = config.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'uuid="([^"]+)"', text)
    return match.group(1) if match else ""


def render_generated_metadata(root: Path) -> str:
    payload: dict[str, Any] = {
        "repositoryRole": "generated-project",
        "inventoryRole": "generated-derived",
        "authoritativeDocs": {
            "generatedProjectIndex": "docs/agent/generated-project-index.md",
            "projectMap": "automation/context/project-map.md",
            "architectureMap": "docs/agent/architecture-map.md",
            "codexWorkflows": "docs/agent/codex-workflows.md",
            "operatorLocalRunbook": "docs/agent/operator-local-runbook.md",
            "runtimeQuickstart": "docs/agent/runtime-quickstart.md",
            "workItemsGuide": "docs/work-items/README.md",
            "workItemsTemplate": "docs/work-items/TEMPLATE.md",
            "verification": "docs/agent/generated-project-verification.md",
            "review": "docs/agent/review.md",
            "envReadme": "env/README.md",
            "projectDeltaHints": "automation/context/project-delta-hints.json",
            "runtimeProfilePolicy": "automation/context/runtime-profile-policy.json",
            "runtimeSupportMatrixJson": "automation/context/runtime-support-matrix.json",
            "runtimeSupportMatrixMarkdown": "automation/context/runtime-support-matrix.md",
            "projectDeltaHotspots": "automation/context/project-delta-hotspots.generated.md",
            "hotspotsSummary": "automation/context/hotspots-summary.generated.md",
            "skills": ".agents/skills/README.md",
            "codexGuide": ".codex/README.md",
            "executionPlans": "docs/exec-plans/README.md",
            "templateMaintenance": "docs/template-maintenance.md",
        },
        "configuration": {
            "xmlPath": "src/cf/Configuration.xml",
            "present": (root / "src" / "cf" / "Configuration.xml").is_file(),
            "name": _configuration_name(root),
            "uuid": _configuration_uuid(root),
        },
        "sourceRoots": {
            "configuration": "src/cf",
            "extensions": "src/cfe",
            "externalProcessors": "src/epf",
            "reports": "src/erf",
        },
        "entrypointInventory": {
            "configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"],
            "httpServices": _list_inventory(root, "src/cf/HTTPServices"),
            "webServices": _list_inventory(root, "src/cf/WebServices"),
            "scheduledJobs": _list_inventory(root, "src/cf/ScheduledJobs"),
            "commonModules": _list_inventory(root, "src/cf/CommonModules"),
            "subsystems": _list_inventory(root, "src/cf/Subsystems"),
            "extensions": _list_inventory(root, "src/cfe"),
            "externalProcessors": _list_inventory(root, "src/epf"),
            "reports": _list_inventory(root, "src/erf"),
        },
        "topLevelEntries": {
            "cf": _list_top_level(root, "src/cf"),
            "cfe": _list_top_level(root, "src/cfe"),
            "epf": _list_top_level(root, "src/epf"),
            "erf": _list_top_level(root, "src/erf"),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _count_inventory(root: Path, rel: str) -> int:
    return len(_list_inventory(root, rel))


def render_generated_project_delta_hotspots(root: Path, metadata_json: str) -> str:
    hints_path = root / "automation" / "context" / "project-delta-hints.json"
    if hints_path.is_file():
        hints = json.loads(hints_path.read_text(encoding="utf-8"))
    else:
        hints = {"selectors": {"pathPrefixes": [], "pathKeywords": []}, "representativePaths": []}
    tree_entries = render_generated_tree(root).splitlines()[2:]
    prefixes = [str(item) for item in hints.get("selectors", {}).get("pathPrefixes", [])]
    keywords = [str(item) for item in hints.get("selectors", {}).get("pathKeywords", [])]
    matches: list[str] = []
    for entry in tree_entries:
        plain = entry[2:] if entry.startswith("./") else entry
        if any(plain.startswith(prefix) for prefix in prefixes) or any(keyword in plain for keyword in keywords):
            matches.append(plain)
    lines = [
        "# Generated Project-Delta Hotspots",
        "",
        "Этот файл является generated-derived bridge между curated project-owned truth и raw inventory.",
        "Source selectors живут в `automation/context/project-delta-hints.json`, а deeper narrowing при необходимости идёт дальше в `automation/context/hotspots-summary.generated.md` и `automation/context/metadata-index.generated.json`.",
        "",
        "## Declared Selectors",
        "",
        "### Path Prefixes",
        "",
    ]
    lines.extend([f"- `{value}`" for value in prefixes] or ["- none"])
    lines.extend(["", "### Path Keywords", ""])
    lines.extend([f"- `{value}`" for value in keywords] or ["- none"])
    lines.extend(["", "### Representative Paths", ""])
    lines.extend([f"- `{value}`" for value in hints.get("representativePaths", [])] or ["- none"])
    lines.extend(["", "## Matching Hotspots", ""])
    lines.extend([f"- `{value}`" for value in matches[:20]] or ["No project-delta selectors are declared yet." if not (prefixes or keywords) else "Selectors are declared, but they do not currently match generated tree entries."])
    lines.extend(
        [
            "",
            "## Follow-Up Routers",
            "",
            "- Curated project truth: `automation/context/project-map.md`",
            "- Project-owned code map: `docs/agent/architecture-map.md`",
            "- Runtime quick reference: `docs/agent/runtime-quickstart.md`",
            "- Raw inventory: `automation/context/metadata-index.generated.json`",
            "- Generic summary-first map: `automation/context/hotspots-summary.generated.md`",
        ]
    )
    return "\n".join(lines) + "\n"


def render_generated_hotspots_summary(root: Path, metadata_json: str, tree_text: str) -> str:
    config_name = _configuration_name(root) or "(unknown)"
    config_uuid = _configuration_uuid(root) or "unknown"
    lines = [
        "# Generated Hotspots Summary",
        "",
        "Этот файл является generated-derived summary-first картой для первого часа работы агента.",
        "Raw inventory остаётся в `automation/context/metadata-index.generated.json`, а следующий curated слой живёт в `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/operator-local-runbook.md` и `docs/agent/runtime-quickstart.md`.",
        "Если project-owned selectors уже описаны, сначала откройте `automation/context/project-delta-hotspots.generated.md` как bridge к project-specific customization layer.",
        "",
        "## Identity",
        "",
        "- Repository role: `generated-project`",
        f"- Configuration name: `{config_name}`",
        f"- Configuration UUID: `{config_uuid}`",
        f"- Configuration XML: `{'present' if (root / 'src/cf/Configuration.xml').is_file() else 'missing'}`",
        "",
        "## Freshness",
        "",
        "- Refresh command: `./scripts/llm/export-context.sh --write`",
        "- Check command: `./scripts/llm/export-context.sh --check`",
        "",
        "## High-Signal Counts",
        "",
        "| Area | Count |",
        "| --- | ---: |",
        f"| HTTP services | {_count_inventory(root, 'src/cf/HTTPServices')} |",
        f"| Web services | {_count_inventory(root, 'src/cf/WebServices')} |",
        f"| Scheduled jobs | {_count_inventory(root, 'src/cf/ScheduledJobs')} |",
        f"| Common modules | {_count_inventory(root, 'src/cf/CommonModules')} |",
        f"| Subsystems | {_count_inventory(root, 'src/cf/Subsystems')} |",
        f"| Extensions | {_count_inventory(root, 'src/cfe')} |",
        f"| External processors | {_count_inventory(root, 'src/epf')} |",
        f"| Reports | {_count_inventory(root, 'src/erf')} |",
        "",
        "## Task-to-Path Routing",
        "",
        "- Integration and service edges -> `src/cf/HTTPServices`, `src/cf/WebServices`",
        "- Background and scheduled execution -> `src/cf/ScheduledJobs`",
        "- Shared business logic and reusable helpers -> `src/cf/CommonModules`",
        "- Navigation and product surface map -> `src/cf/Subsystems`",
        "- Extension-owned behavior -> `src/cfe`",
        "- External processors and reports -> `src/epf`, `src/erf`",
        "",
        "## Follow-Up Routers",
        "",
        "- Curated project truth: `automation/context/project-map.md`",
        "- Project-owned code map: `docs/agent/architecture-map.md`",
        "- Operator-local runtime bridge: `docs/agent/operator-local-runbook.md`",
        "- Project-specific runtime digest: `docs/agent/runtime-quickstart.md`",
        "- Project-specific delta bridge: `automation/context/project-delta-hotspots.generated.md`",
        "- Runtime profile policy: `automation/context/runtime-profile-policy.json`",
        "- Runtime support matrix: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`",
        "- Long-running companion workspace: `docs/work-items/README.md`",
        "- Raw inventory for deeper narrowing: `automation/context/metadata-index.generated.json`",
        "- Verification matrix: `docs/agent/generated-project-verification.md`",
        "- Repeatable workflows and Codex guide: `.agents/skills/README.md`, `.codex/README.md`",
        "- Long-running plans: `docs/exec-plans/README.md`",
    ]
    return "\n".join(lines) + "\n"


def export_context(mode: str, root: Path | None = None) -> int:
    repo_root = root or project_root()
    context_dir = ensure_dir(repo_root / "automation" / "context")
    if mode not in {"--help", "--preview", "--check", "--write"}:
        die(f"unknown mode: {mode}")
    if mode == "--help":
        return 0
    targets: list[tuple[Path, str]] = []
    if is_source_repo(repo_root):
        targets = [
            (context_dir / "template-source-tree.txt", render_source_tree(repo_root)),
            (context_dir / "template-source-source-files.txt", render_source_files(repo_root)),
        ]
    else:
        tree_text = render_generated_tree(repo_root)
        metadata_json = render_generated_metadata(repo_root)
        targets = [
            (context_dir / "source-tree.generated.txt", tree_text),
            (context_dir / "metadata-index.generated.json", metadata_json),
            (context_dir / "project-delta-hotspots.generated.md", render_generated_project_delta_hotspots(repo_root, metadata_json)),
            (context_dir / "hotspots-summary.generated.md", render_generated_hotspots_summary(repo_root, metadata_json, tree_text)),
        ]
    if mode == "--preview":
        for path, content in targets:
            print(f"=== {path.relative_to(repo_root).as_posix()} ===")
            print(content)
        return 0
    if mode == "--check":
        status = 0
        for path, content in targets:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                print(f"stale context file: {path}", file=os.sys.stderr)
                status = 1
        return status
    for path, content in targets:
        write_text(path, content)
    return 0


def verify_traceability(root: Path | None = None) -> int:
    repo_root = root or project_root()
    changes_dir = repo_root / "openspec" / "changes"
    if not changes_dir.is_dir():
        print(f"error: changes directory not found: {changes_dir}", file=os.sys.stderr)
        print("hint: run openspec init in the project root", file=os.sys.stderr)
        return 1
    status = 0
    for change_dir in sorted(path for path in changes_dir.iterdir() if path.is_dir() and path.name != "archive"):
        if not (change_dir / "proposal.md").is_file():
            print(f"missing proposal.md: {change_dir}", file=os.sys.stderr)
            status = 1
        specs_root = change_dir / "specs"
        spec_count = len(list(specs_root.glob("*/*/spec.md"))) + len(list(specs_root.glob("*/spec.md")))
        if spec_count == 0:
            print(f"missing capability spec delta under specs/*/spec.md: {change_dir}", file=os.sys.stderr)
            status = 1
        if not (change_dir / "tasks.md").is_file():
            print(f"missing tasks.md: {change_dir}", file=os.sys.stderr)
            status = 1
        if not (change_dir / "traceability.md").is_file():
            print(f"missing traceability.md: {change_dir}", file=os.sys.stderr)
            status = 1
    return status
