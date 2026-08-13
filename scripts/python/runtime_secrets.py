from __future__ import annotations

import os
from typing import Any, Protocol

from .common import die


class ProfileView(Protocol):
    name: str

    def string(self, *keys: str, default: str = "") -> str: ...


def resolve_secret_value(env_name: str, dry_run: bool = False) -> str:
    if not env_name:
        return ""
    if env_name in os.environ:
        return os.environ[env_name]
    if dry_run:
        return "__REDACTED_SECRET__"
    die(f"required secret env var is not set: {env_name}")


def build_redacted_context(profile: ProfileView | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "runtime_profile": {"name": profile.name or None},
        "infobase": {
            "mode": profile.string("infobase", "mode") or None,
            "server": profile.string("infobase", "server") or None,
            "ref": profile.string("infobase", "ref") or None,
            "file_path": profile.string("infobase", "filePath") or None,
            "auth_mode": profile.string("infobase", "auth", "mode", default="os") or None,
        },
    }
