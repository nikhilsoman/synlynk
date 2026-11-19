# Harness Routing & Manifest Mechanics — Design (Redesign of PR #5340)

## Status

Supersedes the rejected PR #5340 (`docs/superpowers/specs/2026-11-17-harness-parity-phase3-mechanics-design.md` +
its plan) in its entirety. That branch/worktree (`chore/claude/harness-parity-phase3-mechanics-design`) is
abandoned — do not resume it. This spec is "Spec A" of a two-spec split; "Spec B" (cross-harness
instruction-adherence verification, issue #5353) is sequenced after this one and is out of scope here.

## Why the rewrite

Codex's non-authoring review of PR #5340 (job-1228d917) returned CHANGES_REQUESTED with four blocking
findings. Rather than patch the rejected spec, the owner asked for the entire problem space to be
re-investigated. In the course of that:

- A second decide panel (claude/agy/codex/muse) simplified the governing decision's bootstrap mechanic
  (`project-docs/decisions/2026-11-17-second-amendment-to-dec-6da80f2a-harness.md`, decision `dec-8ed62afa`),
  replacing a global 25-task bootstrap window with a **per-cell floor-of-5 rule**. This directly resolves
  Finding 1.
- Muse's real billing rate was tracked down from `dev.meta.ai/docs/pricing-rate-limits` (Standard tier,
  Contributor rates confirmed no longer offered). This resolves Finding 2, and surfaces that the same
  placeholder bug exists live today in `synlynk/costs.py:695`, not just in the rejected spec.
- Direct code reading in `synlynk/dispatch.py` and `synlynk/capability_probe.py` found the real call
  sites for Findings 3 and 4, which the rejected plan had deferred as "to be discovered later." This
  spec cites those real locations throughout.

## Governing decisions (binding, not re-litigated here)

- `dec-6da80f2a` (2026-11-16): Phase 1/2 scope boundary; GOVERNS preflight-only enforcement flagged
  insufficient; no instruction file may hard-pin a role/task-type lane.
- `dec-0a6db720` (2026-11-17, first amendment): Capability-Based Task Allocation is **retained** as binding
  routing authority, not retired. PM-approved canaried fold-back (auto-promote only above n≥5 + ≥1.5x IQR
  margin) stands.
- `dec-8ed62afa` (2026-11-17/18, second amendment): bootstrap mechanic is a **per-cell floor-of-5 rule** —
  no global counter, no campaign/exhaustion event, no cross-cell budget. Reuses the existing CLAUDE.md
  n≥5 floor. Inline per-dispatch query against `capability_ratings`, no cache (row count per cell caps at
  5 before permanent graduation, so cost never grows). Tie-break among sub-floor harnesses for the same
  cell via a persisted per-cell round-robin rotation pointer, advanced only on dispatch to that cell.

This spec implements those decisions; it does not re-decide them.

---

## Section 1 — Eligibility vs. routing split

**Decision (resolved via AskUserQuestion, this session):** keep the Capability-Based Task Allocation table
in CLAUDE.md/AGENTS.md/GEMINI.md as-is — it is the real routing source above the floor, per `dec-0a6db720`.
Do not delete it (the rejected plan's mistake). Add one short paragraph beneath it describing the per-cell
floor-of-5 round-robin exception, so the instruction files stay consistent with what `routing.py` actually
does.

Separately from that table, add a static **eligibility** gate: a hard yes/no on whether a harness can
*possibly* run a given task type at all, independent of ranking preference. This is not new — it already
exists piecemeal as the `_dispatch_capability_preflight`/`_preflight_dispatch` rejection sites in
`dispatch.py` (see Section 7's inventory) — this section just names it as a concept so Section 2's router
has a well-defined "eligible set" to rank or rotate over. No new `.synlynk/capability-roles.json` file and
no deletion of `overrides.dev_authority.task_allocation` (that was the rejected plan's Finding-1 mistake).

**Concretely:**
- `policy.json` gains a new top-level `eligibility` block only as a place to *record* static eligibility
  facts already implied by `HARNESS_CAPABILITY_BASELINES` (e.g. `can_gh_write`) — not a new enforcement
  mechanism. This is additive; nothing existing is removed.
- `overrides.role_task_type_compat` is unchanged.
- File a tech-debt ticket for instruction-file-duplication centralization (CLAUDE.md/AGENTS.md/GEMINI.md
  all carry the same table) — do not build a templating system in this PR. YAGNI.

## Section 2 — Live capability-based routing (`routing.py`)

New `synlynk/routing.py`:

```python
"""Routes an 'auto' dispatch to a harness for a given task_type.

Two branches only, per dec-8ed62afa (second amendment): table-ranked above
the floor, round-robin below it. No global window, no budget, no exhaustion
event — each (harness, task_type) cell graduates independently.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Protocol

SAMPLE_SIZE_FLOOR = 5  # same floor as the Empirical Capability Assessment Policy (CLAUDE.md)

# Per-task_type cost normalization so pr_review_cycles (a small integer) and
# total_cost_usd (dollars, can be $1-$100+) are comparable in one score.
SCORE_COST_DIVISOR = {
    "implement": 10.0,
    "test": 10.0,
    "refactor": 10.0,
    "css": 5.0,
    "templates": 5.0,
    "content": 5.0,
    "subpages": 5.0,
    "canvas": 10.0,
    "js": 10.0,
    "infra": 15.0,
    "cli-plumbing": 10.0,
    "review": 5.0,
    "deploy": 15.0,
    "pm": 5.0,
    "brainstorm": 5.0,
}
_DEFAULT_COST_DIVISOR = 10.0


@dataclass(frozen=True)
class HarnessScore:
    harness: str
    sample_count: int
    median_pr_review_cycles: float
    median_total_cost_usd: float

    @property
    def score(self) -> float:
        divisor = SCORE_COST_DIVISOR.get(self._task_type, _DEFAULT_COST_DIVISOR) if hasattr(self, "_task_type") else _DEFAULT_COST_DIVISOR
        return self.median_pr_review_cycles + (self.median_total_cost_usd / divisor)


class Router(Protocol):
    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str: ...


def _sample_count(db_conn: sqlite3.Connection, harness: str, task_type: str) -> int:
    row = db_conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND task_type=?",
        (harness, task_type),
    ).fetchone()
    return row[0] if row else 0


def _median_scores(db_conn: sqlite3.Connection, harness: str, task_type: str) -> tuple[float, float]:
    cycles_rows = db_conn.execute(
        "SELECT pr_review_cycles FROM capability_ratings "
        "WHERE agent=? AND task_type=? AND pr_review_cycles IS NOT NULL "
        "ORDER BY pr_review_cycles",
        (harness, task_type),
    ).fetchall()
    cost_rows = db_conn.execute(
        "SELECT total_cost_usd FROM cost_entries "
        "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL "
        "ORDER BY total_cost_usd",
        (harness, task_type),
    ).fetchall()

    def _median(rows: list[tuple]) -> float:
        if not rows:
            return 0.0
        values = [r[0] for r in rows]
        mid = len(values) // 2
        if len(values) % 2:
            return float(values[mid])
        return float(values[mid - 1] + values[mid]) / 2.0

    return _median([r for r in cycles_rows]), _median([r for r in cost_rows])


def _next_rotation_index(db_conn: sqlite3.Connection, task_type: str, eligible_count: int) -> int:
    row = db_conn.execute(
        "SELECT rotation_index FROM routing_rotation_state WHERE task_type=?",
        (task_type,),
    ).fetchone()
    current = row[0] if row else 0
    next_index = (current + 1) % max(eligible_count, 1)
    db_conn.execute(
        "INSERT INTO routing_rotation_state (task_type, rotation_index) VALUES (?, ?) "
        "ON CONFLICT(task_type) DO UPDATE SET rotation_index=excluded.rotation_index",
        (task_type, next_index),
    )
    db_conn.commit()
    return current


class LiveQueryRouter:
    """Two branches only: table-ranked (n>=5) or round-robin (n<5), per dec-8ed62afa."""

    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str:
        if not eligible_harnesses:
            raise ValueError(f"No eligible harness for task_type={task_type!r}")

        sub_floor = []
        scored = []
        for harness in sorted(eligible_harnesses):  # alphabetical for deterministic tie-break
            n = _sample_count(db_conn, harness, task_type)
            if n < SAMPLE_SIZE_FLOOR:
                sub_floor.append(harness)
            else:
                cycles, cost = _median_scores(db_conn, harness, task_type)
                divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_COST_DIVISOR)
                scored.append((cycles + cost / divisor, n, harness))

        if sub_floor:
            # Round-robin exploration: only harnesses still below the floor for
            # this specific cell are candidates. Pure rotation, no preference
            # weighting (dec-8ed62afa panel position, unanimous).
            idx = _next_rotation_index(db_conn, task_type, len(sub_floor))
            return sub_floor[idx % len(sub_floor)]

        # All eligible harnesses are at/above the floor: table-ranked routing.
        # Deterministic tie-break: lowest score, then higher sample_count, then alphabetical.
        scored.sort(key=lambda t: (t[0], -t[1], t[2]))
        return scored[0][2]
```

**Migration** (`synlynk/migrations/m0035_routing_rotation_state.py`, following the `m0034` template read
from this repo):

```python
"""Migration 35: per-cell round-robin rotation state for sub-floor harness exploration.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md Section 2.
Replaces the global-bootstrap-window machinery rejected in PR #5340 with a
per-(harness, task_type)-cell floor-of-5 rule (dec-8ed62afa).
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS routing_rotation_state (
            task_type      TEXT PRIMARY KEY,
            rotation_index INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task "
        "ON capability_ratings(agent, task_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_task "
        "ON cost_entries(agent, type_id)"
    )


MIGRATION = Migration(version=35, name="routing_rotation_state", up=_up)
```

Wiring: `dispatch.py`'s `"auto"` resolution path (the branch that currently falls through to a hardcoded
default when no explicit `--agent` is given) calls `LiveQueryRouter().select(eligible, task_type, db_conn)`
instead. `eligible` is produced by the Section 1 static gate (e.g. exclude agents failing
`can_gh_write` for a `requires_gh_write` task), not by this router.

## Section 3 — Harness manifest + onboarding/probe commands

Carried over from PR #5340's Section 3 (not challenged by Codex's review). `.synlynk/harnesses/{harness}.json`:

```json
{
  "manifest_schema_version": 1,
  "harness": "muse",
  "models": ["muse-spark-1.3"],
  "native_cli_flags": {"approval_mode": "never"},
  "auth_model": "subscription",
  "mcp_tools": [],
  "cli_version_hash": "sha256:...",
  "last_validated_smoke_run": {"status": "ok", "at": "2026-11-18T00:00:00Z"}
}
```

New `synlynk/harness_manifest.py:discover_and_validate(harness: str) -> dict`, shared by two new CLI
subcommands wired the same way this repo's existing `tool`/`spec`/`connector` subcommands are (grep
`synlynk/cli.py` for `add_parser("tool"` — nested `add_subparsers(dest=...)` pattern):

```python
harness_parser = subparsers.add_parser("harness", help="Manage per-harness manifests")
harness_sub = harness_parser.add_subparsers(dest="harness_action")
onboard_parser = harness_sub.add_parser("onboard", help="Create/refresh a harness manifest")
onboard_parser.add_argument("--harness", required=True)
probe_parser = harness_sub.add_parser("probe", help="Validate an existing harness manifest")
probe_parser.add_argument("--harness", required=True)
probe_parser.add_argument("--discover", action="store_true")
```

`discover_and_validate` includes the Amendment-4 billing-field validation step: if the harness's billing
mode is `per_token` (not `subscription`), the manifest/`.synlynk/billing.json` must carry a non-placeholder
`cost_per_1k_tokens` block, or validation fails with `HARNESS_BILLING_CONFIG_INVALID`. This is where the
real Muse rate from Section 5 below gets consumed.

## Section 4 — CLI-version-triggered rediscovery

Carried over from PR #5340 (not challenged). Preflight check in `_preflight_dispatch` (`dispatch.py`,
~line 4121 where `baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})` already reads a cached
`harness_records` row): compare the installed CLI's version hash against the manifest's
`cli_version_hash`. On mismatch, return `{"passed": False, "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED", ...}`
unless `--force-harness`. If no manifest exists at all for a harness being dispatched, trigger
`discover_and_validate` inline rather than failing — first-run convenience, not a second code path.

## Section 5 — Muse budget-ledger fix (real rate, real bug)

**Real bug, live today:** `synlynk/costs.py:695` maps `"muse-spark-1.3"` to `_DEFAULT_MODEL_RATE`
(`{"input": 0.003, "output": 0.015, "cache_read": 0.0000003}`) — a generic Claude-Sonnet-shaped
placeholder, not a Muse-specific rate. `synlynk/models.py:156,164` confirm `"muse"` resolves to
`"muse-spark-1.3"`, so every Muse cost entry today is silently mis-costed.

**Fix:** update `_HARDCODED_FALLBACK_RATES["muse-spark-1.3"]` in `costs.py` to the real, user-confirmed
Muse Spark Standard rate (Contributor rates confirmed no longer offered — do not use them), converted to
this repo's `_EXPECTED_RATE_UNIT = "usd_per_1k_tokens"` from Meta's published per-1M rate
(`dev.meta.ai/docs/pricing-rate-limits`, fetched 2026-11-18):

```python
"muse-spark-1.3": {"input": 0.00125, "output": 0.00425, "cache_read": 0.00015},
```

Separately, the budget-ledger bug PR #5340 flagged: a harness fundable only via `credit_grants` (not
`harness_status`/`TIER1_CAPACITY`) is invisibly budget-blocked. Fix in `dispatch.py`'s budget preflight
(~4232-4267, the `CAPACITY_EXCEEDED_INPUT`/`CAPACITY_EXCEEDED_OUTPUT` sentinel sites): add a
`_billing_rate_per_1k_tokens(harness)` helper that checks `credit_grants` as a fallback source of funding
when `harness_status`/`TIER1_CAPACITY` has no entry, before concluding the harness is unfundable. The
user's own billing mode (₹399/month flat subscription, Standard tier, not Contributor) should resolve via
`.synlynk/billing.json`'s existing subscription-mode path — this fix only adds the `credit_grants` fallback
for non-subscription harnesses that currently fall through with no funding source at all.

**Addendum (resolved during planning, 2026-11-18, flagged by Codex review of PR #5369):** this
`credit_grants`-fallback requirement is **already satisfied by existing code** — `synlynk/quota.py:984-1063`
(`_unexpired_credit_remaining` + `provider_pool_preflight`, wired into the budget preflight at
`synlynk/dispatch.py:5060`) already sums `credit_grants` as a fallback funding source whenever a harness
has no subscription-track quota row, and this path is already live. The implementation plan's Task 8
therefore fixes only the `_HARDCODED_FALLBACK_RATES["muse-spark-1.3"]` constant above; it does not add a
new `_billing_rate_per_1k_tokens` helper, since that would duplicate `provider_pool_preflight`'s existing
fallback rather than close a real gap.

## Section 6 — Local-harness reroute fix (real call site)

**Real call site found by direct code reading**, `synlynk/dispatch.py`, inside `dispatch_agent()`:

```
request = pipeline.resolve(request)
pipeline.authorize(request)
probed_agent = take_probed_dispatch_harness()
initial_agent = agent
agent = request.agent                                          # <- line 4773
if local_pilot_requested and agent == "local" and not local_pilot_receipt:
    raise RuntimeError(...)                                     # line 4774
if agent != initial_agent and not force_agent:
    print(_capability_reroute_message(initial_agent, agent, probed_agent))  # line 4780
```

This already prints a reroute message — it is not fully silent. The actual gap (confirmed by checking
every `INSERT INTO cost_entries`/`capability_ratings` call site in `db.py`, `capability_sweep.py`,
`jobs.py`, `role_activation_seed.py`, `local_agent_seed.py`) is that **no insert threads `initial_agent`
separately from `agent`** — every cost/capability row records only the post-reroute harness, so a
local→X substitution is attributed entirely to X with no trace that `local` was ever requested.

**Fix:**
1. New `--allow-reroute` CLI flag on `dispatch`. Without it, `dispatch_agent()` fails closed when
   `agent != initial_agent` and the mismatch is a silent substitution (not an explicit
   `--requires-gh-write`/Grok-sandbox-denial reroute, which already print and are intentional) — i.e. the
   specific case this finding concerns is `initial_agent == "local"`.
2. Add a `requested_harness` column (nullable, defaults to `agent` when unset) to `cost_entries` and
   `capability_ratings` via a migration in the same family as `m0035`. Thread `initial_agent` from
   `dispatch_agent()` into the job record alongside `agent`, so both the requested and actual harness are
   persisted.
3. `synlynk jobs`/`synlynk status` display: when `requested_harness != agent`, render
   `"<agent> (rerouted from <requested_harness>)"` instead of just `<agent>`. This is a real display
   change in `synlynk/status.py`, not a new display-formatting test that recreates the logic — the test
   for this must call the actual rendering function and assert on its real output string.

## Section 7 — MCP parity & rejection-site audit

**Correcting the rejected plan's premise:** there is no `_probe_mcp_tools` function in
`capability_probe.py` — that file has zero MCP-related code. The real MCP logic is:
- `synlynk/probe.py:337-339` — detects `.mcp.json`/`mcp.json`, adds `"mcp"` to a repo's `requirements` set.
- `synlynk/dispatch.py:4108-4119` — the actual rejection site: for Agy with `mcp`/`stitch` in
  `declared_requires`, calls `doctor._run_tc8()`; on failure returns
  `{"passed": False, "sentinel": "MCP_SERVER_MISSING", "reason": ...}`.

`discover_and_validate` (Section 3) adds an MCP smoke-run step for any harness declaring MCP tools in its
manifest, using this same `_run_tc8`-style check rather than inventing a new probe.

**Rejection-site audit (real inventory, read directly from `dispatch.py`'s preflight functions, not
deferred):**

| Sentinel | Site(s) | Legitimate reason |
|---|---|---|
| `HARNESS_PREFLIGHT_FAIL` | `dispatch.py:3439,3457,3466,3480,3570,3580,4163,4181,4188,4209` | generic harness-specific preflight failure (binary missing, auth expired, etc.) |
| `LOCAL_CAPABILITY_UNAVAILABLE` | `dispatch.py:4033,4043,4053,4063` | local harness's declared capability not actually available on this machine |
| `LOCAL_ORBSTACK_UNAVAILABLE` | `dispatch.py:4090` | local harness needs OrbStack; not running |
| `INSTRUCTION_FILE_MISSING` | `dispatch.py:4104` | Core-4 agent missing its required instruction file (LIVE-1/#343 class) |
| `MCP_SERVER_MISSING` | `dispatch.py:4117` | declared MCP/Stitch requirement not satisfied |
| `CAPACITY_EXCEEDED_INPUT`/`_OUTPUT` | `dispatch.py:4257,4267` | budget/quota exhausted (Section 5 fixes a gap here, not the sentinel itself) |
| `GOVERNS_LINKAGE_MISSING` | `dispatch.py:4314` | dispatched job has no linked GOVERNS goal/story |

Each of these 7 sentinels already maps to a legitimate, named reason — the audit's actual deliverable is
confirming this table is accurate (done, above) and fixing any site where a rejection reason is *not*
one of these seven, which requires reading `_dispatch_capability_preflight`/`_preflight_dispatch` in full
during implementation and diffing against this table, not filing a ticket to look at it "later."

---

## Explicitly out of scope

- Spec B (#5353, cross-harness instruction-adherence verification) — separate, sequenced spec.
- Instruction-file-duplication templating system (Section 1) — ticket only.
- Any change to the n≥5 floor value or the PM-approved canaried fold-back gate — both are settled by
  `dec-0a6db720`/`dec-8ed62afa` and not reopened here.
