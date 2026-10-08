"""Shared prerequisites of the metadata CLI tests.

The tests use pytest, lxml and jsonschema. Plain ``python -m unittest discover`` imports every
``test_*.py`` module, so a missing package skips the module instead of failing the whole run.
"""

import importlib.util
import os
import unittest
from pathlib import Path

REQUIRED_PACKAGES = ("pytest", "lxml", "jsonschema")
MISSING_PACKAGES = [name for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]
if MISSING_PACKAGES:
    raise unittest.SkipTest("metadata CLI tests require Python packages: " + ", ".join(MISSING_PACKAGES))

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def designer_export(*required: str) -> Path:
    """Return the BP 3.0 Designer export root or skip the test when a required path is absent.

    The export is not part of the template. Set METADATA_DESIGNER_EXPORTS to its root;
    by default the main configuration root ``src/cf`` of the project is used.
    """
    import pytest

    root = Path(os.environ.get("METADATA_DESIGNER_EXPORTS") or PROJECT_ROOT / "src" / "cf").resolve()
    missing = [item for item in required if not (root / item).exists()]
    if missing:
        pytest.skip(f"Designer export lacks {missing[0]} under {root}; set METADATA_DESIGNER_EXPORTS")
    return root


def present[T](value: T | None) -> T:
    """Return a value that the test expects to exist; a missing value fails the test with AssertionError."""
    assert value is not None
    return value
