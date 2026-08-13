from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_errors import CommandError


@dataclass(slots=True)
class ResourceLock:
    path: Path
    owner: dict[str, Any]
    timeout: float = 30.0
    poll_interval: float = 0.05
    _owned: bool = False

    def acquire(self) -> "ResourceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        payload = json.dumps(self.owner, ensure_ascii=False, sort_keys=True).encode("utf-8")
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(descriptor, payload)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                self._owned = True
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise CommandError(f"resource lock timeout: {self.path}")
                time.sleep(self.poll_interval)

    def release(self) -> None:
        if not self._owned:
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._owned = False
            raise CommandError(f"resource lock ownership cannot be verified: {self.path}")
        if current != self.owner:
            self._owned = False
            raise CommandError(f"resource lock owner changed: {self.path}")
        self.path.unlink()
        self._owned = False

    def __enter__(self) -> "ResourceLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
