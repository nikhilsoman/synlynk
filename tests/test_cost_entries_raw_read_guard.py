import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+cost_entries\b(?!_)", re.IGNORECASE)

# Writers, schema/migration code and the view definition may touch the raw table.
ALLOWED = {
    "synlynk/migrations",          # directory prefix
    "synlynk/db_schema.py",
    "synlynk/native_capture.py",   # upsert/rescan targets the raw table
    "synlynk/native_backfill.py",
}


def _allowed(rel: str) -> bool:
    return any(rel == a or rel.startswith(a + "/") for a in ALLOWED)


def test_no_raw_cost_entries_reads_outside_allowlist():
    offenders = []
    for path in list((ROOT / "synlynk").rglob("*.py")) + list((ROOT / "bin").glob("*.py")):
        rel = str(path.relative_to(ROOT))
        if _allowed(rel):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if PATTERN.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "read cost_entries_effective instead:\n" + "\n".join(offenders)
