# Status Writer Inventory & Canonical Enum (Phase 0) — Design

## Problem

The 2026-10-03 decide panel on PR #1949 (job-status truth / structured completion oracle,
`project-docs/decisions/2026-10-03-review-pr-1949-design-job-status-truth-a.md`, dec-5d37b005)
converged on AMEND, not approve. The panel endorsed the direction (separate observations from
status, explicit effect contracts, verified-remote-effects precedence over receipts/exit codes)
but blocked on 10 required-changes categories, with two of them — a closed status enum with an
alias map (category 4), and the raw inventory of every place the codebase currently writes a
status value (category 4's prerequisite, called out by all three panelists as "a FAILING TEST
over an enumerated list, gating deliverable, not just a doc") — identified as groundwork that has
to land before the oracle rewrite itself (causal attribution, evidence ranking, state-transition
semantics) can be meaningfully specified or reviewed.

Today, status values are written inconsistently across the codebase: `failed_verification`,
`failed_noop_denied`, `circuit_breaker_tripped`, and others, with no single source of truth for
which strings are valid, which are synonyms of each other, and which call sites write which
values. Any amendment to PR #1949 that doesn't first establish this ground truth risks designing
the new oracle against an incomplete or inconsistent picture of what "status" currently means.

This spec covers Phase 0 only: inventory + canonical enum. It does not touch the oracle itself
(causal attribution, evidence ranking, state machine, effect contracts, concurrency) — those are
explicitly deferred to a follow-on spec (b) that pilots the new oracle on the GitHub-review effect
class only, per the panel's convergent rollout condition, and a further spec (c) that broadens to
other effect classes once the pilot clears its promotion gate.

## Scope

**In scope:**
1. A canonical status enum covering every distinct status value currently written anywhere in the
   codebase, with a documented alias map for legacy spellings that are true synonyms.
2. A static, committed inventory of every status-writing call site (file:line), built by scanning
   the codebase for known write patterns.
3. A failing-then-passing test that walks the inventory and asserts every status value found is
   either a canonical enum member or a documented alias.

**Out of scope (explicitly deferred):**
- Migrating any call site to write the canonical enum value directly. Legacy writers keep writing
  their existing strings; the alias map translates them for any consumer that wants the canonical
  name. Call-site migration happens incrementally as each effect class is migrated to the new
  oracle in specs (b)/(c).
- State-transition / revision semantics (panel category 5): which states are absorbing, how a
  non-absorbing state gets upgraded by stronger evidence, retry budgets. This is data-model work
  that belongs with the oracle itself in spec (b), not with naming/classification in Phase 0.
- Effect contracts (panel category 5a), causal attribution (category 1), evidence ranking
  (category 2), the no-op OR-loophole (category 3), idempotency/concurrency (category 6) — all
  deferred to spec (b).
- Any change to runtime behavior. This spec is purely descriptive: it makes today's inconsistent
  status-writing visible and classified, it does not change what any code path actually does.

## Design

### 1. Canonical enum + alias map

New module (exact path TBD by the implementer during the inventory pass — likely
`synlynk/status_enum.py`) defining a single closed enum of canonical status values, plus a dict
mapping legacy/alias strings to their canonical member.

The enum membership is *derived from* the inventory (step 2), not designed up front: the
implementer builds the inventory first, then reviews every distinct status value it surfaces and
decides, per value, whether it:
- is a true synonym of another value already covered (becomes an alias), or
- represents a genuinely distinct state (becomes its own canonical enum member, even if it looks
  superficially similar to another — e.g. `failed_noop_denied` and `circuit_breaker_tripped` are
  not assumed to collapse; each gets its own canonical member unless inspection of the surrounding
  code confirms they mean the same thing).

This ordering (inventory first, enum second) is deliberate — designing the enum before seeing the
full inventory risks baking in the current naming confusion rather than resolving it.

### 2. Status writer inventory

A committed, hand-reviewed data file (e.g. `synlynk/_status_writer_inventory.py`) listing every
status-writing call site found by scanning the codebase for:
- Direct SQL writes: `UPDATE ... SET status = ...` and equivalents.
- Attribute/dict assignment: `.status = "..."`, `status="..."` as a kwarg.
- Calls to any helper function whose name suggests a status mutation (pattern-match on
  `update_*_status`, `set_*_status`, `_mark_*`, or similar — implementer should grep broadly and
  err toward over-inclusion, then prune false positives on review).

Each inventory entry records `(file, line, status_value_or_classification, writer_function_name)`.
Two kinds of entries:
- **Literal** — the status value is a string literal at the write site. Recorded as-is.
- **Dynamic** — the status value is computed (a variable, a function return, string
  interpolation) and not statically resolvable to a single literal. These are recorded with a
  manually-authored list of the possible values that expression can take, derived by the
  implementer reading the surrounding code — not guessed. If the possible-value set genuinely
  cannot be enumerated (fully runtime-computed, e.g. built from unbounded input), the entry is
  flagged `dynamic: unresolved` with a one-line note explaining why, and is excluded from the
  enum-membership assertion but still appears in the inventory as a documented gap for spec (b)/(c)
  to tighten when that call site's effect class is migrated.

### 3. The failing-then-passing test

`tests/test_status_writer_inventory.py`:
1. Re-runs the same scan the inventory was built from (grep/AST walk for the write patterns above)
   and diffs the result against the committed inventory file. Any newly-discovered call site not
   present in the committed inventory is a test failure — this is what keeps the inventory honest
   over time; a future PR that adds a new status-writing call site without updating the inventory
   fails CI.
2. For every `literal` entry in the inventory, asserts its status value is a member of the
   canonical enum or a key in the alias map.
3. For every `dynamic` entry (not `dynamic: unresolved`), asserts every value in its
   manually-authored possible-value list is a member of the canonical enum or a key in the alias
   map.
4. `dynamic: unresolved` entries are asserted to exist only via an explicit allowlist in the test
   itself (so a `dynamic: unresolved` entry can't be added silently to dodge classification — it
   has to be acknowledged in the test file too).

This test fails today, before the enum/alias map/inventory exist, on the inconsistent status
names the panel flagged. It passes once the inventory is complete and every entry resolves to
canonical-or-alias (or is an explicitly allowlisted `dynamic: unresolved`) — not once any call
site's runtime behavior changes.

## Testing

- The test described in Design §3 is the primary deliverable — it IS the acceptance test, not a
  separate thing to additionally verify.
- No live/integration test needed — this spec makes no runtime behavior change, so there is
  nothing to smoke-test beyond the unit-level inventory/enum consistency check.

## Acceptance

- `synlynk/status_enum.py` (or equivalent) exists with a closed enum and alias map.
- `synlynk/_status_writer_inventory.py` (or equivalent) exists, committed, covering every status
  write site the scan finds as of this PR.
- `tests/test_status_writer_inventory.py` passes.
- Zero behavior change: no existing test outside the new one changes its expected outcome: no
  call site's actual write value changes.
- This spec explicitly does not close any of the panel's 10 required-changes categories beyond
  #4 (closed enum + alias map) and its inventory prerequisite. Categories 1, 2, 3, 5, 5a, 6 remain
  open, to be addressed in spec (b) (GitHub-review-only oracle pilot).
