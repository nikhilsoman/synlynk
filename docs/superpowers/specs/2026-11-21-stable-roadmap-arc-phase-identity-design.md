# Stable Roadmap Arc/Phase Identity (Approach C)

> **Revision history:** v1 (this file's original content) was reviewed by a `synlynk decide` panel
> (claude, agy, codex, grok) on 2026-11-21 against the goal of pre-ship flexibility + multi-domain
> reuse; decision recorded in `project-docs/decisions/2026-11-21-review-the-committed-spec-docs-superpowe.md`.
> The panel endorsed the core `arc_uid`/`phase_uid`-on-`goals` approach but found v1's regroup
> semantics, uid lifecycle, and domain-generality underspecified. This is v2, addressing each
> finding. Sections marked **[v2]** are new or substantially rewritten; everything else is
> unchanged from v1.

## Problem

`gh:#5443` ("[LIVE-34]") found `github_sync_map` rows for `entity_type='roadmap_arc'` pointing
at the wrong GitHub Milestone — entity_id `2` (currently arc version `v0.26.10`) mapped to
milestone #21 (live title `"0.39.2"`), entity_id `10` (currently `v0.39.2`) mapped to milestone
#29 (live title `"v0.9.2"`). `fix/codex/live-34-sync-guards` (PR #5445, merged) added a pre-PATCH
live-title drift guard that stops this from corrupting further milestones, but it does not fix
why the drift happens. This spec is that fix (item 3 of gh:#5443, deliberately deferred out of
PR #5445's scope).

**Root cause.** `roadmap_arcs` and `roadmap_phases` (`synlynk/db_schema.py:667-737`) are SQL VIEWs
introduced by the Nov-14 "Fully-Derived Roadmap" migration
(`docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md`, PR #5268). Their
`id` column is `ROW_NUMBER() OVER (ORDER BY arc_version [, phase_title])` — a position in a live,
lexicographically-sorted aggregation over `goals`, recomputed on every query. That spec's own
Section 2 says plainly: *"`roadmap_phases.id` (the `ROW_NUMBER()` column) is not stable across
data changes — it is a display-ordering convenience... Nothing may hold onto it across
requests."* `cost_entries.epic_id`/`phase_id` were retargeted onto `goals.id` for exactly this
reason at the time. `github_sync_map` was the one place that kept holding onto the view's
positional `id` across requests (persisted for weeks), which is exactly the anti-pattern that
spec warned against — any new arc_version placed (or renamed) that sorts earlier than an
existing one shifts every later id, silently repointing old mappings at the wrong arc.

**Why this needs more than "use `goals.id` like `cost_entries` did."** `cost_entries` references
a single representative goal row directly — a 1:1 relationship. An arc or phase is a *group* of
goals sharing an `arc_version` (or `arc_version`+`phase_title`) string; there is no single row
that *is* the arc. The view already picks a "representative" goal per arc for its own `goal_id`
column (`phase_title IS NULL`, earliest `id`), but that representative can itself change if the
specific goal it currently points at is later deleted or unplaced while siblings remain — a
rarer but real version of the same instability. And naively keying on the `arc_version` string
itself breaks the moment that string is corrected or renamed — which has already happened once in
this dataset (`"0.39.2"` → `"v0.39.2"`, found during this same investigation).

## Goals

- `github_sync_map` entity identity for arcs/phases survives: (a) other arcs/phases being
  placed, unplaced, or reordered elsewhere in the roadmap; (b) an arc_version or phase_title
  string being renamed/corrected; (c) a phase's priority or story linkage changing.
- **[v2]** Identity also survives *restructuring* — a subset of an arc's goals moving to a
  different arc, two arcs merging, one arc splitting into two, or a phase moving to a different
  arc — for as long as that restructuring happens **before** anything external has bound to the
  uid. The goal is explicitly: rename/reorder/restructure stays cheap *right up until an
  arc/phase has shipped (i.e. something outside `goals` — today, `github_sync_map` — has recorded
  a reference to its uid)*. After that point, identity is frozen and restructuring must go
  through an explicit, auditable operation rather than happening implicitly.
- **[v2]** The identity model is a generic `goals`-group-identity primitive, not a
  `github_sync_map`-specific mechanism: any current or future consumer that needs to hold a
  stable reference to an arc or phase across requests uses the same `arc_uid`/`phase_uid` columns
  and the same resolver (see "Shared resolver" below), not a bespoke lookup. A lint/test exists
  so a new consumer cannot silently reintroduce the `roadmap_arcs.id`/`roadmap_phases.id`
  positional-persistence bug this spec fixes.
- No regression to the Nov-14 Fully-Derived Roadmap invariant: `roadmap_arcs`/`roadmap_phases`
  stay pure VIEWs over `goals`, with `goals` as the only writer, reached only through the existing
  `INSTEAD OF` triggers or direct `goals` writes — this spec does not reintroduce a second
  writable table.
- Works the same way for a software-release roadmap (frequent version bumps, rapid
  reprioritization) and for a domain with much looser arc/phase churn (e.g. a creative-production
  roadmap with phases that get renamed, reordered, or merged as the project's own plan evolves) —
  no roadmap-domain-specific logic.

## Non-goals

- Re-litigating whether `roadmap_arcs`/`roadmap_phases` should be views at all (settled by PR
  #5268; this spec works within that architecture).
- Fixing the two already-identified bad `github_sync_map` rows (entity_id 2 → milestone 21,
  entity_id 10 → milestone 29) by data-patching their current mapping — their mapping is already
  known wrong; see Migration below for how they're handled (excluded, not auto-"fixed").
- Changing how `roadmap_phases.story_id` resolves a phase's representative story (that's gh:#5434,
  already fixed separately in PR referenced by commit `e5bf5659`).
- **[v2]** Migrating `cost_entries.epic_id`/`phase_id` onto this identity model (that drift is
  tracked separately as gh:#5446, filed out-of-scope by explicit user decision during this spec's
  review). The resolver introduced below (`resolve_arc_uid`/`resolve_phase_uid`) is written so
  gh:#5446 *can* adopt it later without a further schema change, but doing so is not part of this
  spec.
- **[v2]** Building a CLI/UI surface for merge/split/move operations. This spec defines the
  Python-level API and the data model those operations need (so the identity model doesn't paper
  over them with an undefined manual `UPDATE`), but wiring a `synlynk roadmap merge-arcs` command
  is left for whoever has the first real need for it.

## Design: durable `arc_uid` / `phase_uid`

Add two nullable `TEXT` columns to `goals`:

```sql
ALTER TABLE goals ADD COLUMN arc_uid TEXT;
ALTER TABLE goals ADD COLUMN phase_uid TEXT;
```

Each is a random, opaque identifier (`'arc-' || lower(hex(randomblob(8)))`,
`'phase-' || lower(hex(randomblob(8)))`) assigned **once**, the first time a goal is placed under
a given `arc_version` (or `arc_version`+`phase_title` pair). It has no display meaning — unlike
the view's `id`, nothing ever renders it, sorts by it, or shows it to a user. Its only job is to
be a key that other tables (`github_sync_map` today; anything else in the future) can hold onto
across requests.

### **[v2] Identity lifecycle: unbound vs. bound**

v1 treated the uid as immutable from the moment of assignment, with no way to recompute group
membership short of a manual `arc_uid = NULL` reset — the panel correctly flagged this as making
ordinary pre-ship restructuring (a partial move, a merge, a split) either silently wrong or
manual/undocumented. v2 introduces one new concept: a group's identity is **unbound** until
something outside `goals` records a reference to its uid, and **bound** after.

- **Unbound** (no row in `github_sync_map`, or any future consumer table, currently references
  this `arc_uid`/`phase_uid`): regrouping is cheap and implicit. Moving a goal to a different
  `arc_version` while unbound simply re-triggers assignment under the new group (see trigger
  logic below) — no alias is needed because nothing outside `goals` could have been pointing at
  the old uid.
- **Bound** (at least one consumer row references this uid): regrouping must go through one of
  the explicit operations below (`merge_arcs`, `split_arc`, `move_phase`), which record an alias
  so existing consumer rows keep resolving correctly. A plain rename (the `arc_version` string
  changing on every one of a group's goals at once) is **always** cheap regardless of bound
  state — see "Why the `WHEN ... arc_uid IS NULL` guard matters" below; renaming is not
  regrouping.

This is the "freezes only once an external binding exists" rule the panel asked for, expressed
concretely: **"bound" is defined as "referenced from `github_sync_map` (or another consumer
table)," not as an abstract "has it shipped yet" judgment call** — it's a fact the database can
check (`SELECT 1 FROM github_sync_map WHERE entity_id = ?`), not a human process.

### Assignment triggers

Two triggers on `goals` itself (not on the `roadmap_arcs`/`roadmap_phases` views) cover every
insert path — the existing `INSTEAD OF INSERT` triggers on the views, and the many places in this
codebase that insert into `goals` directly (`governs_cli.py`, `db.py`'s story/phase placement
paths, etc.):

```sql
CREATE TRIGGER IF NOT EXISTS trg_goals_assign_arc_uid_insert
AFTER INSERT ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals
       WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL AND rowid != NEW.rowid
       ORDER BY rowid LIMIT 1),
    'arc-' || lower(hex(randomblob(8)))
  )
  WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_arc_uid_update
AFTER UPDATE OF arc_version ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals
       WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL AND rowid != NEW.rowid
       ORDER BY rowid LIMIT 1),
    'arc-' || lower(hex(randomblob(8)))
  )
  WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_phase_uid_insert
AFTER INSERT ON goals
WHEN NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
       WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title
         AND phase_uid IS NOT NULL AND rowid != NEW.rowid
       ORDER BY rowid LIMIT 1),
    'phase-' || lower(hex(randomblob(8)))
  )
  WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_phase_uid_update
AFTER UPDATE OF arc_version, phase_title ON goals
WHEN NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
       WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title
         AND phase_uid IS NOT NULL AND rowid != NEW.rowid
       ORDER BY rowid LIMIT 1),
    'phase-' || lower(hex(randomblob(8)))
  )
  WHERE rowid = NEW.rowid;
END;
```

**[v2] Deterministic tie-break:** v1's lookup subqueries had no `ORDER BY`, so if a group ever
transiently held two distinct non-null uids (a bug state the invariant checks below should
prevent, but defense-in-depth matters when triggers interact with concurrent writers), which one
a *third* new row adopted was undefined. `ORDER BY rowid LIMIT 1` makes that deterministic.

**Why the `WHEN ... arc_uid IS NULL` guard matters:** a plain rename
(`UPDATE goals SET arc_version='v0.39.2' WHERE arc_version='0.39.2'`) fires
`trg_goals_assign_arc_uid_update` for every affected row, but since each row's `arc_uid` is
already non-null, the trigger body never runs — the existing `arc_uid` is left untouched. A
rename is therefore uid-stable automatically, with no rename-specific code path to maintain or
get wrong, **whether or not the uid is bound**.

**Reorder/reprioritize:** `roadmap_priority` changes, moving a phase's `story_id`, or changing a
phase's `status` never touch `arc_version`/`phase_title`, so neither trigger fires at all —
identity is untouched by definition.

**New goal joining an existing arc/phase:** the `COALESCE(... SELECT existing arc_uid ..., fresh
uid)` means a second (or fifth) goal placed under an `arc_version` that already has other placed
goals adopts the *same* `arc_uid` those goals already carry, rather than minting a new one. All
goals in one arc/phase share one uid.

**[v2] A goal moving to a different, unbound arc:** moving a goal's `arc_version` from group A to
group B, where B is unbound, works exactly like the "new goal joining" case above — the trigger
adopts B's existing uid (or mints a fresh one if B is new). No alias needed, because nothing
outside `goals` could have referenced B's (or the moved goal's old) uid while B was unbound. This
is what makes ordinary pre-ship reshuffling cheap: **it only requires the explicit
merge/split/move operations below once at least one side of the operation is bound.**

### **[v2] Explicit regroup operations (for bound uids)**

Once a uid is bound, the following three operations are the *only* supported ways to change group
membership. Each is implemented in a new module, `synlynk/roadmap_identity.py`, and each writes a
row to a new alias table so bound consumers (`github_sync_map` today) keep resolving correctly
without themselves needing to know a regroup happened:

```sql
CREATE TABLE IF NOT EXISTS roadmap_uid_aliases (
    old_uid TEXT PRIMARY KEY,
    new_uid TEXT NOT NULL,
    uid_kind TEXT NOT NULL CHECK (uid_kind IN ('arc', 'phase')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`old_uid` is the primary key (one old uid resolves to exactly one current uid — no fan-out), and
`new_uid` may itself later become an `old_uid` in a subsequent alias row (chained regrouping), so
resolution always walks the chain to its end (see "Shared resolver" below).

- **`merge_arcs(conn, into_uid, *merged_uids, reason)`** — rewrites every goal row's `arc_uid`
  from each `merged_uids` entry to `into_uid`, and inserts one `roadmap_uid_aliases` row per
  merged uid (`old_uid=merged_uid, new_uid=into_uid, uid_kind='arc'`). This replaces v1's
  undocumented manual-rename-plus-`UPDATE ... SET arc_uid = NULL` procedure with an explicit,
  tested function — a deliberate merge is now a single call, not a two-step manual dance a
  human has to get in the right order.
- **`split_arc(conn, from_uid, goal_ids_to_move, reason)`** — mints one fresh `arc_uid`, assigns
  it to the given subset of `from_uid`'s goals, leaves the rest on `from_uid` unchanged. No alias
  row is written for a split (the new uid has no prior identity to alias *from* — it's new,
  pointing at nothing old); existing consumer rows referencing `from_uid` continue to resolve to
  the goals that stayed behind, which is the correct "the original thing kept its identity, a
  piece broke off as something new" semantics.
- **`move_phase(conn, phase_uid, new_arc_version, reason)`** — reassigns `arc_version` on every
  goal sharing `phase_uid`. The `phase_uid` itself is untouched (a phase moving to a different arc
  is still the same phase); this is why the v1 trigger's "`INSTEAD OF UPDATE` rewrites both
  columns and leaves the uid behind" gap the panel flagged doesn't apply once this is the
  supported move path — `move_phase` is the one place that's allowed to change `arc_version`
  without re-running phase-uid assignment, because it isn't creating a new phase.

All three raise `ValueError` if called on an *unbound* uid with no existing consumer reference —
unbound regrouping should go through plain `goals` writes (which the triggers already handle for
free), not these functions; that keeps the "cheap until bound" promise honest rather than routing
every pre-ship edit through ceremony it doesn't need.

### View changes

`roadmap_arcs`/`roadmap_phases` gain `arc_uid`/`phase_uid` columns alongside their existing
`ROW_NUMBER()`-based `id` column. **`id` is kept, unchanged** — `_generate_roadmap_md()`,
`uxcore.py`, and other render paths legitimately use it for *display ordering* (a `ROW_NUMBER()`
by version is a perfectly fine "position in a sorted list" value); the bug was never that `id`
exists, only that something *persisted* it as if it were an identity. The new uid columns are
what anything persisting a reference must use going forward.

```sql
-- roadmap_arcs, added to the SELECT list:
CASE WHEN COUNT(DISTINCT arc_uid) = 1 THEN MIN(arc_uid)
     ELSE NULL END AS arc_uid,
```
```sql
-- roadmap_phases, added to the SELECT list:
CASE WHEN COUNT(DISTINCT phase_uid) = 1 THEN MIN(phase_uid)
     ELSE NULL END AS phase_uid,
```

**[v2] Why `CASE ... COUNT(DISTINCT) ... ELSE NULL`, not plain `MIN`/`MAX`:** v1 used `MIN()`
("every goal in the group has the same value by construction, so any aggregate works"), which is
true only when the invariant holds. The panel's "inconsistency is hidden" finding is exactly the
failure of that assumption: if a bug ever lets a group end up with two distinct non-null uids,
`MIN()` silently picks one, `github_sync_map`'s lookup resolves to a plausible-looking but wrong
row, and nothing signals the corruption. `NULL` on divergence is loud instead — any code reading
`roadmap_arcs.arc_uid` and getting `NULL` for a group that should have goals knows immediately
something is wrong, rather than silently working with a coin-flipped uid. See "Invariant
enforcement" below for how this is actively checked, not just passively surfaced.

## **[v2] Shared resolver**

```python
# synlynk/roadmap_identity.py

def resolve_arc_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Follow roadmap_uid_aliases to the current arc_uid for a possibly-stale uid.
    Returns uid unchanged if it has no alias (the common case)."""
    seen = {uid}
    current = uid
    while True:
        row = conn.execute(
            "SELECT new_uid FROM roadmap_uid_aliases WHERE old_uid = ? AND uid_kind = 'arc'",
            (current,),
        ).fetchone()
        if row is None:
            return current
        if row[0] in seen:
            raise ValueError(f"alias cycle detected starting from {uid!r}")
        seen.add(row[0])
        current = row[0]


def resolve_phase_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Same as resolve_arc_uid, for phase_uid / uid_kind='phase'."""
    ...  # identical shape, uid_kind='phase'
```

This is the one function any current or future consumer calls before trusting a stored
`arc_uid`/`phase_uid` still points at a live group — `sync_arc()` calls it on read (see below);
any later consumer (e.g. a `cost_entries` migration under gh:#5446, or a hypothetical phase-level
GitHub sync) calls the same function rather than re-deriving its own resolution logic. This is
the concrete answer to the panel's "generalize beyond milestones" finding: the generalization
isn't a promise, it's this one shared, tested function every consumer is required to go through.

**[v2] Consumer rule + lint test.** `tests/test_roadmap_identity_lint.py` (new) statically scans
every `.py` file under `synlynk/` for the patterns `roadmap_arcs.id` and `roadmap_phases.id` used
outside of an explicit allowlist (display/ordering call sites that are legitimately allowed to
read the positional `id` — e.g. `gh_sync_cli.py`'s `ORDER BY id ASC` ordering clause, which this
spec's own migration keeps for deterministic iteration, not identity). The allowlist is a literal
list of `(file, line-content-substring)` pairs maintained in the test itself; any *new* match not
already on the allowlist fails the test with a message pointing at `resolve_arc_uid`/the
`arc_uid`/`phase_uid` columns. This is deliberately a blunt grep-based check, not a full AST
analysis — the goal is to make reintroducing this exact bug class loud, not to catch every
conceivable misuse.

## `github_sync_map` migration

`entity_id` for `entity_type IN ('roadmap_arc', 'roadmap_phase')` moves from the positional `id`
to `arc_uid`/`phase_uid` text.

**Call sites to update** (all currently key on the positional `id`):

- `synlynk/gh_sync.py` — three `SELECT ... FROM roadmap_arcs WHERE id=?` lookups in `sync_arc()`
  (notes lookup, phase-status lookup, main arc-fields lookup) become `WHERE arc_uid=?`; the
  `github_sync_map` lookup (`WHERE entity_type='roadmap_arc' AND entity_id=?`) now receives
  `resolve_arc_uid(conn, arc_uid)` instead of `str(arc_id)` — **[v2]** routing through the
  resolver here (rather than the raw `arc_uid` parameter) is what makes `sync_arc` correctly
  follow a merge/split/move that happened after the caller last read the roadmap, instead of
  looking up a uid that's since been superseded by an alias.
- `synlynk/gh_sync_backfill.py` — `run_backfill()`'s `SELECT id FROM roadmap_arcs WHERE
  is_milestone_eligible=1 ORDER BY id ASC` becomes `SELECT arc_uid FROM roadmap_arcs ... ORDER BY
  id ASC` (keep `id` only for deterministic ordering, select `arc_uid` as the value passed to
  `sync_arc()`); the `JOIN roadmap_arcs ra ON ra.id = CAST(gm.entity_id AS INTEGER)` becomes `JOIN
  roadmap_arcs ra ON ra.arc_uid = gm.entity_id` (drop the `CAST ... AS INTEGER`, since the key is
  now text).
- `synlynk/gh_sync_cli.py` — `cmd_sync_roadmap()`'s `SELECT id FROM roadmap_arcs WHERE
  is_milestone_eligible=1 ORDER BY id ASC` becomes `SELECT arc_uid FROM roadmap_arcs ... ORDER BY
  id ASC`, passing `arc_uid` through to `sync_arc()` the same way.
- `sync_arc()`'s signature changes from `arc_id: int` to `arc_uid: str` (rename the parameter
  everywhere it's threaded through, so a reviewer can `grep arc_id` post-merge and find nothing
  left referring to the positional id in this path). **[v2]** This is a correction to v1, which
  described this signature change in prose but left an inconsistent `arc_id: int` in its own
  worked example — the panel's "plan keeps `sync_arc(arc_id: int)`" finding was catching the
  *plan* drifting from the *spec*, not an intentional design choice. The spec's intent was always
  `arc_uid: str`; the plan must match it exactly.

**Backfilling existing `github_sync_map` rows.** For every *currently valid* `roadmap_arc`
mapping — one where PR #5445's drift guard would pass (live milestone title matches the arc's
expected title) — rewrite its `entity_id` from the old positional id to the arc's current
`arc_uid`:

```sql
UPDATE github_sync_map
SET entity_id = (SELECT arc_uid FROM roadmap_arcs WHERE CAST(id AS TEXT) = github_sync_map.entity_id)
WHERE entity_type = 'roadmap_arc'
  AND entity_id IN (
    SELECT CAST(id AS TEXT) FROM roadmap_arcs
  )
  AND entity_id != (SELECT arc_uid FROM roadmap_arcs WHERE CAST(id AS TEXT) = github_sync_map.entity_id);
```

run inside a one-off migration script that, for each row, additionally verifies via a live `gh
api` call (reusing PR #5445's drift-guard comparison, not reimplementing it) that the resulting
mapping's milestone title still matches before committing the rewrite — mirroring the "diff
before cutover" discipline the Nov-14 spec itself used for its own table→view migration.

**[v2] The `gh api` verification call is a separate, offline-safe pass, not inline in the
migration transaction.** v1 ran the live network check inside the same migration step as the
schema/data change, which the panel flagged as making the migration itself network-dependent
(and therefore unsafe to run offline, in CI, or against a network-partitioned environment). v2
splits this into two scripts: (1) the backfill script above, which is pure-SQL and always safe to
run; (2) a separate `verify_github_sync_map_arc_uid_migration.py` one-off that, after (1) has run,
walks every migrated row and confirms live title match, flagging (not auto-fixing) any mismatch
for manual review. (1) is required before cutover; (2) is strongly recommended but is a read-only
check, so its failure mode is "print a warning," never "corrupt data."

**The two already-known-bad rows (entity_id `2`→milestone 21, entity_id `10`→milestone 29) are
excluded from this backfill** — their mapping is already proven wrong (that's what gh:#5443
reported), so rewriting them to use the new uid would just carry the *wrong* `github_number`
forward under a new, differently-shaped key. **[v2]** Deletion of these two specific rows is
title-verified and audited, not a blind positional-id match: the migration script looks up each
row's *current* live milestone title via `gh api` immediately before deleting, logs
`(entity_id, github_number, live_title, "deleted: known-bad LIVE-34 mapping")` to stdout, and
only then deletes — this replaces v1's plain `WHERE entity_id IN ('2', '10')` (which the panel
correctly noted re-keys on the same unstable positional value this spec exists to stop trusting)
with a check that the row being deleted is still the specific bad row gh:#5443 found, not
whatever happens to currently sit at that positional id. The next `synlynk gh sync-roadmap` run
then re-syncs those two arcs from scratch under their fresh `arc_uid` keys — PR #5445's
`_find_milestone_by_title` fallback path will either correctly reuse an existing, title-matching
milestone or create a new one, either of which is strictly better than keeping a row already
known to point at the wrong milestone.

## **[v2] Invariant enforcement**

Three layers, matching the panel's "each active group must resolve to exactly one uid" requirement:

1. **Views** — the `CASE WHEN COUNT(DISTINCT ...) = 1 ... ELSE NULL` shape above makes divergence
   produce a loud `NULL` instead of a silently-wrong value (described above).
2. **Migration** — the Step-1 backfill (see "Migration sequencing") fails loudly (raises, does not
   commit) if, after assignment, any `roadmap_version`/`(arc_version, phase_title)` group has more
   than one distinct non-null uid. This is the "migration fails loudly on conflicts" the panel
   asked for — the existing v1 backfill was silent on this case because it assumed the invariant
   rather than checking it.
3. **`doctor`** — `synlynk doctor` (`synlynk/doctor.py`) gains one new check,
   `check_roadmap_uid_consistency(conn)`: for every `arc_version` and every `(arc_version,
   phase_title)` pair currently represented in `goals`, assert `COUNT(DISTINCT arc_uid)` /
   `COUNT(DISTINCT phase_uid)` is exactly 1 among placed (non-NULL `arc_uid`) rows. Reports any
   violation with the offending `arc_version`/`phase_title` and the distinct uids found, so
   divergence is caught proactively instead of only when a consumer happens to hit the `NULL`
   case above.

## Migration sequencing

Same two-step discipline the Nov-14 Fully-Derived Roadmap spec used for its own cutover, with the
invariant check and atomic cutover the panel asked for:

**Step 1 (additive, verify):** add the `arc_uid`/`phase_uid` columns, the `roadmap_uid_aliases`
table, and the four assignment triggers; add the view columns (new `CASE`-guarded shape above).
Run a one-off backfill assigning `arc_uid`/`phase_uid` to every currently-placed goal (group by
`arc_version` / `arc_version`+`phase_title`, one fresh uid per group, applied to every goal in
that group — equivalent to what the insert/update triggers would produce if they'd existed from
day one). **This backfill raises if any group ends up with more than one distinct uid** (see
"Invariant enforcement" above) rather than silently diffing after the fact. Diff (defense in
depth, since the backfill now self-checks): for every `roadmap_arcs`/`roadmap_phases` row, confirm
every goal in its group now shares exactly one non-null `arc_uid`/`phase_uid` — any group with
more than one distinct value, or any placed goal still `NULL`, blocks the cutover.

**Step 2 (cutover, atomic with the mapping rewrite):** once the diff is clean, in a single
transaction: migrate `github_sync_map` as described above (bulk rewrite of valid rows via
`resolve_arc_uid`-equivalent SQL, title-verified deletion of the two known-bad rows), **and**
switch the three call sites (`gh_sync.py`, `gh_sync_backfill.py`, `gh_sync_cli.py`) to read/write
`arc_uid`/`phase_uid` instead of the positional `id` — these two changes land together, as one
deploy, rather than the read-path switch landing first and running against not-yet-migrated data
(v1's sequencing had the read-path switch described before the mapping rewrite, which the panel
flagged as a window where `sync_arc()` would look up `arc_uid` values that `github_sync_map`
didn't have yet). Re-run `synlynk gh sync-roadmap --dry-run` to confirm it now reports the same
milestone-eligible count as before the migration, with zero drift-guard warnings other than the
two expected fresh syncs. Run the separate, offline-safe `gh api` verification pass (see above)
as a follow-up check, not a cutover blocker.

## Testing

- `tests/test_roadmap_views.py` (existing) — extend with fixtures asserting: (a) `arc_uid` is
  assigned on first placement and identical across every goal subsequently placed under the same
  `arc_version`; (b) renaming `arc_version` on all of an arc's goals leaves `arc_uid` unchanged;
  (c) the same two behaviors for `phase_uid` keyed on `(arc_version, phase_title)`; (d) a brand
  new, never-seen `arc_version` gets a fresh `arc_uid` distinct from every existing one; (e)
  **[v2]** a group that (via direct test-fixture manipulation) ends up with two distinct
  `arc_uid`s surfaces as `arc_uid IS NULL` in the view, not a silently-chosen value.
- New `tests/test_roadmap_identity_migration.py` — fixture with a pre-migration `goals` table
  (some already placed, no uid columns), run the Step 1 backfill, assert every group collapses to
  exactly one uid and no placed goal is left `NULL`; **[v2]** add a case where a fixture is
  deliberately seeded with a pre-existing divergence (two uids under one `arc_version`) and assert
  the backfill raises rather than silently resolving it.
- **[v2]** New `tests/test_roadmap_identity.py` — unit tests for `synlynk/roadmap_identity.py`:
  `merge_arcs` rewrites all merged goals to the target uid and writes one alias row per merged
  uid; `resolve_arc_uid` follows a single alias, follows a chain of two, and raises on a
  (fixture-forced) cycle; `split_arc` mints a uid disjoint from the original and leaves the
  original's remaining goals' uid untouched; `move_phase` changes `arc_version` without changing
  `phase_uid`; all three operations raise `ValueError` when called on a uid with zero
  `github_sync_map` (or other consumer) references (the "unbound — use a plain `goals` write
  instead" guard).
- **[v2]** New `tests/test_roadmap_identity_lint.py` — the static-scan consumer-rule test described
  under "Shared resolver" above.
- `tests/test_gh_sync.py` (existing) — update the arc-sync fixtures to pass `arc_uid` instead of
  integer ids to `sync_arc()`; add a case proving that shifting another arc's sort position
  (insert a new, earlier-sorting `arc_version`) does **not** change an existing arc's
  `github_sync_map` mapping target — this is the regression test for the actual bug gh:#5443
  reported; **[v2]** add a case proving `sync_arc()` correctly follows a `roadmap_uid_aliases`
  redirect (merge a bound arc into another, confirm `sync_arc()` on the old uid still resolves
  and updates the right `github_sync_map` row via `resolve_arc_uid`).
- `tests/test_gh_sync_backfill.py`, `tests/test_gh_sync_cli.py` (existing) — update fixtures for
  the `SELECT arc_uid ...` query shape; no behavioral change expected in these tests beyond the
  key type.
- **[v2]** New `tests/test_doctor_roadmap_uid_consistency.py` — `check_roadmap_uid_consistency`
  passes on a clean fixture and reports the specific `arc_version`/distinct-uid-set on a
  deliberately-corrupted one.

## Deferred / out of scope

- Fixing the merge-by-rename edge case automatically — **[v2] superseded by `merge_arcs()`**,
  which is now the explicit, tested, documented operation; there is no remaining undocumented
  manual procedure.
- Extending `arc_uid`/`phase_uid` identity to `decisions` or `stories` — those already use stable
  natural keys (`decision_id`, `story_id`) and are not affected by this bug class.
- A UI/CLI surface for inspecting or displaying `arc_uid`/`phase_uid` — they are an internal
  join key only, never shown to a user, consistent with how they're described above.
- **[v2]** A UI/CLI surface for `merge_arcs`/`split_arc`/`move_phase` — the Python API is in
  scope; a `synlynk roadmap merge-arcs` command is not, until something has a real need for it.
- **[v2]** Migrating `cost_entries` onto this model (gh:#5446, filed separately).
- **[v2]** A phase-level GitHub sync consumer for `phase_uid` — none exists today (only
  `arc`-level milestones sync to GitHub; phase status is read as text into an arc's milestone
  notes, not synced as its own entity). `phase_uid` therefore ships with direct unit/resolver
  test coverage (see Testing) rather than a production caller, matching the panel's "real
  consumer **or tests**" bar. The resolver and alias table are written so that whenever a real
  phase-level consumer does appear, it is a caller of `resolve_phase_uid`/`move_phase`, not a new
  bespoke lookup — i.e. the generalization this spec promises is already in place, waiting for a
  second consumer, rather than needing to be retrofitted.
