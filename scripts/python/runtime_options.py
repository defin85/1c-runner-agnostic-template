"""Per-capability one-run options of the profile capabilities (load-src, dump-src, update-db).

Options change a single run only; the runtime profile stays unchanged. A flag that a capability does
not accept is left in argv, so the shared capability parser rejects it as an unknown argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .common import die, project_root, read_json

RUNTIME_POLICY_PATH = "automation/context/runtime-profile-policy.json"

VALUE_OPTIONS = {
    "load-src": {"--source-dir"},
    "dump-src": {"--output-dir"},
    "update-db": {"--vendor-cf"},
}
FLAG_OPTIONS = {
    "load-src": {"--override-unsupported-profile"},
    "dump-src": {"--info-only"},
}


@dataclass(slots=True)
class CapabilityOptions:
    source_dir: str = ""
    output_dir: str = ""
    info_only: bool = False
    vendor_cf: str = ""
    override_unsupported: bool = False


def split_capability_options(capability_id: str, argv: list[str]) -> tuple[CapabilityOptions, list[str]]:
    """Take the options accepted by ``capability_id`` out of argv; return them and the rest."""
    options = CapabilityOptions()
    values = VALUE_OPTIONS.get(capability_id, set())
    flags = FLAG_OPTIONS.get(capability_id, set())
    rest: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in values:
            if index + 1 >= len(argv) or not argv[index + 1]:
                die(f"{arg} requires a value")
            value = argv[index + 1]
            if arg == "--source-dir":
                options.source_dir = value
            elif arg == "--output-dir":
                options.output_dir = value
            else:
                options.vendor_cf = value
            index += 2
            continue
        if arg in flags:
            if arg == "--info-only":
                options.info_only = True
            else:
                options.override_unsupported = True
            index += 1
            continue
        rest.append(arg)
        index += 1
    return options, rest


def unsupported_override_allowed(capability_key: str, profile_path: Path, root: Path | None = None) -> bool:
    """True when the policy lists the profile in ``unsupportedOverride.<key>.allowedProfiles``.

    The override of a profile-level ``unsupportedReason`` is limited to expendable infobases whose
    profiles are listed in the checked-in project policy as ``env/<name>.json``.
    """
    repo_root = (root or project_root()).resolve()
    policy_path = repo_root / RUNTIME_POLICY_PATH
    if not policy_path.is_file():
        return False
    try:
        relpath = profile_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return False
    if not relpath.startswith("env/") or "/" in relpath[len("env/") :] or not relpath.endswith(".json"):
        return False
    payload = read_json(policy_path)
    section = payload.get("unsupportedOverride", {}) if isinstance(payload, dict) else {}
    entry = section.get(capability_key, {}) if isinstance(section, dict) else {}
    allowed = entry.get("allowedProfiles", []) if isinstance(entry, dict) else []
    if not isinstance(allowed, list):
        die(f"unsupportedOverride.{capability_key}.allowedProfiles must be an array in {policy_path}")
    return relpath in {str(item) for item in allowed}


def require_unsupported_override(
    capability_id: str,
    capability_key: str,
    profile_path: Path,
    *,
    reason: str | None,
    selected_files: list[str],
    run_root_input: str,
) -> str:
    """Validate a one-time override of ``unsupportedReason``; return the overridden reason."""
    if capability_id != "load-src":
        die("--override-unsupported-profile is supported only for load-src")
    if not reason:
        die(f"--override-unsupported-profile requires capabilities.{capability_key}.unsupportedReason in the profile")
    if not selected_files:
        die("--override-unsupported-profile requires --files (partial load only)")
    if not run_root_input:
        die("--override-unsupported-profile requires an explicit --run-root")
    if not unsupported_override_allowed(capability_key, profile_path):
        die(
            "--override-unsupported-profile is allowed only for expendable profiles listed in "
            f"{RUNTIME_POLICY_PATH} unsupportedOverride.{capability_key}.allowedProfiles; "
            f"profile is not listed: {profile_path}"
        )
    return reason


def require_vendor_cf(vendor_cf: str, adapter: str, run_root_input: str) -> Path:
    path = Path(vendor_cf)
    if not path.is_file():
        die(f"--vendor-cf file not found: {vendor_cf}")
    if adapter not in {"direct-platform", "remote-windows"}:
        die("--vendor-cf requires the direct-platform or remote-windows adapter")
    if not run_root_input:
        die("--vendor-cf requires --run-root for the Designer /Out log")
    return path.resolve()
