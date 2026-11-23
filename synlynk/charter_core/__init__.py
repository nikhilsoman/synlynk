"""Extraction-ready Charter v3.0 core: schema, strict-YAML parsing, structural validation.

Zero synlynk-package imports by design (standalone-extraction-readiness constraint,
docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md).
"""
from synlynk.charter_core.yaml_subset import parse_yaml, dump_yaml  # noqa: F401
from synlynk.charter_core.schema import (  # noqa: F401
    CHARTER_V3_REQUIRED_BLOCKS,
    VALID_OPERATIONS,
    VALID_TRANSPORTS,
    VALID_AUTONOMY_LEVELS,
    validate_structure,
)
