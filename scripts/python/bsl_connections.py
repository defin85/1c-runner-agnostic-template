"""Resolve BSL Analyzer registry entries that reference an infobase runtime profile.

An entry with the ``profile`` key takes the user and the password variable name from ``infobase.auth``
of that profile, so the profile stays the single source of access parameters. The user is passed to
the analyzer through a separate environment variable because the registry accepts only variable names.
Passwords are never read or written here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .runtime_errors import CommandError


def user_env_name(connection: str) -> str:
    return "BSL_ONEC_USER__" + re.sub(r"[^A-Z0-9]", "_", connection.upper())


def resolve_profile_connections(registry: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Return the registry with ``profile`` entries replaced by env references and the user values."""
    connections = registry.get("connections")
    if not isinstance(connections, dict):
        raise CommandError("BSL Analyzer connection registry must contain a connections object")
    resolved: dict[str, Any] = {}
    users: dict[str, str] = {}
    for name, value in connections.items():
        if not isinstance(value, dict):
            raise CommandError(f"BSL Analyzer connection is invalid: {name}")
        entry = dict(value)
        profile_ref = entry.pop("profile", None)
        if profile_ref is not None:
            if "user_env" in entry or "password_env" in entry:
                raise CommandError(f"{name}: profile cannot be combined with user_env/password_env")
            path = Path(str(profile_ref))
            path = path if path.is_absolute() else root / path
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise CommandError(f"{name}: runtime profile cannot be read: {path}: {error}") from error
            infobase = profile.get("infobase") if isinstance(profile, dict) else None
            auth = infobase.get("auth") if isinstance(infobase, dict) else None
            auth = auth if isinstance(auth, dict) else {}
            user, password_env = auth.get("user"), auth.get("passwordEnv")
            if not isinstance(user, str) or not user or not isinstance(password_env, str) or not password_env:
                raise CommandError(f"{name}: profile has no infobase.auth.user/passwordEnv")
            if "\t" in user or "\n" in user:
                raise CommandError(f"{name}: invalid user name in profile")
            env_name = user_env_name(name)
            entry["user_env"], entry["password_env"] = env_name, password_env
            users[env_name] = user
        if "password" in entry:
            raise CommandError(f"{name}: passwords are not allowed in the registry")
        resolved[name] = entry
    return {**registry, "connections": resolved}, users
