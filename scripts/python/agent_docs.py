"""Agent-facing documentation contract for the template source repo and generated projects.

One implementation serves `scripts/qa/check-agent-docs.sh` and `scripts/qa/check-agent-docs.ps1`.
Each failed assertion prints one line to stderr; the check returns 1 when any assertion fails.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .common import project_root
from .context import export_context, is_source_repo
from .runtime import (
    canonical_root_runtime_profile_filename,
    collect_runtime_profile_layout_drift_paths,
    load_sanctioned_additional_root_runtime_profiles,
)

_REPO_PATH_PREFIXES = (
    "./",
    "scripts/",
    "tests/",
    "features/",
    "src/",
    "automation/",
    "docs/",
    "env/",
    ".agents/",
    ".codex/",
    ".claude/",
)
_LOCAL_PRIVATE_PROFILES = frozenset(f"env/{name}.json" for name in ("local", "wsl", "ci", "windows-executor"))
_GENERATED_CODEX_PATHS = frozenset({".codex/.gitkeep", ".codex/README.md", ".codex/config.toml"})
_LOCAL_PRIVATE_TRUTH = (
    r"(?:runtime doctor:|runtime truth:|shared truth:|source of truth:).*env/(?:local|wsl|ci|windows-executor)\.json"
    r"|--profile\s+env/(?:local|wsl|ci|windows-executor)\.json|--profile\s+env/\.local/"
)
# Reported verbatim (grep -E syntax, as in earlier releases); matched through _posix_to_python_regex.
_PLACEHOLDER = "<[[:alnum:]_][^>]*>"
_LINK = re.compile(r"!\[[^\[\]]*\]\([^)]*\)|\[[^\[\]]+\]\([^)]*\)")
_LINE_SPECIFIC_LINK = re.compile(r"\]\([^)]*(?:#L[0-9]+|:[0-9]+)\)")
_AGENT_PATH_REFERENCE = re.compile(r"@/([^`\"\s,)]+)")
# Standalone repository paths only, not suffixes of `$root/...` or other path fragments.
_CURATED_PATH = re.compile(
    r"(?<![\w./\\$-])(?:\./)?(?:src|scripts|tests|features|automation|docs|env|openspec|\.agents|\.codex|\.claude)"
    r"/[^`\"\s,)]+|(?<![\w./\\$-])Makefile\b"
)
_REQUIRED_CONTOUR_IDS = frozenset(
    {
        "codex-onboard",
        "agent-verify",
        "export-context-check",
        "doctor",
        "bdd",
        "bdd-warm-service",
        "smoke",
        "publish-http",
        "load-diff-src",
        "load-task-src",
    }
)
_MATRIX_STATUSES = ["operator-local", "provisioned", "supported", "unsupported"]


class _Docs:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.status = 0
        self._unreadable: set[str] = set()

    def fail(self, message: str) -> None:
        print(message, file=sys.stderr)
        self.status = 1

    def text(self, rel: str) -> str:
        try:
            return (self.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            if rel not in self._unreadable:
                self._unreadable.add(rel)
                self.fail(f"missing or unreadable agent-facing path: {rel}")
            return ""

    def json_object(self, rel: str) -> dict[str, Any]:
        try:
            payload = json.loads(self.text(rel))
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            return payload
        self.fail(f"invalid JSON object: {rel}")
        return {}

    def require_path(self, rel: str) -> None:
        if not (self.root / rel).exists():
            self.fail(f"missing agent-facing path: {rel}")

    def require_contains(self, rel: str, expected: str) -> None:
        if expected not in self.text(rel):
            self.fail(f"missing expected text in {rel}: {expected}")

    def require_markdown_link(self, rel: str, target: str) -> None:
        if f"]({target})" not in self.text(rel):
            self.fail(f"missing required markdown link in {rel}: {target}")

    def has_line_matching(self, rel: str, pattern: str) -> bool:
        compiled = re.compile(pattern)
        return any(compiled.search(line) for line in self.text(rel).splitlines())

    def require_absent_regex(self, rel: str, pattern: str, message: str) -> None:
        if self.has_line_matching(rel, pattern):
            self.fail(f"{message}: {rel}")

    def require_no_placeholder_pattern(self, rel: str, pattern: str) -> None:
        if self.has_line_matching(rel, _posix_to_python_regex(pattern)):
            self.fail(f"unexpected placeholder or template note in {rel}: {pattern}")

    def require_no_local_private_runtime_truth(self, rel: str) -> None:
        self.require_absent_regex(
            rel,
            _LOCAL_PRIVATE_TRUTH,
            "local-private runtime profile must not be advertised as shared truth outside runtime support matrix",
        )

    def check_links(self, rel: str) -> None:
        """Reject line-specific links, broken relative links and anchors, and broken `@/path` references."""
        text = self.text(rel)
        if any(_LINE_SPECIFIC_LINK.search(line) for line in text.splitlines()):
            self.fail(f"line-specific links are not allowed in durable docs: {rel}")
        source = self.root / rel
        for number, line in enumerate(text.splitlines(), 1):
            for match in _LINK.finditer(line):
                link = match.group(0)
                if link.startswith("!"):
                    continue
                target = link[link.index("](") + 2 : -1]
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                path, has_anchor, anchor = target.partition("#")
                resolved = source if not path else source.parent / path
                if not resolved.exists():
                    self.fail(f"broken markdown link in {rel}:{number}: {target}")
                elif has_anchor and (not resolved.is_file() or not _anchor_exists(resolved, anchor)):
                    self.fail(f"missing markdown anchor in {rel}:{number}: {target}")
            for match in _AGENT_PATH_REFERENCE.finditer(line):
                if not (self.root / match.group(1)).exists():
                    self.fail(f"broken agent path reference in {rel}:{number}: @/{match.group(1)}")

    def check_curated_paths(self, rel: str) -> None:
        for candidate in sorted(set(_CURATED_PATH.findall(self.text(rel)))):
            candidate = candidate.removeprefix("./")
            if _is_local_private_profile(candidate):
                continue
            if not (self.root / candidate).exists():
                self.fail(f"representative path is missing: {rel} -> {candidate}")


def _posix_to_python_regex(pattern: str) -> str:
    """Translate the POSIX bracket classes used by these checks; `\\w` also covers non-ASCII letters, like grep in UTF-8."""
    return pattern.replace("[[:alnum:]_]", r"\w").replace("[:alnum:]", r"\w").replace("[:space:]", r"\s")


def _normalize_anchor(value: str) -> str:
    value = re.sub(r"[`\"]", "", value.lower())
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w.-]", "", value)
    return re.sub(r"-+", "-", value).strip("-")


def _anchor_exists(target: Path, anchor: str) -> bool:
    normalized = _normalize_anchor(anchor)
    if not normalized:
        return False
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    headings = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
    return any(_normalize_anchor(heading) == normalized for heading in headings)


def _is_local_private_profile(rel: str) -> bool:
    return rel in _LOCAL_PRIVATE_PROFILES or rel == "env/.local" or rel.startswith("env/.local/")


def _token_references_repo_path(root: Path, token: str) -> bool:
    candidate = re.split(r"[\s;|&()]", token, maxsplit=1)[0]
    if not candidate:
        return False
    if candidate == "Makefile" or candidate.startswith(_REPO_PATH_PREFIXES):
        return (root / candidate.removeprefix("./")).exists()
    return False


def _command_is_repo_owned(root: Path, command: list[str]) -> bool:
    if not command:
        return False
    if command[0] == "make":
        return len(command) >= 2 and bool(command[1]) and not command[1].startswith("-")
    return _token_references_repo_path(root, command[0])


def _check_verification_profile(d: _Docs, rel: str) -> None:
    """Checked-in smoke/bdd commands must be `make <target>` or an existing repo-owned entrypoint."""
    capabilities = d.json_object(rel).get("capabilities")
    if not isinstance(capabilities, dict):
        return
    for capability in ("smoke", "bdd"):
        entry = capabilities.get(capability)
        if not isinstance(entry, dict) or entry.get("command") is None:
            continue
        raw: object = entry["command"]
        tokens = [str(token) for token in raw] if isinstance(raw, list) else []
        if not _command_is_repo_owned(d.root, tokens):
            d.fail(
                "checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: "
                f"{rel} ({capability})"
            )


def _has_git_remote(root: Path) -> bool:
    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True, check=False
        )
        if inside.returncode != 0:
            return False
        remote = subprocess.run(["git", "-C", str(root), "remote"], capture_output=True, text=True, check=False)
    except OSError:
        return False
    return remote.returncode == 0 and bool(remote.stdout.strip())


def _apply(d: _Docs, links: Iterable[tuple[str, str]], contains: Iterable[tuple[str, str]]) -> None:
    for rel, target in links:
        d.require_markdown_link(rel, target)
    for rel, expected in contains:
        d.require_contains(rel, expected)


def _check_forbidden_src_cf_docs(d: _Docs) -> None:
    src_cf = d.root / "src" / "cf"
    if not src_cf.is_dir():
        return
    for path in sorted(src_cf.rglob("*.md")):
        if path.is_file():
            d.fail(
                f"forbidden non-1C markdown artifact inside deployable src/cf: {path.relative_to(d.root).as_posix()}"
            )


def _common_assertions(d: _Docs) -> None:
    for rel in _COMMON_PATHS:
        d.require_path(rel)
    _apply(d, _COMMON_MARKDOWN_LINK, _COMMON_CONTAINS)
    d.require_absent_regex(
        "src/AGENTS.md", r"(^|[^\w./-])cf/AGENTS\.md|src/cf/AGENTS\.md", "src router must stay above deployable src/cf"
    )
    d.require_absent_regex(
        "docs/agent/generated-project-index.md",
        r"^## Codex Controls$",
        "generated-project index must delegate detailed controls to the canonical workflow doc",
    )
    d.require_absent_regex(
        ".codex/README.md",
        r"^## Generated Project Playbooks$|^## Useful Session Controls$",
        "codex README must stay a pointer surface, not a duplicate workflow manual",
    )
    managed = "automation/context/template-managed-paths.txt"
    d.require_absent_regex(managed, r"^src/cf/AGENTS\.md$", "deployable src/cf router must not stay template-managed")
    d.require_absent_regex(
        managed, r"^docs/work-items/README\.md$", "project-owned work-item guide must not become template-managed"
    )
    d.require_absent_regex(
        managed, r"^docs/work-items/TEMPLATE\.md$", "project-owned work-item template must not become template-managed"
    )
    for rel in _LINKCHECK_COMMON:
        d.check_links(rel)
    _check_forbidden_src_cf_docs(d)


def _source_assertions(d: _Docs) -> None:
    for rel in _SOURCE_PATHS:
        d.require_path(rel)
    _apply(d, _SOURCE_MARKDOWN_LINK, _SOURCE_CONTAINS)
    for rel in _SOURCE_CONTEXT_PATHS:
        d.require_path(rel)
    context_dir = d.root / "automation" / "context"
    placeholder = re.compile(r"\{\{|<описание|<context-|Обновите этот файл")
    for path in sorted(context_dir.rglob("*")) if context_dir.is_dir() else []:
        if not path.is_file() or path.name in {"template-source-tree.txt", "template-source-source-files.txt"}:
            continue
        if "templates" in path.relative_to(context_dir).parts[:-1]:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if placeholder.search(text):
            d.fail("live automation context contains placeholders or template notes")
            break
    for rel in (
        "env/local.example.json",
        "env/ci.example.json",
        "env/wsl.example.json",
        "env/windows-executor.example.json",
    ):
        d.require_absent_regex(rel, "TODO:", "placeholder verification command remains in example profile")
        _check_verification_profile(d, rel)


def _generated_private_leaks(d: _Docs) -> None:
    for line in d.text("automation/context/source-tree.generated.txt").splitlines():
        if not line.startswith("./"):
            continue
        rel = line.removeprefix("./")
        if _is_local_private_profile(rel) or (rel.startswith(".codex/") and rel not in _GENERATED_CODEX_PATHS):
            d.fail(f"local-private path leaked into generated context: {rel}")
    if re.search(
        r'"env/(local|wsl|ci|windows-executor)\.json"|env/\.local/',
        d.text("automation/context/metadata-index.generated.json"),
    ):
        d.fail("generated metadata leaked local-private runtime profile paths")


def _generated_metadata_presence(d: _Docs) -> None:
    if not (d.root / "src" / "cf" / "Configuration.xml").is_file():
        return
    metadata = d.text("automation/context/metadata-index.generated.json")
    if '"name": ""' in metadata:
        d.fail("generated metadata leaves configuration.name empty despite src/cf/Configuration.xml")
    if '"present": true' not in metadata:
        d.fail("generated metadata does not mark src/cf/Configuration.xml as present")


def _generated_project_delta(d: _Docs) -> None:
    rel = "automation/context/project-delta-hints.json"
    hints = d.json_object(rel)
    if hints.get("hintsRole") != "project-owned-project-delta-hints":
        d.fail(f"project-delta hints must declare the project-owned role: {rel}")
    selectors = hints.get("selectors")
    for key in ("pathPrefixes", "pathKeywords"):
        if not isinstance(selectors, dict) or not isinstance(selectors.get(key), list):
            d.fail(f"project-delta hints must define selectors.{key} array: {rel}")
    paths = hints.get("representativePaths")
    if not isinstance(paths, list):
        d.fail(f"project-delta hints must define representativePaths array: {rel}")
        return
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        if not (d.root / path).exists():
            d.fail(f"representative path is missing: {rel} -> {path}")


def _generated_runtime_profile_policy(d: _Docs) -> None:
    rel = "automation/context/runtime-profile-policy.json"
    policy = d.json_object(rel).get("rootEnvProfiles")
    for key, kind in (
        ("canonicalExamples", list),
        ("canonicalLocalPrivate", list),
        ("sanctionedAdditionalProfiles", list),
        ("localSandbox", str),
    ):
        if not isinstance(policy, dict) or not isinstance(policy.get(key), kind):
            d.fail(f"runtime profile policy must define {key} {'array' if kind is list else 'string'}: {rel}")
    try:
        drift = collect_runtime_profile_layout_drift_paths(d.root)
        sanctioned = load_sanctioned_additional_root_runtime_profiles(d.root)
    except (ValueError, SystemExit) as exc:
        d.fail(f"invalid runtime profile policy: {exc}")
        return
    if drift:
        d.fail("generated runtime profile policy leaves unsanctioned checked-in root profiles: " + " ".join(drift))
    for profile in sanctioned:
        if not (d.root / profile).is_file():
            d.fail(f"sanctioned runtime profile is missing: {profile}")
            continue
        if canonical_root_runtime_profile_filename(Path(profile).name):
            d.fail(
                f"sanctionedAdditionalProfiles must list only additional root presets, not canonical names: {profile}"
            )
        if "TODO:" in d.text(profile):
            d.fail(f"sanctioned runtime profile contains placeholder TODO: {profile}")
        _check_verification_profile(d, profile)


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _generated_runtime_support_matrix(d: _Docs) -> dict[str, Any]:
    rel = "automation/context/runtime-support-matrix.json"
    matrix = d.json_object(rel)
    if matrix.get("matrixRole") != "project-owned-runtime-support-matrix":
        d.fail(f"runtime support matrix must declare project-owned role: {rel}")
    statuses = matrix.get("statuses")
    if not isinstance(statuses, list) or sorted(str(item) for item in statuses) != _MATRIX_STATUSES:
        d.fail(f"runtime support matrix must define the canonical status set: {rel}")
    contours = matrix.get("contours")
    contour_list = [item for item in contours if isinstance(item, dict)] if isinstance(contours, list) else []
    ids = {item.get("id") for item in contour_list}
    if not _REQUIRED_CONTOUR_IDS <= ids:
        d.fail(f"runtime support matrix must cover the required contour ids: {rel}")
    if (
        not isinstance(contours, list)
        or not contours
        or len(contour_list) != len(contours)
        or not all(
            all(_non_empty_str(item.get(key)) for key in ("id", "status", "profileProvenance"))
            and (_non_empty_str(item.get("entrypoint")) or _non_empty_str(item.get("runbookPath")))
            for item in contour_list
        )
    ):
        d.fail(f"runtime support matrix contours must declare id/status/provenance and entrypoint or runbook: {rel}")
    extension = matrix.get("projectSpecificBaselineExtension")
    if extension is not None and (
        not isinstance(extension, dict)
        or not all(_non_empty_str(extension.get(key)) for key in ("id", "entrypoint", "runbookPath", "summary"))
    ):
        d.fail(f"runtime support matrix projectSpecificBaselineExtension must be null or a complete object: {rel}")
    return matrix


def _jq_text(value: object) -> str:
    """Render a JSON scalar the way `jq -r` does, so a missing field compares as `null`."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _quickstart_rows(text: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:]]
        if len(cells) < 5:
            continue
        first = cells[0]
        if not (first.startswith("`") and first.endswith("`")) or len(first) < 2:
            continue
        rows.setdefault(first[1:-1], [cell.strip("`") for cell in cells[1:5]])
    return rows


def _generated_runtime_quickstart(d: _Docs, matrix: dict[str, Any]) -> None:
    rel = "docs/agent/runtime-quickstart.md"
    rows = _quickstart_rows(d.text(rel))
    contours = matrix.get("contours")
    for contour in contours if isinstance(contours, list) else []:
        if not isinstance(contour, dict) or not isinstance(contour.get("id"), str):
            continue
        contour_id = contour["id"]
        row = rows.get(contour_id)
        if row is None:
            d.fail(f"runtime quick reference is missing contour row: {rel} ({contour_id})")
            continue
        status_cell, entrypoint_cell, prerequisites_cell, runbook_cell = row
        if (
            status_cell != _jq_text(contour.get("status"))
            or entrypoint_cell != _jq_text(contour.get("entrypoint"))
            or runbook_cell != _jq_text(contour.get("runbookPath"))
            or not prerequisites_cell
        ):
            d.fail(f"runtime quick reference drifts from runtime support matrix: {rel} ({contour_id})")
    extension = matrix.get("projectSpecificBaselineExtension")
    if isinstance(extension, dict) and _non_empty_str(extension.get("id")):
        d.require_contains(rel, str(extension["id"]))
        d.require_contains(rel, str(extension.get("entrypoint") or ""))


def _generated_baseline_extension(d: _Docs, matrix: dict[str, Any]) -> None:
    extension = matrix.get("projectSpecificBaselineExtension")
    if not isinstance(extension, dict) or not _non_empty_str(extension.get("id")):
        return
    entrypoint = str(extension.get("entrypoint") or "")
    tokens = entrypoint.split()
    first = tokens[0] if tokens else ""
    if first == "make":
        if len(tokens) < 2 or tokens[1].startswith("-"):
            d.fail(f"project-specific baseline extension must use repo-owned entrypoint or make <target>: {entrypoint}")
    elif first == "Makefile" or first.startswith(_REPO_PATH_PREFIXES):
        if not _token_references_repo_path(d.root, first):
            d.fail(f"project-specific baseline extension entrypoint is missing: {first}")
    else:
        d.fail(f"project-specific baseline extension must use repo-owned entrypoint or make <target>: {entrypoint}")
    runbook = str(extension.get("runbookPath") or "")
    if not runbook or not (d.root / runbook).exists():
        d.fail(f"project-specific baseline extension runbook is missing: {runbook}")


def _generated_closeout(d: _Docs) -> None:
    if _has_git_remote(d.root):
        return
    for rel in ("AGENTS.md", "README.md", "docs/agent/generated-project-index.md", ".codex/README.md"):
        if d.has_line_matching(rel, r"not complete until `git push` succeeds|then `git push`"):
            d.fail(f"generated closeout guidance must distinguish local-only and remote-backed repos: {rel}")


def _generated_assertions(d: _Docs) -> None:
    for rel in _GENERATED_PATHS:
        d.require_path(rel)
    for rel in _LINKCHECK_GENERATED:
        d.check_links(rel)
    _apply(d, _GENERATED_MARKDOWN_LINK, _GENERATED_CONTAINS)
    for rel in (
        "AGENTS.md",
        "README.md",
        "docs/agent/codex-workflows.md",
        "docs/agent/generated-project-index.md",
        "automation/context/project-map.md",
    ):
        d.require_no_local_private_runtime_truth(rel)
    for rel in (
        "README.md",
        "automation/context/project-map.md",
        "docs/agent/codex-workflows.md",
        "docs/agent/architecture-map.md",
        "docs/agent/operator-local-runbook.md",
        "docs/agent/runtime-quickstart.md",
    ):
        d.require_no_placeholder_pattern(rel, _PLACEHOLDER)
    for rel in ("README.md", "automation/context/project-map.md"):
        d.require_no_placeholder_pattern(rel, "template source repo")
    d.require_absent_regex(
        "README.md", r"docs/agent/index\.md", "generated README must not route to source-repo-centric onboarding"
    )
    _generated_private_leaks(d)
    _apply(d, (), _GEN_FUNCS_CONTAINS)
    _generated_metadata_presence(d)
    _generated_project_delta(d)
    _generated_runtime_profile_policy(d)
    matrix = _generated_runtime_support_matrix(d)
    # Linux and Windows render the matrix with the same template_tools code, so the platform
    # entries, live-evidence expiry and Markdown freshness are checked on both.
    from .qa import validate_runtime_support_matrix

    if validate_runtime_support_matrix(d.root) != 0:
        d.status = 1
    for rel in (
        "automation/context/project-map.md",
        "docs/agent/architecture-map.md",
        "docs/agent/operator-local-runbook.md",
        "docs/agent/runtime-quickstart.md",
    ):
        d.check_curated_paths(rel)
    _generated_runtime_quickstart(d, matrix)
    _generated_baseline_extension(d, matrix)
    _generated_closeout(d)


def check_agent_docs(root: Path | None = None) -> int:
    """Run the agent-facing docs contract; return 0 when every assertion holds."""
    d = _Docs(root or project_root())
    _common_assertions(d)
    if is_source_repo(d.root):
        _source_assertions(d)
    else:
        _generated_assertions(d)
    if export_context("--check", d.root) != 0:
        d.status = 1
    if d.status == 0:
        print("Agent-facing docs and context look consistent")
    return d.status


# Assertion tables. Each tuple is (repo-relative file, expected link target or text).

_COMMON_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/AGENTS.md",
    "docs/agent/index.md",
    "docs/agent/architecture.md",
    "docs/agent/generated-project-index.md",
    "docs/agent/codex-workflows.md",
    "docs/agent/generated-project-verification.md",
    "docs/agent/source-vs-generated.md",
    "docs/agent/verify.md",
    "docs/agent/review.md",
    "docs/template-maintenance.md",
    "docs/template-release.md",
    "docs/exec-plans/README.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/EXAMPLE.md",
    "docs/exec-plans/active/.gitkeep",
    "docs/exec-plans/completed/.gitkeep",
    ".codex/README.md",
    ".agents/skills/README.md",
    ".claude/skills/README.md",
    "env/AGENTS.md",
    "tests/AGENTS.md",
    "scripts/AGENTS.md",
    "src/AGENTS.md",
    "automation/AGENTS.md",
    "automation/context/templates/generated-project-hotspots-summary.md",
    "automation/context/templates/generated-project-recommended-skills.md",
    "automation/context/templates/generated-project-architecture-map.md",
    "automation/context/templates/generated-project-operator-local-runbook.md",
    "automation/context/templates/generated-project-project-map.md",
    "automation/context/templates/generated-project-project-delta-hints.json",
    "automation/context/templates/generated-project-project-delta-hotspots.md",
    "automation/context/templates/generated-project-metadata-index.json",
    "automation/context/templates/generated-project-runtime-support-matrix.json",
    "automation/context/templates/generated-project-runtime-support-matrix.md",
    "automation/context/templates/generated-project-runtime-quickstart.md",
    "automation/context/templates/generated-project-runtime-profile-policy.json",
    "automation/context/templates/generated-project-work-items-readme.md",
    "automation/context/templates/generated-project-work-items-template.md",
    "automation/context/template-managed-paths.txt",
    "scripts/qa/codex-onboard.sh",
)

_SOURCE_CONTEXT_PATHS: tuple[str, ...] = (
    "automation/context/template-source-project-map.md",
    "automation/context/template-source-metadata-index.json",
    "automation/context/template-source-tree.txt",
    "automation/context/template-source-source-files.txt",
)

_GENERATED_PATHS: tuple[str, ...] = (
    "automation/context/project-map.md",
    "automation/context/template-managed-paths.txt",
    "automation/context/source-tree.generated.txt",
    "automation/context/metadata-index.generated.json",
    "automation/context/recommended-skills.generated.md",
    "automation/context/hotspots-summary.generated.md",
    "automation/context/project-delta-hints.json",
    "automation/context/project-delta-hotspots.generated.md",
    "automation/context/runtime-profile-policy.json",
    "automation/context/runtime-support-matrix.json",
    "automation/context/runtime-support-matrix.md",
    "docs/agent/codex-workflows.md",
    "docs/agent/architecture-map.md",
    "docs/agent/operator-local-runbook.md",
    "docs/agent/runtime-quickstart.md",
    "docs/work-items/README.md",
    "docs/work-items/TEMPLATE.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/EXAMPLE.md",
    "env/AGENTS.md",
    "tests/AGENTS.md",
    "scripts/AGENTS.md",
    "src/AGENTS.md",
    "src/README.md",
    "scripts/qa/codex-onboard.sh",
    ".template-overlay-version",
)

_LINKCHECK_COMMON: tuple[str, ...] = (
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/AGENTS.md",
    "docs/agent/index.md",
    "docs/agent/architecture.md",
    "docs/agent/codex-workflows.md",
    "docs/agent/generated-project-index.md",
    "docs/agent/generated-project-verification.md",
    "docs/agent/source-vs-generated.md",
    "docs/agent/verify.md",
    "docs/agent/review.md",
    "docs/template-maintenance.md",
    "docs/template-release.md",
    "docs/exec-plans/README.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/EXAMPLE.md",
    "automation/AGENTS.md",
    ".codex/README.md",
    "env/AGENTS.md",
    "tests/AGENTS.md",
    "scripts/AGENTS.md",
    "src/AGENTS.md",
    ".agents/skills/README.md",
    ".claude/skills/README.md",
)

_LINKCHECK_GENERATED: tuple[str, ...] = (
    "docs/agent/codex-workflows.md",
    "docs/agent/architecture-map.md",
    "docs/agent/operator-local-runbook.md",
    "docs/agent/runtime-quickstart.md",
    "docs/work-items/README.md",
    "docs/work-items/TEMPLATE.md",
    "docs/exec-plans/TEMPLATE.md",
    "docs/exec-plans/EXAMPLE.md",
    "src/AGENTS.md",
)

_SOURCE_PATHS: tuple[str, ...] = (
    "scripts/release/install-source-hooks.sh",
    "scripts/release/publish-overlay-release.sh",
    "scripts/release/lib-source-release.sh",
    ".githooks/pre-push",
)

_COMMON_MARKDOWN_LINK: tuple[tuple[str, str], ...] = (
    ("docs/README.md", "agent/index.md"),
    ("docs/agent/index.md", "../../AGENTS.md"),
    ("docs/agent/index.md", "architecture.md"),
    ("docs/agent/index.md", "generated-project-index.md"),
    ("docs/agent/index.md", "source-vs-generated.md"),
    ("docs/agent/index.md", "verify.md"),
    ("docs/agent/index.md", "review.md"),
    ("docs/agent/index.md", "../template-maintenance.md"),
    ("docs/agent/index.md", "../template-release.md"),
    ("docs/agent/index.md", "../exec-plans/README.md"),
    ("docs/agent/index.md", "../../.agents/skills/README.md"),
    ("docs/agent/index.md", "../../.codex/README.md"),
    ("docs/AGENTS.md", "agent/index.md"),
    ("docs/AGENTS.md", "agent/generated-project-index.md"),
    (".codex/README.md", "../docs/agent/index.md"),
    (".codex/README.md", "../docs/agent/generated-project-index.md"),
    (".codex/README.md", "../docs/agent/codex-workflows.md"),
    (".codex/README.md", "../docs/agent/review.md"),
    (".codex/README.md", "../env/README.md"),
    (".codex/README.md", "../.agents/skills/README.md"),
    (".codex/README.md", "../docs/exec-plans/README.md"),
    (".codex/README.md", "../docs/exec-plans/TEMPLATE.md"),
    (".codex/README.md", "../docs/work-items/README.md"),
    (".agents/skills/README.md", "../../.claude/skills/README.md"),
    (".claude/skills/README.md", "../../.agents/skills/README.md"),
    ("env/AGENTS.md", "README.md"),
    ("tests/AGENTS.md", "../docs/agent/generated-project-verification.md"),
    ("tests/AGENTS.md", "../env/README.md"),
    ("scripts/AGENTS.md", "../docs/agent/generated-project-index.md"),
    ("scripts/AGENTS.md", "../env/README.md"),
    ("src/AGENTS.md", "../docs/agent/generated-project-index.md"),
)

_COMMON_CONTAINS: tuple[tuple[str, str], ...] = (
    ("docs/agent/index.md", "docs/agent/architecture.md"),
    ("docs/agent/index.md", "docs/agent/generated-project-index.md"),
    ("docs/agent/index.md", "docs/agent/source-vs-generated.md"),
    ("docs/agent/index.md", "docs/agent/verify.md"),
    ("docs/agent/index.md", "docs/agent/review.md"),
    ("docs/agent/index.md", "docs/exec-plans/README.md"),
    ("docs/README.md", "docs/agent/generated-project-index.md"),
    ("docs/AGENTS.md", "generated repo"),
    ("automation/AGENTS.md", "automation/context/project-map.md"),
    ("automation/AGENTS.md", "automation/context/recommended-skills.generated.md"),
    ("automation/AGENTS.md", "automation/context/hotspots-summary.generated.md"),
    ("automation/AGENTS.md", "automation/context/metadata-index.generated.json"),
    ("automation/AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("automation/AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("automation/AGENTS.md", "docs/agent/generated-project-index.md"),
    ("env/AGENTS.md", "env/README.md"),
    ("env/AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("env/AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("env/AGENTS.md", "unsupportedReason"),
    ("tests/AGENTS.md", "docs/agent/generated-project-verification.md"),
    ("tests/AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("tests/AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("tests/AGENTS.md", "scripts/qa/check-agent-docs.sh"),
    ("tests/AGENTS.md", "scripts/llm/export-context.sh"),
    ("scripts/AGENTS.md", "docs/agent/generated-project-index.md"),
    ("scripts/AGENTS.md", "automation/context/recommended-skills.generated.md"),
    ("scripts/AGENTS.md", "automation/context/hotspots-summary.generated.md"),
    ("scripts/AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("scripts/AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("scripts/AGENTS.md", "make codex-onboard"),
    ("scripts/AGENTS.md", "scripts/llm/export-context.sh"),
    ("scripts/AGENTS.md", "scripts/qa/check-agent-docs.sh"),
    ("src/AGENTS.md", "automation/context/project-map.md"),
    ("src/AGENTS.md", "automation/context/recommended-skills.generated.md"),
    ("src/AGENTS.md", "automation/context/hotspots-summary.generated.md"),
    ("src/AGENTS.md", "automation/context/project-delta-hotspots.generated.md"),
    ("src/AGENTS.md", "automation/context/metadata-index.generated.json"),
    ("src/AGENTS.md", "docs/agent/architecture-map.md"),
    ("src/AGENTS.md", "docs/agent/runtime-quickstart.md"),
    ("src/AGENTS.md", "src/cf/CommonModules"),
    ("src/AGENTS.md", "src/cf/ScheduledJobs"),
    ("src/README.md", "LoadConfigFromFiles"),
    ("src/README.md", "статического анализа BSL"),
    ("src/README.md", "сравнения изменений в Git"),
    ("docs/agent/generated-project-index.md", "seed-once / project-owned"),
    ("docs/agent/generated-project-index.md", "generated-derived"),
    ("docs/agent/generated-project-index.md", "make codex-onboard"),
    ("docs/agent/generated-project-index.md", "make template-update"),
    ("docs/agent/generated-project-index.md", ".template-overlay-version"),
    ("docs/agent/generated-project-index.md", "docs/agent/codex-workflows.md"),
    ("docs/agent/generated-project-index.md", "docs/agent/operator-local-runbook.md"),
    ("docs/agent/generated-project-index.md", "automation/context/recommended-skills.generated.md"),
    ("docs/agent/generated-project-index.md", "automation/context/hotspots-summary.generated.md"),
    ("docs/agent/generated-project-index.md", "automation/context/project-delta-hotspots.generated.md"),
    ("docs/agent/generated-project-index.md", "automation/context/project-delta-hints.json"),
    ("docs/agent/generated-project-index.md", "automation/context/metadata-index.generated.json"),
    ("docs/agent/generated-project-index.md", "docs/agent/architecture-map.md"),
    ("docs/agent/generated-project-index.md", "docs/agent/runtime-quickstart.md"),
    ("docs/agent/generated-project-index.md", "src/AGENTS.md"),
    ("docs/agent/generated-project-index.md", "src/cf/CommonModules"),
    ("docs/agent/generated-project-index.md", "automation/context/runtime-profile-policy.json"),
    ("docs/agent/generated-project-index.md", "automation/context/runtime-support-matrix.md"),
    ("docs/agent/generated-project-index.md", "OpenSpec"),
    ("docs/agent/generated-project-index.md", "docs/exec-plans/README.md"),
    ("docs/agent/generated-project-index.md", "docs/exec-plans/TEMPLATE.md"),
    ("docs/agent/generated-project-index.md", "docs/work-items/README.md"),
    ("docs/agent/generated-project-index.md", "docs/work-items/TEMPLATE.md"),
    ("docs/agent/generated-project-index.md", "docs/agent/review.md"),
    ("docs/agent/generated-project-index.md", "env/README.md"),
    ("docs/agent/generated-project-index.md", ".agents/skills/README.md"),
    ("docs/agent/generated-project-index.md", ".codex/README.md"),
    ("docs/agent/generated-project-index.md", "project-specific baseline extension"),
    (
        "docs/agent/generated-project-index.md",
        "./scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run",
    ),
    (
        "docs/agent/generated-project-index.md",
        "./scripts/platform/load-task-src.sh --profile <operator-profile> --work-item <id> --run-root /tmp/load-task-src-run",
    ),
    ("docs/agent/source-vs-generated.md", "template-managed"),
    ("docs/agent/source-vs-generated.md", ".template-overlay-version"),
    ("docs/agent/source-vs-generated.md", "generated-derived"),
    ("docs/agent/verify.md", "make agent-verify"),
    ("docs/agent/generated-project-verification.md", "Safe Local"),
    ("docs/agent/generated-project-verification.md", "make export-context-preview"),
    ("docs/agent/generated-project-verification.md", "make export-context-check"),
    ("docs/agent/generated-project-verification.md", "make codex-onboard"),
    ("docs/agent/generated-project-verification.md", "make imported-skills-readiness"),
    ("docs/agent/generated-project-verification.md", "Profile-Required"),
    ("docs/agent/generated-project-verification.md", "Provisioned / Self-Hosted 1C"),
    ("docs/agent/generated-project-verification.md", "./scripts/llm/export-context.sh --write"),
    ("docs/agent/generated-project-verification.md", "unsupportedReason"),
    ("docs/agent/generated-project-verification.md", "runtime-profile-policy.json"),
    ("docs/agent/generated-project-verification.md", "runtime-support-matrix.md"),
    ("docs/agent/generated-project-verification.md", "runtime-quickstart.md"),
    ("docs/agent/generated-project-verification.md", "operator-local-runbook.md"),
    ("docs/agent/generated-project-verification.md", "projectSpecificBaselineExtension"),
    ("docs/template-maintenance.md", "template maintenance"),
    ("docs/template-maintenance.md", "make template-check-update"),
    ("docs/template-maintenance.md", "make template-update"),
    ("docs/template-maintenance.md", "./scripts/template/check-update.sh"),
    ("docs/template-maintenance.md", "./scripts/template/update-template.sh"),
    ("docs/template-maintenance.md", ".template-overlay-version"),
    ("docs/template-maintenance.md", "automation/context/template-managed-paths.txt"),
    ("docs/template-maintenance.md", "src/cf/AGENTS.md"),
    ("docs/template-maintenance.md", "src/cf/README.md"),
    ("docs/template-maintenance.md", "./scripts/llm/export-context.sh --write"),
    ("docs/template-maintenance.md", "tests/smoke/copier-update-ready.sh"),
    ("docs/template-release.md", "source repo шаблона"),
    ("docs/template-release.md", "./scripts/release/install-source-hooks.sh"),
    ("docs/template-release.md", "./scripts/release/publish-overlay-release.sh --tag v0.3.6"),
    ("docs/template-release.md", "origin/main"),
    ("docs/template-release.md", "refs/tags/v*"),
    ("docs/template-release.md", "make agent-verify"),
    (".codex/README.md", "env/README.md"),
    (".codex/README.md", "docs/agent/review.md"),
    (".codex/README.md", "docs/exec-plans/README.md"),
    (".codex/README.md", "docs/exec-plans/TEMPLATE.md"),
    (".codex/README.md", "docs/work-items/README.md"),
    (".codex/README.md", "make codex-onboard"),
    (".codex/README.md", "make imported-skills-readiness"),
    (".codex/README.md", "automation/context/recommended-skills.generated.md"),
    (".codex/README.md", "runtime-support-matrix.md"),
    (".codex/README.md", "docs/agent/runtime-quickstart.md"),
    (".codex/README.md", "docs/agent/codex-workflows.md"),
    (".codex/README.md", "docs/agent/operator-local-runbook.md"),
    ("docs/agent/source-vs-generated.md", "runtime-support-matrix.md"),
    ("docs/agent/source-vs-generated.md", "runtime-support-matrix.json"),
    ("docs/agent/source-vs-generated.md", "docs/work-items/README.md"),
    ("docs/agent/source-vs-generated.md", "docs/work-items/TEMPLATE.md"),
    ("scripts/qa/codex-onboard.sh", "Repository role: generated-project"),
    ("scripts/qa/codex-onboard.sh", "Canonical onboarding router: docs/agent/generated-project-index.md"),
    ("scripts/qa/codex-onboard.sh", "Workflow guide:"),
    ("scripts/qa/codex-onboard.sh", "Architecture map:"),
    ("scripts/qa/codex-onboard.sh", "Operator-local runbook:"),
    ("scripts/qa/codex-onboard.sh", "Runtime quick reference:"),
    ("scripts/qa/codex-onboard.sh", "Runtime support matrix (md):"),
    ("scripts/qa/codex-onboard.sh", "Recommended skills:"),
    ("scripts/qa/codex-onboard.sh", "Project-delta hints:"),
    ("scripts/qa/codex-onboard.sh", "Project-delta hotspots:"),
    ("scripts/qa/codex-onboard.sh", "Project-specific baseline extension:"),
    ("scripts/qa/codex-onboard.sh", "AI-readiness:"),
    ("scripts/qa/codex-onboard.sh", "Codex controls:"),
    ("scripts/qa/codex-onboard.sh", "Planning matrix:"),
    ("scripts/qa/codex-onboard.sh", "docs/exec-plans/TEMPLATE.md"),
    ("scripts/qa/codex-onboard.sh", "docs/work-items/README.md"),
    ("scripts/qa/codex-onboard.sh", "docs/work-items/TEMPLATE.md"),
    ("scripts/qa/codex-onboard.sh", "generated-project-recommended-skills.md"),
    ("scripts/qa/codex-onboard.sh", "Generated-project work-item scaffolds:"),
    ("automation/context/templates/generated-project-metadata-index.json", "runtimeSupportMatrixJsonPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "runtimeSupportMatrixMarkdownPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "recommendedSkillsPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "architectureMapPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "codexWorkflowsPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "operatorLocalRunbookPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "runtimeQuickstartPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "workItemsGuidePath"),
    ("automation/context/templates/generated-project-metadata-index.json", "workItemsTemplatePath"),
    ("automation/context/templates/generated-project-metadata-index.json", "projectDeltaHintsPath"),
    ("automation/context/templates/generated-project-metadata-index.json", "projectDeltaHotspotsPath"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "runtime-support-matrix.md"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "recommended-skills.generated.md"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "project-delta-hotspots.generated.md"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "docs/agent/architecture-map.md"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/templates/generated-project-hotspots-summary.md", "docs/work-items/README.md"),
    ("automation/context/templates/generated-project-operator-local-runbook.md", "runtime-support-matrix.md"),
    (
        "automation/context/templates/generated-project-operator-local-runbook.md",
        "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run",
    ),
    (
        "automation/context/templates/generated-project-operator-local-runbook.md",
        "./scripts/platform/load-task-src.sh --profile env/local.json --work-item 93984 --run-root /tmp/load-task-src-run",
    ),
    ("automation/context/templates/generated-project-architecture-map.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/templates/generated-project-architecture-map.md", "recommended-skills.generated.md"),
    ("automation/context/templates/generated-project-architecture-map.md", "project-delta-hotspots.generated.md"),
    ("automation/context/templates/generated-project-runtime-quickstart.md", "runtime-support-matrix.md"),
    ("automation/context/templates/generated-project-runtime-quickstart.md", "recommended-skills.generated.md"),
    ("automation/context/templates/generated-project-runtime-quickstart.md", "make imported-skills-readiness"),
    ("automation/context/templates/generated-project-runtime-quickstart.md", "operator-local-runbook.md"),
    ("automation/context/templates/generated-project-recommended-skills.md", "recommended-skills.generated.md"),
    ("automation/context/templates/generated-project-recommended-skills.md", "make imported-skills-readiness"),
    ("automation/context/templates/generated-project-work-items-readme.md", "docs/work-items/TEMPLATE.md"),
    ("automation/context/templates/generated-project-work-items-template.md", "docs/exec-plans/active/<task-id>.md"),
    ("automation/context/templates/generated-project-project-map.md", "runtime support truth"),
    ("automation/context/templates/generated-project-project-delta-hints.json", "project-delta-hotspots.generated.md"),
    ("automation/context/templates/generated-project-project-delta-hotspots.md", "project-delta-hints.json"),
    ("automation/context/templates/generated-project-runtime-support-matrix.json", "requiredContourIds"),
    ("automation/context/templates/generated-project-runtime-support-matrix.md", "# Runtime Support Matrix Reference"),
    ("automation/context/templates/generated-project-runtime-support-matrix.md", "projectSpecificBaselineExtension"),
    ("automation/context/templates/generated-project-runtime-support-matrix.md", "bdd-warm-service"),
    ("automation/context/templates/generated-project-operator-local-targets.json", "operatorLocalTargets"),
    ("automation/context/templates/generated-project-runtime-support-matrix.md", "docs/agent/runtime-quickstart.md"),
    (
        "automation/context/templates/generated-project-runtime-support-matrix.md",
        "docs/agent/operator-local-runbook.md",
    ),
    ("automation/context/template-managed-paths.txt", "docs/agent/codex-workflows.md"),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-runtime-support-matrix.json",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-runtime-support-matrix.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-operator-local-targets.json",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-architecture-map.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-recommended-skills.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-operator-local-runbook.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-project-delta-hints.json",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-project-delta-hotspots.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-runtime-quickstart.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-work-items-readme.md",
    ),
    (
        "automation/context/template-managed-paths.txt",
        "automation/context/templates/generated-project-work-items-template.md",
    ),
    ("automation/context/template-managed-paths.txt", "scripts/qa/codex-onboard.sh"),
    ("automation/context/template-managed-paths.txt", "docs/exec-plans/TEMPLATE.md"),
    ("automation/context/template-managed-paths.txt", "docs/exec-plans/EXAMPLE.md"),
    ("automation/context/template-managed-paths.txt", "src/README.md"),
    (".agents/skills/README.md", ".claude/skills/"),
    (".claude/skills/README.md", ".agents/skills/"),
    (".agents/skills/README.md", "1c-load-diff-src"),
    (".agents/skills/README.md", "./scripts/platform/load-diff-src.sh"),
    (".claude/skills/README.md", "1c-load-diff-src"),
    (".claude/skills/README.md", "./scripts/platform/load-diff-src.sh"),
    (".agents/skills/1c-load-diff-src/SKILL.md", "./scripts/platform/load-diff-src.sh"),
    (".agents/skills/1c-load-diff-src/SKILL.md", "--dry-run"),
    (".claude/skills/1c-load-diff-src/SKILL.md", "./scripts/platform/load-diff-src.sh"),
    (".claude/skills/1c-load-diff-src/SKILL.md", "--dry-run"),
    (".agents/skills/README.md", "1c-load-task-src"),
    (".agents/skills/README.md", "./scripts/platform/load-task-src.sh"),
    (".claude/skills/README.md", "1c-load-task-src"),
    (".claude/skills/README.md", "./scripts/platform/load-task-src.sh"),
    (".agents/skills/1c-load-task-src/SKILL.md", "--work-item"),
    (".agents/skills/1c-load-task-src/SKILL.md", "--range"),
    (".agents/skills/1c-load-task-src/SKILL.md", "./scripts/git/task-trailers.sh render --work-item <id>"),
    (".claude/skills/1c-load-task-src/SKILL.md", "--work-item"),
    (".claude/skills/1c-load-task-src/SKILL.md", "--range"),
    (".claude/skills/1c-load-task-src/SKILL.md", "./scripts/git/task-trailers.sh render --work-item <id>"),
    ("docs/exec-plans/README.md", "Progress"),
    ("docs/exec-plans/README.md", "Surprises & Discoveries"),
    ("docs/exec-plans/README.md", "Decision Log"),
    ("docs/exec-plans/README.md", "Outcomes & Retrospective"),
    ("docs/exec-plans/README.md", "TEMPLATE.md"),
    ("docs/exec-plans/README.md", "EXAMPLE.md"),
    ("docs/exec-plans/TEMPLATE.md", "Execution Matrix"),
    ("docs/exec-plans/EXAMPLE.md", "Example Execution Plan"),
)

_SOURCE_MARKDOWN_LINK: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "docs/agent/index.md"),
    ("AGENTS.md", "docs/agent/architecture.md"),
    ("AGENTS.md", "docs/agent/verify.md"),
    ("AGENTS.md", "docs/exec-plans/README.md"),
    ("README.md", "docs/agent/index.md"),
    ("README.md", "docs/template-maintenance.md"),
    ("docs/agent/architecture.md", "../template-release.md"),
)

_SOURCE_CONTAINS: tuple[tuple[str, str], ...] = (
    ("README.md", "1c-runner-agnostic-template"),
    ("README.md", "automation/context/templates/"),
    ("docs/README.md", "automation/context/hotspots-summary.generated.md"),
    ("docs/agent/index.md", "docs/template-release.md"),
    ("docs/agent/architecture.md", "docs/template-release.md"),
    ("docs/agent/architecture.md", "./scripts/release/publish-overlay-release.sh --tag vX.Y.Z"),
    ("docs/template-maintenance.md", "docs/template-release.md"),
)

_GENERATED_MARKDOWN_LINK: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "docs/agent/generated-project-index.md"),
    ("AGENTS.md", "docs/agent/codex-workflows.md"),
    ("AGENTS.md", "automation/context/project-map.md"),
    ("AGENTS.md", "automation/context/recommended-skills.generated.md"),
    ("AGENTS.md", "automation/context/hotspots-summary.generated.md"),
    ("AGENTS.md", "automation/context/metadata-index.generated.json"),
    ("AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("AGENTS.md", "automation/context/runtime-support-matrix.json"),
    ("AGENTS.md", "docs/agent/generated-project-verification.md"),
    ("AGENTS.md", "docs/work-items/README.md"),
    ("AGENTS.md", "docs/template-maintenance.md"),
    ("README.md", "docs/agent/generated-project-index.md"),
    ("README.md", "docs/agent/codex-workflows.md"),
    ("README.md", "automation/context/project-map.md"),
    ("README.md", "docs/agent/architecture-map.md"),
    ("README.md", "docs/agent/operator-local-runbook.md"),
    ("README.md", "docs/agent/runtime-quickstart.md"),
    ("README.md", "automation/context/recommended-skills.generated.md"),
    ("README.md", "automation/context/hotspots-summary.generated.md"),
    ("README.md", "automation/context/project-delta-hotspots.generated.md"),
    ("README.md", "automation/context/metadata-index.generated.json"),
    ("README.md", "automation/context/runtime-profile-policy.json"),
    ("README.md", "automation/context/runtime-support-matrix.md"),
    ("README.md", "automation/context/runtime-support-matrix.json"),
    ("README.md", "docs/agent/generated-project-verification.md"),
    ("README.md", "docs/agent/review.md"),
    ("README.md", "env/README.md"),
    ("README.md", ".agents/skills/README.md"),
    ("README.md", ".codex/README.md"),
    ("README.md", "docs/exec-plans/README.md"),
    ("README.md", "docs/work-items/README.md"),
    ("README.md", "docs/template-maintenance.md"),
)

_GENERATED_CONTAINS: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "generated 1С-project"),
    ("AGENTS.md", "generated-project-first onboarding path"),
    ("AGENTS.md", "make codex-onboard"),
    ("AGENTS.md", "make imported-skills-readiness"),
    ("AGENTS.md", "docs/agent/codex-workflows.md"),
    ("AGENTS.md", "docs/work-items/README.md"),
    ("AGENTS.md", "automation/context/recommended-skills.generated.md"),
    ("AGENTS.md", "automation/context/hotspots-summary.generated.md"),
    ("AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("AGENTS.md", "automation/context/runtime-support-matrix.md"),
    ("AGENTS.md", "./scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run"),
    (
        "AGENTS.md",
        "./scripts/platform/load-task-src.sh --profile <operator-profile> --work-item <id> --run-root /tmp/load-task-src-run",
    ),
    ("README.md", "generated 1С-проект"),
    ("README.md", "Ownership Classes"),
    ("README.md", "make codex-onboard"),
    ("README.md", "make imported-skills-readiness"),
    ("README.md", ".template-overlay-version"),
    ("README.md", "docs/agent/codex-workflows.md"),
    ("README.md", "docs/agent/architecture-map.md"),
    ("README.md", "docs/agent/operator-local-runbook.md"),
    ("README.md", "docs/agent/runtime-quickstart.md"),
    ("README.md", "docs/work-items/README.md"),
    ("README.md", "automation/context/recommended-skills.generated.md"),
    ("README.md", "automation/context/hotspots-summary.generated.md"),
    ("README.md", "automation/context/project-delta-hotspots.generated.md"),
    ("README.md", "automation/context/runtime-profile-policy.json"),
    ("README.md", "automation/context/runtime-support-matrix.md"),
    ("automation/context/project-map.md", "Ownership Model"),
    ("automation/context/project-map.md", "Repo-Derived Snapshot"),
    ("automation/context/project-map.md", "generated-derived"),
    ("automation/context/project-map.md", "docs/agent/codex-workflows.md"),
    ("automation/context/project-map.md", "docs/agent/operator-local-runbook.md"),
    ("automation/context/project-map.md", "automation/context/recommended-skills.generated.md"),
    ("automation/context/project-map.md", "automation/context/project-delta-hints.json"),
    ("automation/context/project-map.md", "automation/context/project-delta-hotspots.generated.md"),
    ("automation/context/project-map.md", "automation/context/runtime-profile-policy.json"),
    ("automation/context/project-map.md", "automation/context/runtime-support-matrix.md"),
    ("automation/context/project-map.md", "docs/agent/architecture-map.md"),
    ("automation/context/project-map.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/project-map.md", "docs/work-items/README.md"),
    ("env/AGENTS.md", "automation/context/runtime-profile-policy.json"),
    ("tests/AGENTS.md", "scripts/qa/check-agent-docs.sh"),
    ("scripts/AGENTS.md", "automation/context/hotspots-summary.generated.md"),
)

_GEN_FUNCS_CONTAINS: tuple[tuple[str, str], ...] = (
    ("automation/context/metadata-index.generated.json", '"entrypointInventory"'),
    ("automation/context/metadata-index.generated.json", '"configurationRoots"'),
    ("automation/context/metadata-index.generated.json", '"httpServices"'),
    ("automation/context/metadata-index.generated.json", '"webServices"'),
    ("automation/context/metadata-index.generated.json", '"scheduledJobs"'),
    ("automation/context/metadata-index.generated.json", '"commonModules"'),
    ("automation/context/metadata-index.generated.json", '"subsystems"'),
    ("automation/context/metadata-index.generated.json", '"architectureMap"'),
    ("automation/context/metadata-index.generated.json", '"codexWorkflows"'),
    ("automation/context/metadata-index.generated.json", '"operatorLocalRunbook"'),
    ("automation/context/metadata-index.generated.json", '"runtimeQuickstart"'),
    ("automation/context/metadata-index.generated.json", '"workItemsGuide"'),
    ("automation/context/metadata-index.generated.json", '"workItemsTemplate"'),
    ("automation/context/metadata-index.generated.json", '"projectDeltaHints"'),
    ("automation/context/metadata-index.generated.json", '"projectDeltaHotspots"'),
    ("automation/context/metadata-index.generated.json", '"review"'),
    ("automation/context/metadata-index.generated.json", '"envReadme"'),
    ("automation/context/metadata-index.generated.json", '"skills"'),
    ("automation/context/metadata-index.generated.json", '"codexGuide"'),
    ("automation/context/metadata-index.generated.json", '"executionPlans"'),
    ("automation/context/metadata-index.generated.json", '"runtimeProfilePolicy"'),
    ("automation/context/metadata-index.generated.json", '"runtimeSupportMatrixJson"'),
    ("automation/context/metadata-index.generated.json", '"runtimeSupportMatrixMarkdown"'),
    ("automation/context/metadata-index.generated.json", '"hotspotsSummary"'),
    ("automation/context/metadata-index.generated.json", '"recommendedSkills"'),
    ("automation/context/recommended-skills.generated.md", "# Generated Recommended Skills"),
    ("automation/context/recommended-skills.generated.md", "## Detected Signals"),
    ("automation/context/recommended-skills.generated.md", "## First-Hour Recommendations"),
    ("automation/context/recommended-skills.generated.md", "## Follow-Up Routers"),
    ("automation/context/recommended-skills.generated.md", ".agents/skills/README.md"),
    ("automation/context/recommended-skills.generated.md", "make imported-skills-readiness"),
    ("automation/context/recommended-skills.generated.md", "./scripts/skills/run-imported-skill.sh --readiness"),
    ("automation/context/recommended-skills.generated.md", "automation/context/project-map.md"),
    ("automation/context/recommended-skills.generated.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/recommended-skills.generated.md", "automation/context/hotspots-summary.generated.md"),
    ("automation/context/recommended-skills.generated.md", "automation/context/metadata-index.generated.json"),
    ("automation/context/hotspots-summary.generated.md", "# Generated Hotspots Summary"),
    ("automation/context/hotspots-summary.generated.md", "## Identity"),
    ("automation/context/hotspots-summary.generated.md", "## Freshness"),
    ("automation/context/hotspots-summary.generated.md", "## High-Signal Counts"),
    ("automation/context/hotspots-summary.generated.md", "## Task-to-Path Routing"),
    ("automation/context/hotspots-summary.generated.md", "## Follow-Up Routers"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/project-map.md"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/recommended-skills.generated.md"),
    ("automation/context/hotspots-summary.generated.md", "docs/agent/architecture-map.md"),
    ("automation/context/hotspots-summary.generated.md", "docs/agent/operator-local-runbook.md"),
    ("automation/context/hotspots-summary.generated.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/hotspots-summary.generated.md", "docs/work-items/README.md"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/project-delta-hotspots.generated.md"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/metadata-index.generated.json"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/runtime-profile-policy.json"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/runtime-support-matrix.md"),
    ("automation/context/hotspots-summary.generated.md", "automation/context/runtime-support-matrix.json"),
    ("automation/context/project-delta-hotspots.generated.md", "# Generated Project-Delta Hotspots"),
    ("automation/context/project-delta-hotspots.generated.md", "## Declared Selectors"),
    ("automation/context/project-delta-hotspots.generated.md", "## Matching Hotspots"),
    ("automation/context/project-delta-hotspots.generated.md", "automation/context/project-delta-hints.json"),
    ("automation/context/project-delta-hotspots.generated.md", "automation/context/project-map.md"),
    ("automation/context/project-delta-hotspots.generated.md", "docs/agent/architecture-map.md"),
    ("automation/context/project-delta-hotspots.generated.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/project-delta-hotspots.generated.md", "automation/context/hotspots-summary.generated.md"),
    ("automation/context/project-delta-hotspots.generated.md", "automation/context/metadata-index.generated.json"),
    ("automation/context/runtime-support-matrix.md", "# Runtime Support Matrix"),
    ("automation/context/runtime-support-matrix.md", "`supported`"),
    ("automation/context/runtime-support-matrix.md", "`unsupported`"),
    ("automation/context/runtime-support-matrix.md", "`operator-local`"),
    ("automation/context/runtime-support-matrix.md", "`provisioned`"),
    ("automation/context/runtime-support-matrix.md", "## Optional Project-Specific Baseline Extension"),
    ("automation/context/runtime-support-matrix.md", "automation/context/project-map.md"),
    ("automation/context/runtime-support-matrix.md", "docs/agent/operator-local-runbook.md"),
    ("automation/context/runtime-support-matrix.md", "docs/agent/runtime-quickstart.md"),
    ("automation/context/runtime-support-matrix.md", "docs/agent/generated-project-index.md"),
    ("automation/context/runtime-support-matrix.md", "docs/agent/generated-project-verification.md"),
    ("docs/agent/architecture-map.md", "# Architecture Map"),
    ("docs/agent/architecture-map.md", "## Representative Change Scenarios"),
    ("docs/agent/architecture-map.md", "## Hot Zones"),
    ("docs/agent/architecture-map.md", "automation/context/project-map.md"),
    ("docs/agent/architecture-map.md", "automation/context/recommended-skills.generated.md"),
    ("docs/agent/architecture-map.md", "automation/context/project-delta-hints.json"),
    ("docs/agent/architecture-map.md", "automation/context/project-delta-hotspots.generated.md"),
    ("docs/agent/architecture-map.md", "automation/context/hotspots-summary.generated.md"),
    ("docs/agent/architecture-map.md", "automation/context/metadata-index.generated.json"),
    ("docs/agent/architecture-map.md", "docs/agent/runtime-quickstart.md"),
    ("docs/agent/codex-workflows.md", "# Codex Workflows"),
    ("docs/agent/codex-workflows.md", "## Planning Path"),
    ("docs/agent/codex-workflows.md", "## Session Controls"),
    ("docs/agent/codex-workflows.md", "## Generated Project Flows"),
    ("docs/agent/codex-workflows.md", "Analysis-Only"),
    ("docs/agent/codex-workflows.md", "Approved Code Work"),
    ("docs/agent/codex-workflows.md", "Long-Running Work"),
    ("docs/agent/codex-workflows.md", "Review-Only"),
    ("docs/agent/codex-workflows.md", "## Skills And MCP"),
    ("docs/agent/codex-workflows.md", "docs/agent/generated-project-index.md"),
    ("docs/agent/codex-workflows.md", "docs/exec-plans/TEMPLATE.md"),
    ("docs/agent/codex-workflows.md", "docs/work-items/README.md"),
    ("docs/agent/codex-workflows.md", "docs/work-items/TEMPLATE.md"),
    ("docs/agent/codex-workflows.md", ".agents/skills/README.md"),
    ("docs/agent/codex-workflows.md", "docs/agent/operator-local-runbook.md"),
    ("docs/work-items/README.md", "# Work Items"),
    ("docs/work-items/README.md", "## Role Separation"),
    ("docs/work-items/README.md", "docs/exec-plans/README.md"),
    ("docs/work-items/README.md", "docs/work-items/TEMPLATE.md"),
    ("docs/work-items/README.md", "docs/agent/codex-workflows.md"),
    ("docs/work-items/README.md", "docs/agent/generated-project-index.md"),
    ("docs/work-items/TEMPLATE.md", "# Work Item Template"),
    ("docs/work-items/TEMPLATE.md", "docs/exec-plans/active/<task-id>.md"),
    ("docs/work-items/TEMPLATE.md", "OpenSpec change / spec"),
    ("docs/work-items/TEMPLATE.md", "## Evidence"),
    ("docs/work-items/TEMPLATE.md", "## Handoff Notes"),
    ("docs/agent/operator-local-runbook.md", "# Operator-Local Runbook"),
    ("docs/agent/operator-local-runbook.md", "## When To Use"),
    ("docs/agent/operator-local-runbook.md", "## Preflight Checklist"),
    ("docs/agent/operator-local-runbook.md", "## Contours"),
    ("docs/agent/operator-local-runbook.md", "automation/context/runtime-support-matrix.md"),
    ("docs/agent/operator-local-runbook.md", "docs/agent/runtime-quickstart.md"),
    ("docs/agent/operator-local-runbook.md", "env/README.md"),
    ("docs/agent/operator-local-runbook.md", "docs/agent/generated-project-verification.md"),
    ("docs/agent/runtime-quickstart.md", "# Runtime Quickstart"),
    ("docs/agent/runtime-quickstart.md", "## Safe Local First Pass"),
    ("docs/agent/runtime-quickstart.md", "## AI-Ready First Pass"),
    ("docs/agent/runtime-quickstart.md", "## Contour Quick Reference"),
    ("docs/agent/runtime-quickstart.md", "## Optional Project-Specific Baseline Extension"),
    ("docs/agent/runtime-quickstart.md", "automation/context/runtime-support-matrix.md"),
    ("docs/agent/runtime-quickstart.md", "automation/context/runtime-support-matrix.json"),
    ("docs/agent/runtime-quickstart.md", "automation/context/recommended-skills.generated.md"),
    ("docs/agent/runtime-quickstart.md", "make imported-skills-readiness"),
    ("docs/agent/runtime-quickstart.md", "docs/agent/generated-project-verification.md"),
    ("docs/agent/runtime-quickstart.md", "docs/agent/operator-local-runbook.md"),
    ("docs/agent/runtime-quickstart.md", "env/README.md"),
    ("docs/agent/runtime-quickstart.md", "docs/agent/architecture-map.md"),
    ("AGENTS.md", "local-only"),
    ("AGENTS.md", "remote-backed"),
    ("README.md", "local-only"),
    ("README.md", "remote-backed"),
    ("docs/agent/generated-project-index.md", "local-only"),
    ("docs/agent/generated-project-index.md", "remote-backed"),
    (".codex/README.md", "local-only"),
    (".codex/README.md", "remote-backed"),
)
