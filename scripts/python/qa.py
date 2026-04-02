from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .common import die, project_root, run_process
from .context import export_context, is_source_repo, verify_traceability


def analyze_bsl() -> int:
    jar = os.environ.get("BSL_LANGUAGE_SERVER_JAR", "")
    if not jar:
        die("required env var is not set: BSL_LANGUAGE_SERVER_JAR")
    root = project_root()
    src_dir = os.environ.get("BSL_SRC_DIR", str(root / "src" / "cf"))
    output_dir = os.environ.get("BSL_REPORT_DIR", str(root / "reports" / "bsl-analysis"))
    config_path = os.environ.get("BSL_LANGUAGE_SERVER_CONFIG", "")
    xmx = os.environ.get("BSL_LS_XMX", "2g")
    cmd = ["java", f"-Xmx{xmx}", "-jar", jar]
    if config_path:
        cmd.extend(["--configuration", config_path])
    cmd.extend(["--analyze", "--srcDir", src_dir, "--outputDir", output_dir, "--reporter", "json", "--reporter", "junit"])
    return run_process(cmd, cwd=root, check=False, capture_output=False).returncode


def format_bsl() -> int:
    jar = os.environ.get("BSL_LANGUAGE_SERVER_JAR", "")
    if not jar:
        die("required env var is not set: BSL_LANGUAGE_SERVER_JAR")
    root = project_root()
    src_dir = os.environ.get("BSL_FORMAT_SRC", str(root / "src" / "cf"))
    xmx = os.environ.get("BSL_LS_XMX", "2g")
    cmd = ["java", f"-Xmx{xmx}", "-jar", jar, "--format", "--src", src_dir]
    return run_process(cmd, cwd=root, check=False, capture_output=False).returncode


def check_skill_bindings(root: Path | None = None) -> int:
    repo_root = root or project_root()
    status = 0
    for rel in (".agents/skills", ".claude/skills"):
        skills_dir = repo_root / rel
        if not skills_dir.is_dir():
            die(f"skills directory not found: {skills_dir}")
        if not (skills_dir / "README.md").is_file():
            print(f"missing skills README: {skills_dir / 'README.md'}", file=os.sys.stderr)
            status = 1
        for skill_file in sorted(skills_dir.glob("*/*/SKILL.md")) + sorted(skills_dir.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            if not re.search(r"^Repo script: `\./scripts/.+`$", text, re.MULTILINE):
                print(f"missing repo script binding: {skill_file}", file=os.sys.stderr)
                status = 1
            if re.search(r"powershell\.exe -File|/opt/1cv8|1cv8 DESIGNER|rac ", text):
                print(f"skill embeds runtime implementation details: {skill_file}", file=os.sys.stderr)
                status = 1
    return status


def check_overlay_manifest(root: Path | None = None) -> int:
    repo_root = root or project_root()
    manifest = repo_root / "automation" / "context" / "template-managed-paths.txt"
    if not manifest.is_file():
        die(f"overlay manifest is missing: {manifest}")
    if not (repo_root / "automation" / "context" / "template-source-project-map.md").is_file():
        forbidden_prefixes = ("openspec/", "tooling/")
        forbidden_exact = {"AGENTS.md", "README.md", "copier.yml"}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line in forbidden_exact or any(line.startswith(prefix) for prefix in forbidden_prefixes):
                print("generated-project overlay manifest must not manage source-only or project-owned paths", file=os.sys.stderr)
                return 1
            if line.startswith("src/") and line not in {"src/AGENTS.md", "src/README.md"} and not line.startswith("src/epf/TemplateXUnitHarness/"):
                print("generated-project overlay manifest must not manage source-only or project-owned paths", file=os.sys.stderr)
                return 1
        return 0
    tracked = run_process(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo_root, check=True).stdout.splitlines()
    expected: list[str] = []
    for entry in tracked:
        if entry == "[[[ _copier_conf.answers_file ]]]":
            continue
        if entry in {"AGENTS.md", "CLAUDE.md", "README.md", "copier.yml"}:
            continue
        if entry.startswith("openspec/") or entry.startswith(".claude/commands/") or entry.startswith("tooling/"):
            continue
        if entry in {
            "automation/context/template-source-metadata-index.json",
            "automation/context/template-source-project-map.md",
            "automation/context/template-source-source-files.txt",
            "automation/context/template-source-tree.txt",
            "automation/context/template-update-preserve-paths.txt",
            ".codex/config.toml",
        }:
            continue
        if entry.startswith(".githooks/") or entry.startswith("scripts/release/"):
            continue
        if entry == "tests/smoke/template-release-workflow.sh":
            continue
        if entry.startswith("docs/work-items/"):
            continue
        if entry.startswith("src/") and entry not in {"src/AGENTS.md", "src/README.md"} and not entry.startswith("src/epf/TemplateXUnitHarness/"):
            continue
        expected.append(entry)
    actual = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return 0 if sorted(set(expected)) == sorted(actual) else 1


def check_agent_docs(root: Path | None = None) -> int:
    repo_root = root or project_root()
    required_paths = [
        repo_root / "AGENTS.md",
        repo_root / "README.md",
        repo_root / "docs" / "agent" / ("index.md" if is_source_repo(repo_root) else "generated-project-index.md"),
        repo_root / "docs" / "template-maintenance.md",
        repo_root / "automation" / "context" / ("template-source-tree.txt" if is_source_repo(repo_root) else "source-tree.generated.txt"),
        repo_root / "automation" / "context" / ("template-source-source-files.txt" if is_source_repo(repo_root) else "metadata-index.generated.json"),
    ]
    status = 0
    for path in required_paths:
        if not path.exists():
            print(f"missing agent-facing path: {path.relative_to(repo_root).as_posix()}", file=os.sys.stderr)
            status = 1
    if export_context("--check", repo_root) != 0:
        status = 1
    return status


def codex_onboard(root: Path | None = None) -> str:
    repo_root = root or project_root()
    if is_source_repo(repo_root):
        return "\n".join(
            [
                "# Codex Onboard",
                "",
                "Repository role: template-source",
                "Canonical onboarding router: docs/agent/index.md",
                "Architecture guide: docs/agent/architecture.md",
                "Verification entrypoint: make agent-verify",
                "Generated-project router reference: docs/agent/generated-project-index.md",
                "Generated-project workflow guide: docs/agent/codex-workflows.md",
                "",
                "Next commands:",
                "- make agent-verify",
                "- openspec list",
                "- bd ready",
                "",
            ]
        )
    support_matrix = repo_root / "automation" / "context" / "runtime-support-matrix.json"
    extension_line = "not declared"
    if support_matrix.is_file():
        payload = json.loads(support_matrix.read_text(encoding="utf-8"))
        extension = payload.get("projectSpecificBaselineExtension")
        if extension:
            extension_line = f"{extension.get('id')} -> {extension.get('entrypoint')} ({extension.get('runbookPath')})"
    config_name = ""
    metadata = repo_root / "automation" / "context" / "metadata-index.generated.json"
    if metadata.is_file():
        config_name = json.loads(metadata.read_text(encoding="utf-8")).get("configuration", {}).get("name", "")
    lines = [
        "# Codex Onboard",
        "",
        "Repository role: generated-project",
        "Canonical onboarding router: docs/agent/generated-project-index.md",
        "Project map: automation/context/project-map.md",
        "Workflow guide: docs/agent/codex-workflows.md",
        "Architecture map: docs/agent/architecture-map.md",
        "Operator-local runbook: docs/agent/operator-local-runbook.md",
        "Runtime quick reference: docs/agent/runtime-quickstart.md",
        "Runtime support matrix (md): automation/context/runtime-support-matrix.md",
        "Runtime support matrix (json): automation/context/runtime-support-matrix.json",
        "Project-delta hints: automation/context/project-delta-hints.json",
        "Project-delta hotspots: automation/context/project-delta-hotspots.generated.md",
        "Summary-first map: automation/context/hotspots-summary.generated.md",
        "Raw inventory: automation/context/metadata-index.generated.json",
        "Exec-plan template: docs/exec-plans/TEMPLATE.md",
        "Work-items guide: docs/work-items/README.md",
        "Work-item template: docs/work-items/TEMPLATE.md",
        f"Project-specific baseline extension: {extension_line}",
    ]
    if config_name:
        lines.append(f"Configuration name: {config_name}")
    lines.extend(
        [
            "",
            "Safe-local first pass:",
            "- make codex-onboard",
            "- make agent-verify",
            "- make export-context-check",
            "",
            "Next commands:",
            "- make agent-verify",
            "- make export-context-check",
            "- bd ready",
            "",
        ]
    )
    return "\n".join(lines)


def agent_verify(root: Path | None = None) -> int:
    repo_root = root or project_root()
    openspec = shutil.which("openspec")
    if not openspec:
        die("command not found: openspec")
    status = run_process([openspec, "validate", "--all", "--strict", "--no-interactive"], cwd=repo_root, capture_output=False).returncode
    if status != 0:
        return status
    for check in (
        verify_traceability,
        check_skill_bindings,
        check_overlay_manifest,
        check_agent_docs,
    ):
        result = check(repo_root)
        if result != 0:
            return result
    return 0
