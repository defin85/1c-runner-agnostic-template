"""KD 2.01 rules compiler core.

The core builds a release from neutral metadata structures and explicit rule nodes. It must not import
the stage executor (`scripts.migration.kd_cycle_*`) or project modules; `tests/python/test_kd_xml_compiler.py`
checks this boundary.
"""

from .compiler import exchange_document, registration_document
from .metadata import Configuration, MetadataField, MetadataObject, load_structure
from .release import DOCUMENT_ROLES, ReleaseError, RuleProvider, TechnicalRules, compile_release, validate_matrix

__all__ = [
    "DOCUMENT_ROLES",
    "Configuration",
    "MetadataField",
    "MetadataObject",
    "ReleaseError",
    "RuleProvider",
    "TechnicalRules",
    "compile_release",
    "exchange_document",
    "load_structure",
    "registration_document",
    "validate_matrix",
]
