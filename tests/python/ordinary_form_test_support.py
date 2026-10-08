"""Shared prerequisites of the ordinary form conversion tests.

The conversion reads ``Form.bin`` through v8unpack 1.2.6 and validates forms with lxml and jsonschema.
Without these packages plain ``python -m unittest discover`` skips the module instead of failing.
"""

import importlib.util
import unittest

REQUIRED_PACKAGES = ("v8unpack", "lxml", "jsonschema")
MISSING_PACKAGES = [name for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]
if MISSING_PACKAGES:
    raise unittest.SkipTest("ordinary form tests require Python packages: " + ", ".join(MISSING_PACKAGES))
