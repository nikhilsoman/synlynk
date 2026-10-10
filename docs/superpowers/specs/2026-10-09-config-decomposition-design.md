# Design: Decompose `.synlynk/config.json` (gh:#2101)

**Status:** Approved by Nikhil, 2026-10-09
**Related:** gh:#2101 (source issue), gh:#2145 (roles/capability-mapping triplication, filed out-of-scope from this design)

## 1. Problem

`.synlynk/config.json` has grown into a single ~120-line blob mixing three
unrelated concerns: workspace identity/dispatch behavior, billing/budget
data, and governance-flavored policy fields. `load_config()`
(`synlynk/__init__.py`) owns a large hand-rolled defaults dict and re-derives
`roles` on every call via `_load_capability_roles()`/`_default_roles_map()`.
The issue's own acceptance criteria name a `policy.json` split target that
collides with an existing, unrelated file: `synlynk/policy.py`'s governance
file (`merge_authority`, `dev_authority.task_allocation`,
`governs_authority`, `release_authority`, `capability_policy`, etc.), which
already has its own two-tier workspace-default + repo-override merge system.

## 2. File split

- **`workspace.json`** — `org`, `owner`, `repo`, `project_id`,
  `identity_slug`, `project_docs_dir`, `workspace_id`, `agent_slots`,
  `workgroup_agents`, `agents`, `team`, `sync_endpoint`, `dispatch{}`,
  `local_auto_threshold`, `local_fallback`, `watch_interval_seconds`,
  `auto_smoke_test`, `auto_launch_after_wizard`, `dispatch_mode`,
  `fenced_commands`, `nudges{}`, `exec_timeout_minutes`,
  `stall_timeout_minutes`, `review_stall_timeout_minutes`,
  `swarm_runners{}`, `last_housekeeping_date`, `features{}`, `repo_id`,
  `dr_sync_path`, `mode`.
  - `features`, `repo_id`, `dr_sync_path`, and `mode` are four legacy/ad-hoc
    keys discovered during implementation planning, none in `load_config()`'s
    own defaults dict because all four call sites bypass `load_config()` and
    hand-roll their own file read/write: `synlynk/uxcore.py`'s
    `FeatureFlags.is_enabled()` reads `features`; `synlynk/workspace.py`'s
    `add_repo()` reads/writes `repo_id`; `synlynk/__init__.py`'s `_dr_sync()`
    and `synlynk/db.py`'s disaster-recovery mirror functions read/write
    `dr_sync_path`; `synlynk/__init__.py`'s re-init preview function reads
    `mode` (`cfg.get("mode", "solo")`) to display the workspace's current
    solo/team mode before a re-init. All four are workspace-identity/behavior
    data, so `workspace.json` is their natural home.
- **`billing.json`** — `budget{}`, `harness_billing{}`, `payment_models{}`,
  `capability_sweep{}`.
- **`policy.json`** (existing governance file, extended) — four flat
  top-level keys move here: `qa_gate_mode`, `roles`, `story_classification`,
  `sentinel{}`. These are siblings of `capability_policy`/`overrides`/
  `repo_id` at the top level, not nested under `overrides` — `overrides`
  specifically means "override a workspace-tier default," and these four
  keys have no workspace-tier default to override.
  - `roles` migrating here is a stopgap, not a fix. gh:#2145 tracks the
    separate problem that `.synlynk/capability-roles.json`, `config.json`'s
    `roles` key, and `policy.json`'s own `overrides.role_task_type_compat`/
    `overrides.dev_authority.task_allocation` are three independently
    drifting sources of the same harness/role capability mapping. This
    design does not resolve that collision — it only relocates one of the
    three sources to live alongside the other two for future consolidation.

## 3. Precedence

`workspace.json` and `billing.json` are flat, repo-level files, re-read on
every call — matching `config.json`'s current convention exactly (no new
merge tier introduced). `policy.json`'s existing workspace-default +
repo-override merge tier (`load_policy()`) is untouched; the four migrated
keys are plain repo-level fields on the merged result, not part of that
override mechanism.

## 4. Schema validation

`synlynk/config_schema.py`'s `CONFIG_SCHEMA` splits into `WORKSPACE_SCHEMA`
and `BILLING_SCHEMA`, each validated independently against its own file.
The existing policy schema gains field definitions for the four migrated
keys (`qa_gate_mode`, `roles`, `story_classification`, `sentinel`). No
`jsonschema` dependency is introduced — both new schemas reuse the existing
hand-rolled `validate()`/`validate_fields()`/`_check_field()` helpers.

## 5. API compatibility

`load_config()` remains the single entry point for all ~80+ existing call
sites (`synlynk/jobs.py`, `synlynk/dispatch.py`, etc.) that expect one flat
merged dict (e.g. `config.get("budget")`, `config["harness_billing"]`).
Internally it now reads `workspace.json` + `billing.json` + the four
migrated `policy.json` fields and re-merges them into the same flat shape
it returns today. **Zero call-site changes are required.** New
`load_workspace()` and `load_billing()` functions are added for future code
that wants the split view directly; adopting them is optional, not forced.

## 6. Migration

On first read after upgrade: if `config.json` exists on disk and
`workspace.json`/`billing.json` do not, the loader:

1. Splits the in-memory defaults-merged config into the three target shapes.
2. Writes `workspace.json` and `billing.json` to disk.
3. Merges the four policy-flavored keys into `policy.json` (creating it with
   defaults first if the repo has no existing `policy.json`).
4. Renames `config.json` → `config.json.bak` (not deleted, for
   recoverability — matches this project's general preference for
   reversible operations over destructive ones).

This is idempotent: step 1 only runs when the new files don't yet exist, so
a second invocation after migration is a no-op passthrough to the normal
split-file read path.

## 7. Dogfooding exception: this repo's own tracked files

**Correction (found during implementation planning):** the premise below was
backwards. `synlynk/parity.py`'s onboarding `.gitignore` template (the
template synlynk itself writes into *every newly onboarded repo*, not just
this one) already negates `.synlynk/config.json` and `.synlynk/policy.json`
out of the blanket `**/.synlynk/*` ignore — i.e. **config.json/policy.json
are default-TRACKED by synlynk's own general convention**, not a one-off
quirk of this repo's dogfooding. `git ls-files` confirming this repo's
`config.json`/`policy.json` are tracked (commit `524624e5`) is this
convention working as designed, not an exception to it.

- `synlynk/parity.py`'s `ensure_recursive_gitignore()` gitignore-rules
  string gains two new **tracked** exceptions, `!**/.synlynk/workspace.json`
  and `!**/.synlynk/billing.json`, alongside the existing
  `!**/.synlynk/config.json`/`!**/.synlynk/policy.json` lines — so every
  newly onboarded repo keeps tracking its split config files by default,
  matching `config.json`'s current real-world convention. (`billing.json`
  still carries budget/billing data; if that turns out to warrant different
  treatment from `workspace.json`, that's a follow-up decision, not blocking
  here — this design keeps parity with `config.json`'s existing default.)
- This repo's own root `.gitignore` already has the `**/.synlynk/*` block
  with those exception lines (`ensure_recursive_gitignore()` is a one-time
  bootstrap, already run here) — this design adds the two new exception
  lines to this repo's root `.gitignore` directly, mirroring the
  `parity.py` template update above.
- In this repo specifically, the migration step must `git add` the new
  `workspace.json`/`billing.json` and `git rm` the old `config.json`, in the
  same commit that performs the split here — otherwise this repo silently
  stops tracking its own canonical config sample.

## 8. Error handling

- Missing `workspace.json`/`billing.json` with no legacy `config.json`
  present either (e.g. a brand-new `synlynk init`): both files are created
  from defaults, same as `config.json` does today for a fresh workspace.
- A `workspace.json` or `billing.json` that fails schema validation raises
  the same error type `load_config()` raises today for an invalid
  `config.json` — no new exception class.
- A `policy.json` that fails to parse during migration (corrupt JSON)
  aborts the migration without touching `config.json` — the legacy file is
  only renamed to `.bak` after all three target writes succeed.

## 9. Testing

- Split logic: a test with an in-memory legacy-shaped dict asserts the
  three-way split produces the exact `workspace.json`/`billing.json` field
  sets listed in Section 2, and the four-field subset routed to
  `policy.json`.
- Migration: a test seeds a temp directory with only `config.json`, calls
  the migration path, and asserts `workspace.json`, `billing.json`,
  `policy.json` (merged), and `config.json.bak` all exist afterward, and
  that a second call is a no-op (no file timestamps change).
- Facade compatibility: existing `load_config()` call-site tests (budget
  checks, harness billing lookups) are run unmodified against the new
  split-file backend — if they still pass without edits, API compatibility
  is verified.
- Schema: one test per new schema (`WORKSPACE_SCHEMA`, `BILLING_SCHEMA`)
  exercising a valid and an invalid document each.

## 10. Out of scope

- Consolidating the roles/capability-mapping triplication — tracked
  separately as gh:#2145.
- Any change to `policy.json`'s existing `overrides`/merge-tier mechanism.
- Changing `config_schema.py`'s validation style (e.g. adopting
  `jsonschema`) — out of scope for this split.
