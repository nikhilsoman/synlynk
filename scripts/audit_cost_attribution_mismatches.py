"""One-off audit: list cost_entries rows whose harness/model disagree with
their daemon_jobs.actual_harness/resolved_model. Report only -- does not
modify any row. gh:#2547."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import synlynk


def main():
    conn = synlynk._get_db()
    rows = conn.execute(
        """SELECT ce.id, ce.job_id, ce.harness, ce.model,
                  dj.actual_harness, dj.resolved_model
           FROM cost_entries ce
           JOIN daemon_jobs dj ON ce.job_id = dj.job_id
           WHERE dj.actual_harness IS NOT NULL
             AND ce.harness IS NOT NULL
             AND ce.harness != dj.actual_harness"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No harness-attribution mismatches found.")
        return 0
    print(f"{len(rows)} mismatched cost_entries rows:")
    for r in rows:
        print(f"  cost_entries.id={r[0]} job_id={r[1]} "
              f"cost_entries.harness={r[2]!r} vs daemon_jobs.actual_harness={r[4]!r} "
              f"(model {r[3]!r} vs {r[5]!r})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
