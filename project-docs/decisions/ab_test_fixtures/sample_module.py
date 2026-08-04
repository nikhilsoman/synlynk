"""Fixture module for the local-agent A/B test battery.

Each function here is a deliberately small, isolated target for a single-file,
narrowly-scoped edit prompt (docstring add / mechanical rename / small extraction),
per docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
Never edit this file directly as part of real feature work — it exists only to
give the A/B harness a safe, low-stakes, reproducible surface to test against.
"""


def add(a, b):
    """Return the sum of a and b."""
    return a + b


def old_name_needs_rename(x):
    return x * 2


def compute_stats(values):
    total = 0
    count = 0
    for v in values:
        total += v
        count += 1
    average = total / count if count else 0
    return {"total": total, "count": count, "average": average}
