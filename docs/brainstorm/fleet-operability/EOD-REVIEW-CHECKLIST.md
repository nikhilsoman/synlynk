# Fleet operability — EOD review checklist

**Purpose:** Daily end-of-day check for one week after #661/#667/#670 so Supported/Proven does not silently rot.

**Cadence:** EOD each day through ~2026-08-09 (auto reminder scheduled in Grok Build; tasks expire after 7 days).

**Repo:** `~/dev/synlynk` on `main` (pull first).

---

## Commands (copy-paste)

```bash
cd ~/dev/synlynk
git pull origin main --ff-only

python3 -m synlynk selftest --matrix
python3 -m synlynk doctor 2>&1 | tee /tmp/synlynk-eod-doctor.txt | tail -40
python3 -m synlynk status 2>&1 | head -30

python3 - <<'PY'
from synlynk.fleet import find_nested_product_state_dbs
n = find_nested_product_state_dbs('.')
print(f'nested product state.db count: {n}')
if n:
    for p in n[:20]:
        print(' ', p)
    if len(n) > 20:
        print(f'  ... +{len(n)-20} more')
PY
```

Optional (costs $; only if you want Proven refreshed this week):

```bash
python3 -m synlynk selftest --matrix --live --budget 2
```

---

## Pass criteria

| Check | Pass |
|-------|------|
| Dry matrix | exit **0**, **0** tier-1 red |
| Nested product DBs | count **0** |
| Core 4 doctor TC-2 | ✓ for claude / agy / codex / grok |
| Status TIER | Core 4 **supported** or **proven** (not unsupported) |
| local | experimental failures OK to ignore |

---

## If something fails

1. **Nested DBs reappeared** — list paths; purge only under finished job worktrees; note whether #670 fallback/purge missed a path; file issue if systematic.
2. **Dry matrix red (other cells)** — instruction missing / baseline drift; fix or open issue before Phase 3.
3. **Codex TC-2 red again** — flag rename/drift; check `AGENT_CAPABILITY_BASELINES['codex']` vs `codex --help`.
4. **Proven went stale** (>7d without live green) — run live matrix with budget, or accept supported-only until next live run.

---

## Week goal (not blocking)

- Quiet CI dry matrix on real PRs
- No nested product state.db growth under `worktrees/` / `.worktrees/`
- Decide by ~2026-08-09: start Phase 3 design (GH-write + grants) or park fleet

## Related

- Spec: `docs/superpowers/specs/2026-08-02-fleet-operability-design.md`
- PRs: #661 (truth gate), #667 (codex TC-2), #670 (CI + hygiene + live smoke)
