"""Versioned schema-migration framework for synlynk's state.db.

Migrations numbered 1-15 are owned by the legacy consolidated migration in
synlynk/db.py (`_run_legacy_migration_and_repairs`), preserved verbatim for
safety. This package governs migration 16 onward.
"""
from dataclasses import dataclass
from typing import Callable
import sqlite3


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]
