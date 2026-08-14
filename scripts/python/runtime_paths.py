from __future__ import annotations

import os
from pathlib import Path

from .common import canonical_path, project_root


def resolve_project_tree_path(candidate: str) -> Path:
    if os.path.isabs(candidate):
        return canonical_path(candidate)
    return canonical_path(project_root() / candidate)
