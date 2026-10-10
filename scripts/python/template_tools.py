from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .common import canonical_path, die, ensure_dir, project_root, run_git, run_process, write_json, write_text
from .context import export_context
from .project_extensions import copy_with_project_block, is_preserved, seed_missing_project_files

DEFAULT_TEMPLATE_GIT_URL = "https://github.com/defin85/1c-runner-agnostic-template.git"
MANIFEST_RELPATH = "automation/context/template-managed-paths.txt"
PRESERVE_RELPATH = "automation/context/template-update-preserve-paths.txt"
VERSION_RELPATH = ".template-overlay-version"
SOURCE_RELPATH = ".template-overlay-source"


def resolve_project_template(explicit: str = "", cwd: Path | None = None) -> str:
    if explicit:
        return explicit
    env_template = os.environ.get("ONEC_PROJECT_TEMPLATE", "")
    if env_template:
        return env_template
    repo_root = cwd or project_root()
    if (repo_root / "copier.yml").is_file() and (repo_root / MANIFEST_RELPATH).is_file():
        return str(repo_root)
    return DEFAULT_TEMPLATE_GIT_URL


def template_answers_value(root: Path, key: str, default: str | None = None) -> str:
    answers_file = root / ".copier-answers.yml"
    if not answers_file.is_file():
        die(f"answers file not found: {answers_file}")
    prefix = f"{key}:"
    for line in answers_file.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        return value
    if default is not None:
        return default
    die(f"answers file does not contain {key}: {answers_file}")


def _manifest_entries(path: Path) -> list[str]:
    if not path.is_file():
        return []
    result: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result.append(line)
    return result


def overlay_manifest_file(root: Path) -> Path:
    return root / MANIFEST_RELPATH


def overlay_preserve_manifest_file(root: Path) -> Path:
    return root / PRESERVE_RELPATH


def overlay_version_file(root: Path) -> Path:
    return root / VERSION_RELPATH


def overlay_source_file(root: Path) -> Path:
    return root / SOURCE_RELPATH


def sync_overlay_manifests(
    source_root: Path,
    target_root: Path,
    previous_manifest: Path,
    next_manifest: Path,
    preserve_manifest: Path | None = None,
    *,
    dry_run: bool = False,
) -> None:
    previous_entries = set(_manifest_entries(previous_manifest))
    next_entries = set(_manifest_entries(next_manifest))
    preserve_entries = set(_manifest_entries(preserve_manifest)) if preserve_manifest else set()
    for rel in sorted(previous_entries | next_entries):
        source_path = source_root / rel
        target_path = target_root / rel
        # Project-owned paths win over the managed manifest: overlay sync never writes or removes them.
        if is_preserved(rel, preserve_entries):
            continue
        if rel in next_entries:
            if not source_path.is_file():
                die(f"overlay entry is missing in source release: {rel}")
            if dry_run:
                print(f"sync {rel}")
                continue
            ensure_dir(target_path.parent)
            if not copy_with_project_block(source_path, target_path, rel):
                shutil.copy2(source_path, target_path)
            continue
        if dry_run:
            print(f"remove {rel}")
            continue
        if target_path.exists():
            target_path.unlink()


def bootstrap_template_ref_or_fallback(root: Path, template_source: Path | str) -> str:
    try:
        return template_answers_value(root, "_commit")
    except Exception:
        source_path = Path(str(template_source))
        if source_path.is_dir() and (source_path / ".git").exists():
            return run_git(["describe", "--tags", "--always"], cwd=source_path, check=True).stdout.strip()
        return "unknown"


def write_overlay_version(root: Path, version: str) -> None:
    write_text(overlay_version_file(root), version + "\n")


def write_overlay_source(root: Path, source: str) -> None:
    write_text(overlay_source_file(root), source + "\n")


def template_source_path(root: Path) -> str:
    try:
        return template_answers_value(root, "_src_path")
    except Exception:
        source_file = overlay_source_file(root)
        if source_file.is_file():
            source_lines = source_file.read_text(encoding="utf-8").splitlines()
            if source_lines:
                return source_lines[0]
        raise


README_ROUTER_START = "<!-- RUNNER_AGNOSTIC_PROJECT:START -->"
README_ROUTER_END = "<!-- RUNNER_AGNOSTIC_PROJECT:END -->"


def _generated_readme_router() -> str:
    return "\n".join(
        [
            README_ROUTER_START,
            "## Agent Entry Point",
            "",
            "Этот репозиторий является generated 1С-проектом, созданным на шаблоне `1c-runner-agnostic-template`.",
            "",
            "- Canonical onboarding router: [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).",
            "- Read-only first screen: `make codex-onboard` или `./make.ps1 codex-onboard`.",
            "- Curated project truth: [automation/context/project-map.md](automation/context/project-map.md).",
            "- Project-owned code map: [docs/agent/architecture-map.md](docs/agent/architecture-map.md).",
            "- Operator-local runtime bridge: [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md).",
            "- Project-specific runtime digest: [docs/agent/runtime-quickstart.md](docs/agent/runtime-quickstart.md).",
            "- Checked-in runtime support truth: [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md), [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json).",
            "- AI-ready skill routing: [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md), `make imported-skills-readiness`.",
            README_ROUTER_END,
        ]
    )


def _generated_readme(project_name: str, project_description: str) -> str:
    return (
        "\n".join(
            [
                _generated_readme_router(),
                "",
                f"# {project_name}",
                "",
                project_description or "1С-проект, созданный на шаблоне runner-agnostic monorepo.",
                "",
            ]
        )
        + "\n"
    )


def _refresh_generated_readme(readme: Path, project_name: str, project_description: str) -> None:
    """Replace only the template router block; project text below it stays as the project wrote it."""
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    is_source_overview = (
        "# 1c-runner-agnostic-template" in text and "docs/agent/index.md" in text and README_ROUTER_START not in text
    )
    if not text.strip() or is_source_overview:
        write_text(readme, _generated_readme(project_name, project_description))
        return
    kept: list[str] = []
    inside = False
    for line in text.splitlines():
        if line == README_ROUTER_START:
            inside = True
        elif inside and line == README_ROUTER_END:
            inside = False
        elif not inside:
            kept.append(line)
    while kept and not kept[0].strip():
        kept.pop(0)
    write_text(readme, _generated_readme_router() + "\n\n" + "\n".join(kept) + "\n")


def _project_map(project_name: str, project_slug: str, project_description: str) -> str:
    return (
        "\n".join(
            [
                "# Project Map",
                "",
                "## Repository Identity",
                "",
                f"- name: `{project_name}`",
                f"- slug: `{project_slug}`",
                f"- description: {project_description or '1С-проект, созданный на шаблоне runner-agnostic monorepo.'}",
                "- role: generated 1С-проект на шаблоне runner-agnostic monorepo",
                "",
                "## Repo-Derived Snapshot",
                "",
                f"- configuration xml: `{'present' if (project_root() / 'src' / 'cf' / 'Configuration.xml').is_file() else 'missing'}`",
                f"- extensions: `{sum(1 for _ in (project_root() / 'src' / 'cfe').glob('*')) if (project_root() / 'src' / 'cfe').is_dir() else 0}`",
                f"- external processors: `{sum(1 for _ in (project_root() / 'src' / 'epf').glob('*')) if (project_root() / 'src' / 'epf').is_dir() else 0}`",
                f"- reports: `{sum(1 for _ in (project_root() / 'src' / 'erf').glob('*')) if (project_root() / 'src' / 'erf').is_dir() else 0}`",
                "",
                "## Canonical Entrypoints",
                "",
                "- onboarding: `make codex-onboard` / `./make.ps1 codex-onboard`",
                "- baseline verify: `make agent-verify` / `./make.ps1 agent-verify`",
                "- context refresh: `./scripts/llm/export-context.sh --write` / `./scripts/llm/export-context.ps1 --write`",
                "- imported skill readiness: `make imported-skills-readiness` / `./make.ps1 imported-skills-readiness`",
                "",
            ]
        )
        + "\n"
    )


def _architecture_map() -> str:
    return (
        "# Architecture Map\n\n"
        "- Curated project truth: `automation/context/project-map.md`\n"
        "- Project-aware first-hour skills: `automation/context/recommended-skills.generated.md`\n"
        "- Runtime quick answers: `docs/agent/runtime-quickstart.md`\n"
        "- Raw generated inventory: `automation/context/metadata-index.generated.json`\n"
    )


def _operator_local_runbook() -> str:
    return "# Operator-Local Runbook\n\n- Linux/macOS: `./scripts/diag/doctor.sh --profile env/local.json --run-root ./.artifacts/doctor-run`\n- Windows: `./scripts/diag/doctor.ps1 --profile env/windows-local.json --run-root ./.artifacts/doctor-run`\n"


def _runtime_quickstart() -> str:
    return (
        "# Runtime Quickstart\n\n"
        "- Linux shell entrypoints: `./scripts/.../*.sh` or `make <target>`\n"
        "- Windows PowerShell entrypoints: `./scripts/.../*.ps1` or `./make.ps1 <target>`\n"
        "- Native Windows direct-platform preset: `env/windows-local.example.json`\n"
        "- POSIX-only contours: `platform.xvfb`, `platform.ldPreload`\n"
        "- Compact first-hour skill routing: `automation/context/recommended-skills.generated.md`\n"
        "- Imported skill readiness: `make imported-skills-readiness` or `./scripts/skills/run-imported-skill.sh --readiness`\n"
    )


def _runtime_profile_policy() -> dict[str, object]:
    return {
        "rootEnvProfiles": {
            "canonicalExamples": [
                "env/local.example.json",
                "env/wsl.example.json",
                "env/ci.example.json",
                "env/windows-executor.example.json",
                "env/windows-local.example.json",
            ],
            "canonicalLocalPrivate": [
                "env/local.json",
                "env/wsl.json",
                "env/ci.json",
                "env/windows-executor.json",
                "env/windows-local.json",
            ],
            "sanctionedAdditionalProfiles": [],
            "localSandbox": "env/.local/",
        }
    }


# Development toolkit contours. Linux and Windows wrappers exist for each of them, but the Windows
# path has not been executed yet: profile-bound entries keep `operator-local` without live evidence,
# and every summary says so until a Windows run records evidence.
WINDOWS_NOT_RUN = "Windows wrapper ships but has not been executed on Windows yet."


def _toolkit_contours() -> list[dict[str, object]]:
    return [
        {
            "id": "check-bsl",
            "layer": "profile-required",
            "status": "operator-local",
            "entrypoint": 'make check-bsl ARGS="--profile env/local.json MODULE.bsl" / ./make.ps1 check-bsl --profile env/windows-local.json MODULE.bsl',
            "profileProvenance": "bsl-analyzer-app for static mode; operator-local env/local.json or explicit --profile for platform mode",
            "runbookPath": ".agents/skills/1c-check-bsl/SKILL.md",
            "summary": "Syntax check of selected BSL modules: static parse plus platform compile in the profile infobase; "
            "reports 'not checked' when a tool is unavailable. " + WINDOWS_NOT_RUN,
        },
        {
            "id": "check-cf-modules",
            "layer": "profile-required",
            "status": "operator-local",
            "entrypoint": 'make check-cf-modules ARGS="--profile env/local.json MODULE.bsl" / ./make.ps1 check-cf-modules --profile env/windows-local.json MODULE.bsl',
            "profileProvenance": "operator-local env/local.json or explicit --profile",
            "runbookPath": ".agents/skills/1c-check-bsl/SKILL.md",
            "summary": "Designer /CheckModules after a partial load of selected main-configuration modules; "
            "the database configuration is not updated. " + WINDOWS_NOT_RUN,
        },
        {
            "id": "analyze-bsl-external",
            "layer": "tool-required",
            "status": "operator-local",
            "entrypoint": 'make analyze-bsl-external ARGS="--all-managed" / ./make.ps1 analyze-bsl-external --all-managed',
            "profileProvenance": "operator-installed bsl-analyzer-app; no runtime profile",
            "runbookPath": ".agents/skills/1c-check-bsl/SKILL.md",
            "summary": "Static check of EPF/ERF modules together with the main configuration; exit code 3 means "
            "the analyzer is unavailable. " + WINDOWS_NOT_RUN,
        },
        {
            "id": "run-client",
            "layer": "profile-required",
            "status": "operator-local",
            "entrypoint": 'make run-client ARGS="start --profile env/local.json --run-root /tmp/run-client-run" / ./make.ps1 run-client start --profile env/windows-local.json',
            "profileProvenance": "operator-local env/local.json (Linux: platform.xpra.enabled) or explicit --profile",
            "runbookPath": ".agents/skills/1c-run-client/SKILL.md",
            "summary": "Start, wait for, inspect and stop a 1C client of the profile infobase under the observation adapter; "
            "screenshot, key and click work on Linux only. " + WINDOWS_NOT_RUN,
        },
        {
            "id": "technological-log",
            "layer": "profile-required",
            "status": "operator-local",
            "entrypoint": "./scripts/diag/technological-log.sh status / ./scripts/diag/technological-log.ps1 status",
            "profileProvenance": "operator-local platform install with writable logcfg.xml (TECHLOG_CONFIG_PATH)",
            "runbookPath": ".agents/skills/1c-observe-run/SKILL.md",
            "summary": "Bounded technological log for one observed launch, cursor read and logcfg.xml restore; "
            "observation.jsonl and progress.txt are written by every observed launch. " + WINDOWS_NOT_RUN,
        },
        {
            "id": "artifact-storage",
            "layer": "safe-local",
            "status": "supported",
            "entrypoint": 'make artifact-storage ARGS="status" / ./make.ps1 artifact-storage status',
            "profileProvenance": "none",
            "runbookPath": "docs/agent/generated-project-verification.md",
            "summary": "Run storage outside the checkout with size and free-space limits; Windows locking and free-space "
            "checks are covered by contract tests only. " + WINDOWS_NOT_RUN,
        },
    ]


def _runtime_support_matrix_json() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "matrixRole": "project-owned-runtime-support-matrix",
        "statuses": ["supported", "unsupported", "operator-local", "provisioned"],
        "projectSpecificBaselineExtension": None,
        "contours": [
            {
                "id": "codex-onboard",
                "layer": "safe-local",
                "status": "supported",
                "entrypoint": "make codex-onboard / ./make.ps1 codex-onboard",
                "profileProvenance": "none",
                "runbookPath": "docs/agent/generated-project-index.md",
                "summary": "Read-only onboarding snapshot for a new Codex session.",
            },
            {
                "id": "agent-verify",
                "layer": "safe-local",
                "status": "supported",
                "entrypoint": "make agent-verify / ./make.ps1 agent-verify",
                "profileProvenance": "none",
                "runbookPath": "docs/agent/generated-project-verification.md",
                "summary": "No-1C baseline verification for docs and context.",
            },
            {
                "id": "export-context-check",
                "layer": "safe-local",
                "status": "supported",
                "entrypoint": "make export-context-check",
                "profileProvenance": "none",
                "runbookPath": "docs/agent/generated-project-verification.md",
                "summary": "Read-only freshness check for generated-derived context.",
            },
            {
                "id": "doctor",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "./scripts/diag/doctor.ps1 --profile env/windows-local.json --run-root ./.artifacts/doctor-run",
                "profileProvenance": "operator-local env/windows-local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Runtime readiness check depends on an operator-owned local profile.",
            },
            {
                "id": "check-x11-contour",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make check-x11-contour",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "X11/xpra readiness diagnostic for GUI-based 1C contours.",
            },
            {
                "id": "load-cfe",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make load-cfe",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Sequential ibcmd load/check/apply for extensions under src/cfe.",
            },
            {
                "id": "configure-cfe-runtime-flags",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make configure-cfe-runtime-flags",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Generic extension safe-mode and unsafe-action-protection configuration.",
            },
            {
                "id": "check-cfe-applicability",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make check-cfe-applicability",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Designer applicability diagnostic for extensions under src/cfe.",
            },
            {
                "id": "check-cfe-config",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make check-cfe-config",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Designer extension configuration diagnostic.",
            },
            {
                "id": "load-diff-src",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make load-diff-src",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Load only current git-backed source diff.",
            },
            {
                "id": "load-task-src",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make load-task-src",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Load committed task scope by Work-Item or range.",
            },
            {
                "id": "yaxunit",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make test-yaxunit",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Run init-test-tooling when pinned sources are absent, then sync-yaxunit-runtime for the selected target before this YAxUnit runner.",
            },
            {
                "id": "yaxunit-warm-rpc",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make yaxunit-warm-service",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Run init-test-tooling when pinned sources are absent, then sync-yaxunit-runtime for the selected target before this warm RPC service.",
            },
            {
                "id": "web-client-diagnostic",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make web-client-diagnostic",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Opt-in post-failure 1C web-client diagnostic.",
            },
            {
                "id": "golden-baseline",
                "layer": "project-required",
                "status": "operator-local",
                "entrypoint": "make golden-baseline",
                "profileProvenance": "project-owned tests/golden/run.sh or GOLDEN_BASELINE_COMMAND",
                "runbookPath": "tests/golden/README.md",
                "summary": "Mandatory project regression baseline; fails closed until the project wires the golden comparison.",
            },
            {
                "id": "bdd",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make test-bdd",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "BDD contour for projects that provide local runtime assets.",
            },
            {
                "id": "bdd-warm-service",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make bdd-warm-service",
                "profileProvenance": "operator-local env/local.json plus automation/context/operator-local-targets.json",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Run init-test-tooling and install-test-tooling when their outputs are absent, sync the selected extensions, then start /TESTMANAGER and /TestClient; project-owned 1C code handles capabilities.bddWarmService.launchParameterName.",
            },
            {
                "id": "smoke",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make smoke",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Project smoke contour.",
            },
            {
                "id": "publish-http",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "./scripts/platform/publish-http.sh --profile env/local.json",
                "profileProvenance": "operator-local env/local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "HTTP publication contour.",
            },
            *_toolkit_contours(),
        ],
    }
    return apply_runtime_support_platforms(payload)


POSIX_ONLY_CONTOURS = frozenset(
    {
        "check-x11-contour",
        "yaxunit",
        "yaxunit-warm-rpc",
        "web-client-diagnostic",
        "golden-baseline",
        "bdd-warm-service",
    }
)


RUNTIME_SUPPORT_PLATFORMS = ("linux", "windows")
RUNTIME_SUPPORT_MATRIX_MIGRATION_COMMAND = (
    "./scripts/template/migrate-runtime-support-matrix.sh "
    "(Windows: .\\scripts\\template\\migrate-runtime-support-matrix.ps1)"
)


def _unverified_platform_support(contour: dict[str, Any], platform: str) -> dict[str, Any]:
    """Platform entry without live evidence (`evidence: null`): the platform has not been verified yet."""
    return {
        "status": "unsupported"
        if platform == "windows" and contour.get("id") in POSIX_ONLY_CONTOURS
        else contour.get("status"),
        "evidenceClass": "contract-only" if contour.get("layer") == "safe-local" else "contract-plus-live",
        "evidence": None,
    }


def add_missing_runtime_support_platforms(payload: dict[str, Any]) -> list[str]:
    """Add only absent linux/windows entries; existing entries and fields stay untouched.

    Returns the added `<contour>/<platform>` pairs in matrix order.
    """
    added: list[str] = []
    for contour in payload["contours"]:
        platforms = contour.get("platforms")
        if not isinstance(platforms, dict):
            platforms = {}
            contour["platforms"] = platforms
        for platform in RUNTIME_SUPPORT_PLATFORMS:
            if not isinstance(platforms.get(platform), dict):
                platforms[platform] = _unverified_platform_support(contour, platform)
                added.append(f"{contour.get('id')}/{platform}")
    return added


def apply_runtime_support_platforms(payload: dict[str, Any]) -> dict[str, Any]:
    """Add the linux/windows entries without live evidence; keeps entries a project already wrote."""
    add_missing_runtime_support_platforms(payload)
    return payload


def _runtime_support_matrix_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Runtime Support Matrix",
        "",
        "Этот файл является project-owned checked-in truth для runtime contour-ов generated repo.",
        "Он строится из `automation/context/runtime-support-matrix.json`; меняйте JSON и Markdown вместе.",
        "",
        "Статусы:",
        "",
        "- `supported` — runnable по checked-in baseline или safe-local contract.",
        "- `unsupported` — контур пока должен завершаться fail-closed и не считается baseline-ready.",
        "- `operator-local` — runnable только через ignored local-private profile или operator-owned local setup.",
        "- `provisioned` — требует provisioned/self-hosted runtime contour и выходит за safe-local baseline.",
        "",
        "| Contour | Platform | Status | Evidence | Profile provenance | Canonical entrypoint | Runbook |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for contour in payload["contours"]:
        for platform, support in contour["platforms"].items():
            lines.append(
                f"| `{contour['id']}` | `{platform}` | `{support['status']}` | `{support['evidenceClass']}` | "
                f"`{contour['profileProvenance']}` | `{contour['entrypoint']}` | `{contour['runbookPath']}` |"
            )
    not_run_on_windows = [
        f"`{contour['id']}`" for contour in payload["contours"] if WINDOWS_NOT_RUN in str(contour.get("summary") or "")
    ]
    lines.extend(
        [
            "",
            "Live evidence records a platform/runtime fingerprint, timestamp, and expiry. "
            "Operator-local status is not shared baseline readiness.",
            "",
            "Missing test sources route to `init-test-tooling`; installed YAxUnit sources route to "
            "`sync-yaxunit-runtime`; Vanessa BDD additionally routes missing Vanessa Automation Single to "
            "`install-test-tooling`.",
        ]
    )
    if not_run_on_windows:
        lines.extend(
            [
                "",
                "Windows: обёртки "
                + ", ".join(not_run_on_windows)
                + " поставляются, но на Windows ещё не запускались. Пока у Windows-записи нет живого доказательства, "
                "не считайте контур проверенным на Windows.",
            ]
        )
    lines.extend(
        [
            "",
            "## Optional Project-Specific Baseline Extension",
            "",
            "- По умолчанию `projectSpecificBaselineExtension` в `automation/context/runtime-support-matrix.json` "
            "остаётся `null`.",
            "- Если проект добавляет extra no-1C smoke, используйте direct repo-owned entrypoint или "
            "`make project-smoke` и держите его отдельным от template baseline.",
            "- `docs/agent/runtime-quickstart.md` и `make codex-onboard` должны ссылаться на extension только после "
            "того, как он объявлен здесь.",
            "",
            "## Rules",
            "",
            "- Если durable docs ссылаются на contour, который живёт только через ignored local-private profile, "
            "отмечайте его здесь как `operator-local` и ведите decision bridge через "
            "`docs/agent/operator-local-runbook.md`.",
            "- `automation/context/project-map.md` и onboarding docs должны ссылаться на этот matrix вместо того, "
            "чтобы делать `env/local.json` shared source of truth.",
            "- Меняйте этот файл синхронно с `automation/context/runtime-profile-policy.json`, "
            "`docs/agent/generated-project-index.md` и `docs/agent/generated-project-verification.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_runtime_support_matrix_files(json_path: Path, markdown_path: Path | None = None) -> None:
    """Add platform entries to a seeded matrix JSON and render its Markdown (used by the POSIX bootstrap)."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if add_missing_runtime_support_platforms(payload):
        write_json(json_path, payload)
    if markdown_path is not None:
        write_text(markdown_path, _runtime_support_matrix_md(payload))


def migrate_runtime_support_matrix(root: Path) -> str:
    """Add absent platform entries to a project's matrix JSON and rebuild its Markdown from that JSON.

    Existing fields are never changed; a second run with nothing to add leaves both files byte-identical.
    """
    context = root / "automation" / "context"
    json_path = context / "runtime-support-matrix.json"
    markdown_path = context / "runtime-support-matrix.md"
    if not json_path.is_file():
        die(f"runtime support matrix not found: {json_path}")
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        die(f"runtime support matrix is not valid JSON: {json_path}: {error}")
    contours = payload.get("contours") if isinstance(payload, dict) else None
    if not isinstance(contours, list) or not all(isinstance(contour, dict) for contour in contours):
        die(f"runtime support matrix must contain a contours array of objects: {json_path}")
    incomplete = [
        str(contour.get("id") or "<missing id>")
        for contour in contours
        if not all(isinstance(contour.get(key), str) for key in ("id", "status", "profileProvenance"))
        or not all(key in contour for key in ("entrypoint", "runbookPath"))
    ]
    if incomplete:
        die(
            "runtime support matrix contours need string id/status/profileProvenance "
            "and entrypoint/runbookPath keys: " + " ".join(incomplete)
        )
    added = add_missing_runtime_support_platforms(payload)
    if added:
        write_json(json_path, payload)
    markdown = _runtime_support_matrix_md(payload)
    markdown_changed = not markdown_path.is_file() or markdown_path.read_text(encoding="utf-8") != markdown
    if markdown_changed:
        write_text(markdown_path, markdown)
    lines = [f"added platform entry (evidence: null): {pair}" for pair in added]
    if markdown_changed:
        lines.append(
            f"rebuilt {markdown_path.relative_to(root).as_posix()} from JSON; "
            "its previous content was replaced, review it with git diff"
        )
    if not lines:
        lines.append("runtime support matrix already has linux/windows entries; nothing changed")
    return "\n".join(lines) + "\n"


def _operator_local_targets_json() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "operatorLocalTargets": {
            "vanessaBdd": {
                "targetId": "",
                "infobase": {
                    "mode": "",
                    "filePath": "",
                    "server": "",
                    "ref": "",
                },
            }
        },
        "notes": [
            "Project-owned non-secret target truth for operator-local profiles.",
            "Set operatorLocalTargets.vanessaBdd before enabling bdd-warm-service.",
            "Keep credentials and local Vanessa paths in ignored runtime profiles.",
        ],
    }


# Project-owned files that seed_generated_project_surface writes into a generated project.
# They do not exist in the template source repo; keep this list in sync with the function below.
GENERATED_PROJECT_SEED_PATHS: frozenset[str] = frozenset(
    {
        "README.md",
        "automation/context/project-map.md",
        "docs/agent/architecture-map.md",
        "docs/agent/operator-local-runbook.md",
        "docs/agent/runtime-quickstart.md",
        "automation/context/runtime-profile-policy.json",
        "automation/context/operator-local-targets.json",
        "automation/context/runtime-support-matrix.json",
        "automation/context/runtime-support-matrix.md",
    }
)


def seed_generated_project_surface(root: Path, project_name: str, project_slug: str, project_description: str) -> None:
    ensure_dir(root / "src" / "cf")
    ensure_dir(root / "src" / "cfe")
    ensure_dir(root / "src" / "epf")
    ensure_dir(root / "src" / "erf")
    write_text(root / "README.md", _generated_readme(project_name, project_description))
    write_text(
        root / "automation" / "context" / "project-map.md",
        _project_map(project_name, project_slug, project_description),
    )
    write_text(root / "docs" / "agent" / "architecture-map.md", _architecture_map())
    write_text(root / "docs" / "agent" / "operator-local-runbook.md", _operator_local_runbook())
    write_text(root / "docs" / "agent" / "runtime-quickstart.md", _runtime_quickstart())
    write_json(root / "automation" / "context" / "runtime-profile-policy.json", _runtime_profile_policy())
    write_json(root / "automation" / "context" / "operator-local-targets.json", _operator_local_targets_json())
    matrix = _runtime_support_matrix_json()
    write_json(root / "automation" / "context" / "runtime-support-matrix.json", matrix)
    write_text(root / "automation" / "context" / "runtime-support-matrix.md", _runtime_support_matrix_md(matrix))


def refresh_generated_project_surface(
    root: Path, project_name: str, project_slug: str, project_description: str
) -> None:
    """Template-update counterpart of seed_generated_project_surface, same as the POSIX
    refresh_generated_project_surface_on_update: README gets a fresh router block, every other
    project-owned file is written only when it is missing, so filled matrix and quickstart stay intact."""
    for name in ("cf", "cfe", "epf", "erf"):
        ensure_dir(root / "src" / name)
    _refresh_generated_readme(root / "README.md", project_name, project_description)
    starters: dict[str, Callable[[], str]] = {
        "automation/context/project-map.md": lambda: _project_map(project_name, project_slug, project_description),
        "docs/agent/architecture-map.md": _architecture_map,
        "docs/agent/operator-local-runbook.md": _operator_local_runbook,
        "docs/agent/runtime-quickstart.md": _runtime_quickstart,
    }
    for rel, render in starters.items():
        if not (root / rel).exists():
            write_text(root / rel, render())
    context = root / "automation" / "context"
    if not (context / "runtime-profile-policy.json").exists():
        write_json(context / "runtime-profile-policy.json", _runtime_profile_policy())
    if not (context / "operator-local-targets.json").exists():
        write_json(context / "operator-local-targets.json", _operator_local_targets_json())
    matrix_json = context / "runtime-support-matrix.json"
    if not matrix_json.exists():
        write_json(matrix_json, _runtime_support_matrix_json())
    if not (context / "runtime-support-matrix.md").exists():
        render_runtime_support_matrix_files(matrix_json, context / "runtime-support-matrix.md")


def append_agents_overlay(agents_file: Path) -> None:
    ensure_dir(agents_file.parent)
    existing = agents_file.read_text(encoding="utf-8") if agents_file.is_file() else ""
    block = "\n".join(
        [
            "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->",
            "# Project Docs",
            "",
            "- Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).",
            "- Run `make codex-onboard` or `./make.ps1 codex-onboard` for a read-only first screen in a generated repo.",
            "- Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.",
            "- Use [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md) as the compact project-aware skill router.",
            "- Use [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md) and [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json) as the checked-in runtime support truth.",
            "- Use `make imported-skills-readiness` before executable imported compatibility skills.",
            "<!-- RUNNER_AGNOSTIC_TEMPLATE:END -->",
            "",
        ]
    )
    start = "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"
    end = "<!-- RUNNER_AGNOSTIC_TEMPLATE:END -->"
    if start in existing and end in existing:
        existing = existing.split(start)[0].rstrip() + "\n"
    if existing and not existing.endswith("\n"):
        existing += "\n"
    write_text(agents_file, existing + block)


def _delegate_shell_bootstrap(script_relpath: str, args: list[str], repo_root: Path) -> int | None:
    if os.name == "nt" or shutil.which("bash") is None:
        return None
    script_path = repo_root / script_relpath
    if not script_path.is_file():
        return None
    return run_process(["bash", str(script_path), *args], cwd=repo_root, check=False, capture_output=False).returncode


def bootstrap_post_copy(
    template_src_path: str,
    template_source: str,
    project_name: str,
    project_slug: str,
    project_description: str,
    _preferred_adapter: str,
    openspec_tools: str,
    init_git_repository: str,
    *,
    root: Path | None = None,
) -> int:
    repo_root = root or project_root()
    delegated = _delegate_shell_bootstrap(
        "scripts/bootstrap/copier-post-copy.sh",
        [
            template_src_path,
            template_source,
            project_name,
            project_slug,
            project_description,
            _preferred_adapter,
            openspec_tools,
            init_git_repository,
        ],
        repo_root,
    )
    if delegated is not None:
        return delegated
    if init_git_repository == "yes" and not (repo_root / ".git").exists():
        run_git(["init"], cwd=repo_root, check=True)
    run_process(["openspec", "init", "--tools", openspec_tools], cwd=repo_root, check=True, capture_output=False)
    write_text(repo_root / "openspec" / "config.yaml", "schema: spec-driven\n")
    seed_generated_project_surface(repo_root, project_name, project_slug, project_description)
    append_agents_overlay(repo_root / "AGENTS.md")
    source_root = Path(template_src_path)
    sync_overlay_manifests(
        source_root,
        repo_root,
        overlay_manifest_file(repo_root),
        overlay_manifest_file(source_root),
    )
    write_overlay_version(repo_root, bootstrap_template_ref_or_fallback(repo_root, Path(template_src_path)))
    write_overlay_source(repo_root, template_source)
    export_context("--write", repo_root)
    return 0


def bootstrap_post_update(
    template_src_path: str,
    project_name: str,
    project_slug: str,
    project_description: str,
    *,
    root: Path | None = None,
) -> int:
    repo_root = root or project_root()
    delegated = _delegate_shell_bootstrap(
        "scripts/bootstrap/copier-post-update.sh",
        [template_src_path, project_name, project_slug, project_description],
        repo_root,
    )
    if delegated is not None:
        return delegated
    sync_overlay_manifests(
        Path(template_src_path),
        repo_root,
        overlay_manifest_file(repo_root),
        overlay_manifest_file(Path(template_src_path)),
        overlay_preserve_manifest_file(Path(template_src_path)),
    )
    refresh_generated_project_surface(repo_root, project_name, project_slug, project_description)
    append_agents_overlay(repo_root / "AGENTS.md")
    write_overlay_version(repo_root, bootstrap_template_ref_or_fallback(repo_root, Path(template_src_path)))
    write_overlay_source(repo_root, template_src_path)
    export_context("--write", repo_root)
    return 0


def resolve_target_overlay_ref(source: str, requested_ref: str = "") -> str:
    if requested_ref:
        return requested_ref
    source_path = Path(source)
    if source_path.is_dir() and (source_path / ".git").exists():
        tags = run_git(["tag", "--list"], cwd=source_path, check=True).stdout.splitlines()
    else:
        tags = [
            line.split("/")[-1]
            for line in run_git(
                ["ls-remote", "--tags", "--refs", source], cwd=project_root(), check=True
            ).stdout.splitlines()
            if line.strip()
        ]
    if not tags:
        die(f"no tagged overlay releases found for template source: {source}")
    return sorted(tags, reverse=True)[0]


def check_update(requested_ref: str = "", *, root: Path | None = None) -> int:
    repo_root = root or project_root()
    source_path = template_source_path(repo_root)
    current_version = (
        overlay_version_file(repo_root).read_text(encoding="utf-8").strip()
        if overlay_version_file(repo_root).is_file()
        else template_answers_value(repo_root, "_commit", "unknown")
    )
    target_ref = resolve_target_overlay_ref(source_path, requested_ref)
    print(f"Current overlay version: {current_version}")
    print(f"Available overlay release: {target_ref}")
    print("Project is up-to-date." if current_version == target_ref else "Overlay update available.")
    return 0


def update_template(requested_ref: str = "", pretend: bool = False, *, root: Path | None = None) -> int:
    repo_root = root or project_root()
    if run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_root).returncode != 0:
        die("copier update requires a git repository")
    if run_git(["status", "--porcelain"], cwd=repo_root, check=True).stdout.strip():
        die("git working tree is dirty; commit or stash changes before overlay update")
    source_path = template_source_path(repo_root)
    current_version = (
        overlay_version_file(repo_root).read_text(encoding="utf-8").strip()
        if overlay_version_file(repo_root).is_file()
        else template_answers_value(repo_root, "_commit", "unknown")
    )
    target_ref = resolve_target_overlay_ref(source_path, requested_ref)
    if current_version == target_ref:
        print("Overlay is already up-to-date")
        return 0
    with tempfile.TemporaryDirectory(prefix="overlay-release-") as temp_dir:
        release_root = Path(temp_dir) / "release"
        run_git(
            ["clone", "--depth", "1", "--branch", target_ref, source_path, str(release_root)], cwd=repo_root, check=True
        )
        if pretend:
            sync_overlay_manifests(
                release_root,
                repo_root,
                overlay_manifest_file(repo_root),
                overlay_manifest_file(release_root),
                overlay_preserve_manifest_file(release_root),
                dry_run=True,
            )
            seed_missing_project_files(release_root, repo_root, dry_run=True)
            print("would refresh generated overlay surfaces")
            return 0
        sync_overlay_manifests(
            release_root,
            repo_root,
            overlay_manifest_file(repo_root),
            overlay_manifest_file(release_root),
            overlay_preserve_manifest_file(release_root),
        )
        seed_missing_project_files(release_root, repo_root)
        refresh_generated_project_surface(
            repo_root,
            template_answers_value(repo_root, "project_name"),
            template_answers_value(repo_root, "project_slug"),
            template_answers_value(repo_root, "project_description"),
        )
        append_agents_overlay(repo_root / "AGENTS.md")
        write_overlay_version(repo_root, target_ref)
        write_overlay_source(repo_root, source_path)
        export_context("--write", repo_root)
    return 0


def migrate_runtime_profile_v2(legacy_profile: Path) -> str:
    payload = json.loads(legacy_profile.read_text(encoding="utf-8"))
    if payload.get("schemaVersion", 1) != 1:
        die(f"migration helper expects schemaVersion=1 profile: {legacy_profile}")
    shell_env = payload.get("shellEnv", {})
    binary_path = ""
    for key in ("LOAD_SRC_CMD", "DUMP_SRC_CMD", "UPDATE_DB_CMD", "CREATE_IB_CMD"):
        raw = str(shell_env.get(key, "")).strip()
        if raw:
            binary_path = raw.split()[0]
            break
    result = {
        "schemaVersion": 2,
        "profileName": payload.get("profileName", ""),
        "projectName": payload.get("projectName"),
        "projectSlug": payload.get("projectSlug"),
        "description": payload.get("description"),
        "runnerAdapter": payload.get("runnerAdapter") or "direct-platform",
        "notes": ["Generated by migrate-runtime-profile-v2.sh. Review all fields before use."],
        "platform": {
            "binaryPath": binary_path
            or (r"C:/Program Files/1cv8/common/1cv8.exe" if os.name == "nt" else "/opt/1cv8/1cv8")
        },
        "infobase": {
            "mode": "file",
            "filePath": f"./.artifacts/{payload.get('projectSlug') or 'project'}",
            "connectionStringOverride": None,
            "auth": {"mode": "os", "user": None, "passwordEnv": None},
        },
        "capabilities": {
            "dumpSrc": {"outputDir": "./src/cf"},
            "loadSrc": {"sourceDir": "./src/cf"},
            "diffSrc": {"command": ["git", "diff", "--", "./src"]},
            "bdd": {
                "unsupportedReason": "Review and wire a repo-owned BDD contour before using this migrated profile."
            },
            "smoke": {
                "unsupportedReason": "Review and wire a repo-owned smoke contour before using this migrated profile."
            },
            "publishHttp": {
                "unsupportedReason": "Review and wire a repo-owned publish contour before using this migrated profile."
            },
        },
    }
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def migrate_runtime_profile_v3(schema_v2_profile: Path, *, profile_only: bool = False) -> str:
    payload = json.loads(schema_v2_profile.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 2:
        die(f"migration helper expects schemaVersion=2 profile: {schema_v2_profile}")
    result = copy.deepcopy(payload)
    result["schemaVersion"] = 3
    adapter = result.pop("runnerAdapter", None)
    if adapter == "direct-platform":
        result.pop("transport", None)
    elif adapter == "remote-windows":
        result["transport"] = {"kind": "remote-windows"}
    else:
        die(f"schemaVersion=2 profile has unsupported runnerAdapter for automatic migration: {adapter!r}")

    unsupported_commands: list[str] = []
    capabilities = result.get("capabilities", {})
    if not isinstance(capabilities, dict):
        die("schemaVersion=2 profile capabilities must be an object")
    for capability_name, capability in capabilities.items():
        if not isinstance(capability, dict) or "command" not in capability:
            continue
        command = capability.get("command")
        if capability_name == "diffSrc" and command == ["git", "diff", "--", "./src"]:
            capability.pop("command", None)
            continue
        unsupported_commands.append(str(capability_name))
    if unsupported_commands:
        die(
            "schemaVersion=2 profile contains command orchestration without a supported "
            "schemaVersion=3 backend: " + ", ".join(sorted(unsupported_commands))
        )

    notes = result.setdefault("notes", [])
    if not isinstance(notes, list):
        die("schemaVersion=2 profile notes must be an array")
    notes.append(
        "Migrated by migrate-runtime-profile-v3 in dry-run mode; review the generated profile before replacing local-private configuration."
    )
    if profile_only:
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    report = {
        "status": "dry-run",
        "sourceSchemaVersion": 2,
        "targetSchemaVersion": 3,
        "sourceProfile": str(schema_v2_profile.resolve(strict=False)),
        "profile": result,
    }
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def new_project(destination: str, template: str, copier_args: list[str], *, cwd: Path | None = None) -> int:
    repo_root = cwd or project_root()
    cmd = ["copier", "copy", "--trust"]
    if (Path(template) / ".git").is_dir():
        cmd.extend(["--vcs-ref", "HEAD"])
    cmd.extend([*copier_args, template, destination])
    return run_process(cmd, cwd=repo_root, check=False, capture_output=False).returncode


def update_project(destination: str, extra_args: list[str]) -> int:
    repo_root = canonical_path(destination)
    preferred_suffix = ".ps1" if os.name == "nt" else ".sh"
    update_script = repo_root / "scripts" / "template" / f"update-template{preferred_suffix}"
    if not update_script.is_file():
        fallback_suffix = ".sh" if preferred_suffix == ".ps1" else ".ps1"
        update_script = repo_root / "scripts" / "template" / f"update-template{fallback_suffix}"
    if not update_script.exists():
        die(f"generated project does not provide {update_script}")
    if update_script.suffix == ".ps1":
        cmd = ["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(update_script), *extra_args]
    else:
        cmd = [str(update_script), *extra_args]
    return run_process(cmd, cwd=repo_root, check=False, capture_output=False).returncode
