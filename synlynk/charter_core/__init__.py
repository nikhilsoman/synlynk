"""Extraction-ready Charter v3.0 core.

The package intentionally contains no imports from the wider ``synlynk``
package so it can be extracted as a standalone schema/validation library.
"""

from synlynk.charter_core.schema import (
    CHARTER_V3_REQUIRED_BLOCKS,
    VALID_AUTONOMY_LEVELS,
    VALID_OPERATIONS,
    VALID_TRANSPORTS,
    validate_structure,
)

__all__ = [
    "CHARTER_V3_REQUIRED_BLOCKS",
    "VALID_AUTONOMY_LEVELS",
    "VALID_OPERATIONS",
    "VALID_TRANSPORTS",
    "validate_structure",
]
