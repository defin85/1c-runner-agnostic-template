"""Project paths that appear only after an optional module is materialized.

Template-shipped skills may name these paths before the module is enabled in a
generated project. Checks treat such a path as absent-by-design while the
module root does not exist, and verify it normally once the module is
materialized.
"""

from __future__ import annotations

from pathlib import Path

# Project-owned roots created by `make optional-module-init MODULE=<name>` (design D1).
# A trailing slash marks a directory root; other entries are single files.
OPTIONAL_MODULE_TARGETS: dict[str, tuple[str, ...]] = {
    "customer-site-operations": ("infra/site/", "docs/infra/site/"),
    "kd21-migration": ("migration/kd21/", "docs/agent/kd21-rules-workbench-runbook.md"),
}

# Fixed extension directories created by `init-test-tooling` under `src/cfe/`.
TEST_TOOLING_TARGETS: tuple[str, ...] = ("src/cfe/VATestContour/", "src/cfe/YAxUnit/", "src/cfe/VAExtension/")


def optional_target_roots() -> tuple[str, ...]:
    roots = [target for targets in OPTIONAL_MODULE_TARGETS.values() for target in targets]
    return (*roots, *TEST_TOOLING_TARGETS)


def owning_optional_root(rel: str) -> str | None:
    normalized = rel.removeprefix("./").replace("\\", "/")
    for root in optional_target_roots():
        if normalized == root.rstrip("/") or (root.endswith("/") and normalized.startswith(root)):
            return root
    return None


def is_unmaterialized_optional_path(repo_root: Path, rel: str) -> bool:
    root = owning_optional_root(rel)
    return root is not None and not (repo_root / root.rstrip("/")).exists()
