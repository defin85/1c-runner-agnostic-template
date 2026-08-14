from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .common import die, project_root, run_process
from .context import export_context, is_source_repo, verify_traceability
from .imported_skills import _is_overlay_managed, imported_skill_readiness_payload


def _frontmatter_lines(text: str) -> list[tuple[int, str]]:
    if not text.startswith("---\n"):
        return []
    lines = text.splitlines()
    try:
        end_index = lines.index("---", 1)
    except ValueError:
        return []
    return list(enumerate(lines[1:end_index], start=2))


def _is_unsafe_plain_yaml_scalar(value: str) -> bool:
    stripped = value.strip()
    if not stripped or stripped in {">", "|", "[]"}:
        return False
    if stripped[0] in {'"', "'"}:
        return False
    return ": " in stripped


def _skill_frontmatter_errors(skill_file: Path, text: str) -> list[str]:
    errors: list[str] = []
    patterns = (
        ("description", re.compile(r"^description:\s*(.*)$")),
        ("argument-hint", re.compile(r"^argument-hint:\s*(.*)$")),
        ("short-description", re.compile(r"^  short-description:\s*(.*)$")),
    )
    for line_number, line in _frontmatter_lines(text):
        for field_name, pattern in patterns:
            match = pattern.match(line)
            if not match:
                continue
            if _is_unsafe_plain_yaml_scalar(match.group(1)):
                errors.append(f"unsafe unquoted YAML scalar in {field_name}: {skill_file}:{line_number}")
    return errors


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
            if not skill_file.parent.name.startswith("openspec-") and not re.search(r"^Repo script: `\./scripts/.+`$", text, re.MULTILINE):
                print(f"missing repo script binding: {skill_file}", file=os.sys.stderr)
                status = 1
            if re.search(r"powershell\.exe -File|/opt/1cv8|1cv8 DESIGNER|rac ", text):
                print(f"skill embeds runtime implementation details: {skill_file}", file=os.sys.stderr)
                status = 1
            for error in _skill_frontmatter_errors(skill_file, text):
                print(error, file=os.sys.stderr)
                status = 1
    return status


def check_overlay_manifest(root: Path | None = None) -> int:
    repo_root = root or project_root()
    manifest = repo_root / "automation" / "context" / "template-managed-paths.txt"
    if not manifest.is_file():
        die(f"overlay manifest is missing: {manifest}")
    def is_managed_src_scaffold(path: str) -> bool:
        return (
            path.startswith("src/epf/TemplateXUnitHarness/")
            or path in {"src/epf/AGENT_TEMPLATES.md", "src/cfe/AGENT_TEMPLATES.md"}
            or path.startswith("src/epf/_templates/")
            or path.startswith("src/cfe/_templates/")
        )
    if not (repo_root / "automation" / "context" / "template-source-project-map.md").is_file():
        forbidden_prefixes = ("openspec/", "tooling/", "analysis/testing/")
        forbidden_exact = {"AGENTS.md", "README.md", "copier.yml"}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line in forbidden_exact or any(line.startswith(prefix) for prefix in forbidden_prefixes):
                print("generated-project overlay manifest must not manage source-only or project-owned paths", file=os.sys.stderr)
                return 1
            if line.startswith("src/") and line not in {"src/AGENTS.md", "src/README.md"} and not is_managed_src_scaffold(line):
                print("generated-project overlay manifest must not manage source-only or project-owned paths", file=os.sys.stderr)
                return 1
        return 0
    tracked = run_process(["git", "-c", "core.quotePath=false", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo_root, check=True).stdout.splitlines()
    expected = [entry for entry in tracked if _is_overlay_managed(entry)]
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
    if not is_source_repo(repo_root):
        required_paths.append(repo_root / "automation" / "context" / "recommended-skills.generated.md")
    status = 0
    for path in required_paths:
        if not path.exists():
            print(f"missing agent-facing path: {path.relative_to(repo_root).as_posix()}", file=os.sys.stderr)
            status = 1
    if export_context("--check", repo_root) != 0:
        status = 1
    if not is_source_repo(repo_root):
        if validate_runtime_support_matrix(repo_root) != 0:
            status = 1
        tree_file = repo_root / "automation" / "context" / "source-tree.generated.txt"
        metadata_file = repo_root / "automation" / "context" / "metadata-index.generated.json"
        for line in tree_file.read_text(encoding="utf-8").splitlines():
            rel = line.strip()
            if rel in {
                "./env/local.json",
                "./env/wsl.json",
                "./env/ci.json",
                "./env/windows-executor.json",
                "./env/.local",
            } or rel.startswith("./env/.local/"):
                print(f"local-private path leaked into generated context: {rel.removeprefix('./')}", file=os.sys.stderr)
                status = 1
            if rel.startswith("./.codex/") and rel not in {
                "./.codex/.gitkeep",
                "./.codex/README.md",
                "./.codex/config.toml",
            }:
                print(f"local-private path leaked into generated context: {rel.removeprefix('./')}", file=os.sys.stderr)
                status = 1
        metadata_text = metadata_file.read_text(encoding="utf-8")
        if re.search(r'"env/(local|wsl|ci|windows-executor)\.json"|env/\.local/', metadata_text):
            print("generated metadata leaked local-private runtime profile paths", file=os.sys.stderr)
            status = 1
    return status


def validate_runtime_support_matrix(root: Path) -> int:
    json_path = root / "automation" / "context" / "runtime-support-matrix.json"
    markdown_path = root / "automation" / "context" / "runtime-support-matrix.md"
    if not json_path.is_file() or not markdown_path.is_file():
        return 1
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    allowed_statuses = set(payload.get("statuses") or [])
    now = datetime.now(timezone.utc)
    for contour in payload.get("contours") or []:
        contour_id = str(contour.get("id") or "<missing>")
        platforms = contour.get("platforms") or {}
        for platform in ("linux", "windows"):
            support = platforms.get(platform)
            pair = f"{contour_id}/{platform}"
            if not isinstance(support, dict):
                print(f"runtime support matrix is missing capability/platform entry: {pair}", file=os.sys.stderr)
                return 1
            status = support.get("status")
            evidence_class = support.get("evidenceClass")
            if status not in allowed_statuses or evidence_class not in {"contract-only", "contract-plus-live"}:
                print(f"runtime support matrix has invalid status/evidence class: {pair}", file=os.sys.stderr)
                return 1
            if status == "supported" and evidence_class == "contract-plus-live":
                evidence = support.get("evidence")
                if not isinstance(evidence, dict) or not all(evidence.get(key) for key in ("fingerprint", "timestamp", "expiresAt")):
                    print(f"runtime support matrix lacks current live evidence: {pair}", file=os.sys.stderr)
                    return 1
                try:
                    expires_at = datetime.fromisoformat(str(evidence["expiresAt"]).replace("Z", "+00:00"))
                except ValueError:
                    print(f"runtime support matrix has invalid evidence expiry: {pair}", file=os.sys.stderr)
                    return 1
                if expires_at <= now:
                    print(f"runtime support matrix live evidence expired: {pair}", file=os.sys.stderr)
                    return 1
    from .template_tools import _runtime_support_matrix_md

    actual_markdown = markdown_path.read_text(encoding="utf-8")
    expected_markdown = _runtime_support_matrix_md(payload)
    if actual_markdown != expected_markdown:
        for contour in payload.get("contours") or []:
            for platform in ("linux", "windows"):
                prefix = f"| `{contour['id']}` | `{platform}` |"
                expected_row = next(line for line in expected_markdown.splitlines() if line.startswith(prefix))
                if expected_row not in actual_markdown.splitlines():
                    print(f"runtime support matrix Markdown is stale: {contour['id']}/{platform}", file=os.sys.stderr)
                    return 1
        print("runtime support matrix Markdown has unexpected stale content", file=os.sys.stderr)
        return 1
    return 0


def check_imported_skill_readiness_contract(root: Path | None = None) -> int:
    repo_root = root or project_root()
    payload = imported_skill_readiness_payload()
    if payload.get("canonicalTarget") != "make imported-skills-readiness":
        print("unexpected imported-skill readiness target", file=os.sys.stderr)
        return 1
    representative = dict(payload.get("representative") or {})
    required = {
        "python": "cf-edit",
        "node": "web-test",
        "reference": "form-patterns",
        "nativeAlias": "db-create",
    }
    for key, skill_name in required.items():
        item = dict(representative.get(key) or {})
        if str(item.get("representative_skill") or "") != skill_name:
            print(f"missing representative readiness entry: {key}", file=os.sys.stderr)
            return 1
        if not str(item.get("entrypoint") or "").startswith("./scripts/skills/run-imported-skill.sh "):
            print(f"invalid readiness entrypoint for {key}", file=os.sys.stderr)
            return 1
        if not item.get("ready") and not item.get("bootstrap_commands"):
            print(f"missing bootstrap commands for unready imported runtime: {key}", file=os.sys.stderr)
            return 1
    if not (repo_root / "scripts" / "skills" / "run-imported-skill.sh").is_file():
        print("missing imported-skill dispatcher", file=os.sys.stderr)
        return 1
    return 0


def _imported_skill_readiness_status_lines() -> list[str]:
    payload = imported_skill_readiness_payload()
    representative = dict(payload.get("representative") or {})
    lines = [
        f"Imported skill readiness target: {payload['canonicalTarget']}",
        f"Imported skill readiness command: {payload['canonicalCommand']}",
    ]
    for key in ("python", "node", "reference", "nativeAlias"):
        item = dict(representative.get(key) or {})
        runtime_kind = str(item.get("runtime_kind") or key)
        skill_name = str(item.get("representative_skill") or key)
        if item.get("ready"):
            lines.append(f"Imported skill runtime `{runtime_kind}` (`{skill_name}`): ready")
            continue
        missing = ", ".join(str(dep) for dep in item.get("missing_dependencies") or [])
        lines.append(f"Imported skill runtime `{runtime_kind}` (`{skill_name}`): missing {missing}")
    return lines


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
                "Generated-project support-matrix templates: automation/context/templates/generated-project-runtime-support-matrix.md, automation/context/templates/generated-project-runtime-support-matrix.json",
                "Generated-project productivity scaffolds: automation/context/templates/generated-project-architecture-map.md, automation/context/templates/generated-project-operator-local-runbook.md, automation/context/templates/generated-project-runtime-quickstart.md, automation/context/templates/generated-project-project-delta-hints.json, automation/context/templates/generated-project-project-delta-hotspots.md, automation/context/templates/generated-project-recommended-skills.md",
                "Generated-project work-item scaffolds: automation/context/templates/generated-project-work-items-readme.md, automation/context/templates/generated-project-work-items-template.md",
                "Execution plan starters: docs/exec-plans/TEMPLATE.md, docs/exec-plans/EXAMPLE.md",
                "",
                "Codex controls:",
                "- /plan -> execution matrix for long-running work",
                "- /compact -> reduce session size before handoff",
                "- /review -> focused review pass",
                "- /ps -> inspect background shell work",
                "- /mcp -> inspect available MCP tools",
                "",
                "Next commands:",
                "- make agent-verify",
                "- openspec list",
                "",
            ]
        )
    support_matrix = repo_root / "automation" / "context" / "runtime-support-matrix.json"
    required_generated_paths = [
        repo_root / "automation" / "context" / "project-map.md",
        repo_root / "docs" / "agent" / "architecture-map.md",
        repo_root / "docs" / "agent" / "codex-workflows.md",
        repo_root / "docs" / "agent" / "operator-local-runbook.md",
        repo_root / "docs" / "agent" / "runtime-quickstart.md",
        repo_root / "automation" / "context" / "runtime-support-matrix.json",
        repo_root / "automation" / "context" / "runtime-support-matrix.md",
        repo_root / "automation" / "context" / "recommended-skills.generated.md",
        repo_root / "automation" / "context" / "project-delta-hints.json",
        repo_root / "automation" / "context" / "project-delta-hotspots.generated.md",
        repo_root / "docs" / "exec-plans" / "TEMPLATE.md",
        repo_root / "docs" / "work-items" / "README.md",
        repo_root / "docs" / "work-items" / "TEMPLATE.md",
    ]
    for path in required_generated_paths:
        if not path.exists():
            die(f"generated-project onboarding path is missing: {path.relative_to(repo_root).as_posix()}")
    support_matrix_payload: dict[str, object] = {}
    extension_line = "not declared"
    if support_matrix.is_file():
        support_matrix_payload = json.loads(support_matrix.read_text(encoding="utf-8"))
        extension = support_matrix_payload.get("projectSpecificBaselineExtension")
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
        "Recommended skills: automation/context/recommended-skills.generated.md",
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
            "- make imported-skills-readiness",
            "",
            "AI-readiness:",
        ]
    )
    lines.extend(f"- {line}" for line in _imported_skill_readiness_status_lines())
    lines.extend(["", "Runtime contour statuses:"])
    for contour in support_matrix_payload.get("contours") or []:
        if not isinstance(contour, dict):
            continue
        contour_id = str(contour.get("id") or "")
        contour_status = str(contour.get("status") or "unknown")
        provenance = str(contour.get("profileProvenance") or "unknown")
        if contour_id:
            lines.append(f"- {contour_id}: {contour_status} ({provenance})")
    lines.extend(
        [
            "",
            "Codex controls:",
            "- /plan -> зафиксировать execution matrix до большого multi-session change",
            "- /compact -> свернуть длинную сессию перед handoff",
            "- /review -> попросить focused review pass по текущему worktree",
            "- /ps -> посмотреть фоновые shell/runtime contours",
            "- /mcp -> подтвердить доступные MCP tools",
            "",
            "Planning matrix:",
            "- OpenSpec -> use for new capability, breaking change, architecture shift, or ambiguous intent",
            "- docs/exec-plans/TEMPLATE.md -> copy-ready starter for long-running, multi-session, or cross-cutting work",
            "- docs/work-items/README.md -> task-local supporting artifacts workspace next to the exec-plan",
            "",
            "Follow-up routers:",
            "- docs/agent/review.md",
            "- docs/agent/codex-workflows.md",
            "- docs/agent/operator-local-runbook.md",
            "- env/README.md",
            "- .agents/skills/README.md",
            "- .codex/README.md",
            "- docs/exec-plans/README.md",
            "- docs/work-items/README.md",
            "- docs/template-maintenance.md",
            "",
            "Next commands:",
            "- make agent-verify",
            "- make export-context-check",
            "- make imported-skills-readiness",
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
        check_imported_skill_readiness_contract,
    ):
        result = check(repo_root)
        if result != 0:
            return result
    return 0
