from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .common import canonical_path, die, ensure_dir, project_root, run_git, run_process, write_json, write_text
from .context import export_context


DEFAULT_TEMPLATE_GIT_URL = "https://github.com/defin85/1c-runner-agnostic-template.git"
MANIFEST_RELPATH = "automation/context/template-managed-paths.txt"
PRESERVE_RELPATH = "automation/context/template-update-preserve-paths.txt"
VERSION_RELPATH = ".template-overlay-version"


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
        if rel in next_entries:
            if not source_path.is_file():
                die(f"overlay entry is missing in source release: {rel}")
            if dry_run:
                print(f"sync {rel}")
                continue
            ensure_dir(target_path.parent)
            shutil.copy2(source_path, target_path)
            continue
        if rel in preserve_entries:
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


def _generated_readme(project_name: str, project_description: str) -> str:
    return "\n".join(
        [
            "<!-- RUNNER_AGNOSTIC_PROJECT:START -->",
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
            "<!-- RUNNER_AGNOSTIC_PROJECT:END -->",
            "",
            f"# {project_name}",
            "",
            project_description or "1С-проект, созданный на шаблоне runner-agnostic monorepo.",
            "",
        ]
    ) + "\n"


def _project_map(project_name: str, project_slug: str, project_description: str) -> str:
    return "\n".join(
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
            "## Canonical Entrypoints",
            "",
            "- onboarding: `make codex-onboard` / `./make.ps1 codex-onboard`",
            "- baseline verify: `make agent-verify` / `./make.ps1 agent-verify`",
            "- context refresh: `./scripts/llm/export-context.sh --write` / `./scripts/llm/export-context.ps1 --write`",
            "",
        ]
    ) + "\n"


def _architecture_map() -> str:
    return "# Architecture Map\n\n- Curated project truth: `automation/context/project-map.md`\n- Runtime quick answers: `docs/agent/runtime-quickstart.md`\n- Raw generated inventory: `automation/context/metadata-index.generated.json`\n"


def _operator_local_runbook() -> str:
    return "# Operator-Local Runbook\n\n- Linux/macOS: `./scripts/diag/doctor.sh --profile env/local.json --run-root ./.artifacts/doctor-run`\n- Windows: `./scripts/diag/doctor.ps1 --profile env/windows-local.json --run-root ./.artifacts/doctor-run`\n"


def _runtime_quickstart() -> str:
    return "# Runtime Quickstart\n\n- Linux shell entrypoints: `./scripts/.../*.sh` or `make <target>`\n- Windows PowerShell entrypoints: `./scripts/.../*.ps1` or `./make.ps1 <target>`\n- Native Windows direct-platform preset: `env/windows-local.example.json`\n- POSIX-only contours: `platform.xvfb`, `platform.ldPreload`\n"


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


def _runtime_support_matrix_json() -> dict[str, object]:
    return {
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
                "id": "doctor",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "./scripts/diag/doctor.ps1 --profile env/windows-local.json --run-root ./.artifacts/doctor-run",
                "profileProvenance": "operator-local env/windows-local.json or explicit --profile",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Runtime readiness check depends on an operator-owned local profile.",
            },
        ],
    }


def _runtime_support_matrix_md() -> str:
    return "# Runtime Support Matrix\n\n| Contour | Status | Profile provenance | Canonical entrypoint | Runbook |\n| --- | --- | --- | --- | --- |\n| `codex-onboard` | `supported` | `none` | `make codex-onboard` / `./make.ps1 codex-onboard` | `docs/agent/generated-project-index.md` |\n| `agent-verify` | `supported` | `none` | `make agent-verify` / `./make.ps1 agent-verify` | `docs/agent/generated-project-verification.md` |\n| `doctor` | `operator-local` | `env/windows-local.json` | `./scripts/diag/doctor.ps1 --profile env/windows-local.json --run-root ./.artifacts/doctor-run` | `docs/agent/operator-local-runbook.md` |\n"


def seed_generated_project_surface(root: Path, project_name: str, project_slug: str, project_description: str) -> None:
    ensure_dir(root / "src" / "cf")
    ensure_dir(root / "src" / "cfe")
    ensure_dir(root / "src" / "epf")
    ensure_dir(root / "src" / "erf")
    write_text(root / "README.md", _generated_readme(project_name, project_description))
    write_text(root / "automation" / "context" / "project-map.md", _project_map(project_name, project_slug, project_description))
    write_text(root / "docs" / "agent" / "architecture-map.md", _architecture_map())
    write_text(root / "docs" / "agent" / "operator-local-runbook.md", _operator_local_runbook())
    write_text(root / "docs" / "agent" / "runtime-quickstart.md", _runtime_quickstart())
    write_json(root / "automation" / "context" / "runtime-profile-policy.json", _runtime_profile_policy())
    write_json(root / "automation" / "context" / "runtime-support-matrix.json", _runtime_support_matrix_json())
    write_text(root / "automation" / "context" / "runtime-support-matrix.md", _runtime_support_matrix_md())


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
            "- Use [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md) and [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json) as the checked-in runtime support truth.",
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


def bootstrap_post_copy(
    template_src_path: str,
    project_name: str,
    project_slug: str,
    project_description: str,
    _preferred_adapter: str,
    openspec_tools: str,
    init_git_repository: str,
    init_beads: str,
    beads_prefix: str,
    *,
    root: Path | None = None,
) -> int:
    repo_root = root or project_root()
    if init_beads == "yes" and init_git_repository != "yes" and not (repo_root / ".git").exists():
        die("beads requires a git repository; enable git init or disable beads")
    if init_git_repository == "yes" and not (repo_root / ".git").exists():
        run_git(["init"], cwd=repo_root, check=True)
    run_process(["openspec", "init", "--tools", openspec_tools], cwd=repo_root, check=True, capture_output=False)
    if init_beads == "yes":
        prefix = beads_prefix or project_slug
        run_process(["bd", "init", "--stealth", "-p", prefix], cwd=repo_root, check=True, capture_output=False)
    seed_generated_project_surface(repo_root, project_name, project_slug, project_description)
    append_agents_overlay(repo_root / "AGENTS.md")
    sync_overlay_manifests(
        Path(template_src_path),
        repo_root,
        overlay_manifest_file(repo_root),
        overlay_manifest_file(Path(template_src_path)),
    )
    write_overlay_version(repo_root, bootstrap_template_ref_or_fallback(repo_root, Path(template_src_path)))
    export_context("--write", repo_root)
    return 0


def bootstrap_post_update(
    template_src_path: str,
    project_name: str,
    project_slug: str,
    project_description: str,
    _init_beads: str,
    *,
    root: Path | None = None,
) -> int:
    repo_root = root or project_root()
    sync_overlay_manifests(
        Path(template_src_path),
        repo_root,
        overlay_manifest_file(repo_root),
        overlay_manifest_file(Path(template_src_path)),
        overlay_preserve_manifest_file(Path(template_src_path)),
    )
    seed_generated_project_surface(repo_root, project_name, project_slug, project_description)
    append_agents_overlay(repo_root / "AGENTS.md")
    write_overlay_version(repo_root, bootstrap_template_ref_or_fallback(repo_root, Path(template_src_path)))
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
            for line in run_git(["ls-remote", "--tags", "--refs", source], cwd=project_root(), check=True).stdout.splitlines()
            if line.strip()
        ]
    if not tags:
        die(f"no tagged overlay releases found for template source: {source}")
    return sorted(tags, reverse=True)[0]


def check_update(requested_ref: str = "", *, root: Path | None = None) -> int:
    repo_root = root or project_root()
    source_path = template_answers_value(repo_root, "_src_path")
    current_version = overlay_version_file(repo_root).read_text(encoding="utf-8").strip() if overlay_version_file(repo_root).is_file() else template_answers_value(repo_root, "_commit", "unknown")
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
    source_path = template_answers_value(repo_root, "_src_path")
    current_version = overlay_version_file(repo_root).read_text(encoding="utf-8").strip() if overlay_version_file(repo_root).is_file() else template_answers_value(repo_root, "_commit", "unknown")
    target_ref = resolve_target_overlay_ref(source_path, requested_ref)
    if current_version == target_ref:
        print("Overlay is already up-to-date")
        return 0
    with tempfile.TemporaryDirectory(prefix="overlay-release-") as temp_dir:
        release_root = Path(temp_dir) / "release"
        run_git(["clone", "--depth", "1", "--branch", target_ref, source_path, str(release_root)], cwd=repo_root, check=True)
        if pretend:
            sync_overlay_manifests(
                release_root,
                repo_root,
                overlay_manifest_file(repo_root),
                overlay_manifest_file(release_root),
                overlay_preserve_manifest_file(release_root),
                dry_run=True,
            )
            print("would refresh generated overlay surfaces")
            return 0
        sync_overlay_manifests(
            release_root,
            repo_root,
            overlay_manifest_file(repo_root),
            overlay_manifest_file(release_root),
            overlay_preserve_manifest_file(release_root),
        )
        seed_generated_project_surface(
            repo_root,
            template_answers_value(repo_root, "project_name"),
            template_answers_value(repo_root, "project_slug"),
            template_answers_value(repo_root, "project_description"),
        )
        append_agents_overlay(repo_root / "AGENTS.md")
        write_overlay_version(repo_root, target_ref)
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
            "binaryPath": binary_path or (r"C:/Program Files/1cv8/common/1cv8.exe" if os.name == "nt" else "/opt/1cv8/1cv8")
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
            "xunit": {"unsupportedReason": "Review and wire a repo-owned xUnit contour before using this migrated profile."},
            "bdd": {"unsupportedReason": "Review and wire a repo-owned BDD contour before using this migrated profile."},
            "smoke": {"unsupportedReason": "Review and wire a repo-owned smoke contour before using this migrated profile."},
            "publishHttp": {"unsupportedReason": "Review and wire a repo-owned publish contour before using this migrated profile."},
        },
    }
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def new_project(destination: str, template: str, copier_args: list[str], *, cwd: Path | None = None) -> int:
    repo_root = cwd or project_root()
    cmd = ["copier", "copy", "--trust", *copier_args, template, destination]
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
