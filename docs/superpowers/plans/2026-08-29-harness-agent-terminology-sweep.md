# Harness vs Agent Terminology Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sweep `synlynk/*.py` help text, docstrings, and comments to use "Harness" (execution backend: Claude/Agy/Codex/Grok/local) and "Agent" (role identity: pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) consistently with the already-decided canonical definitions in `docs/glossary-agent-vs-harness.md`, closing gh#1202.

**Architecture:** This is a prose-only correction pass — no renamed CLI flags, subcommands, function names, or DB columns. Those are load-bearing public/internal API surface (`synlynk agent`, `--agent`, `--as-agent`, `agent_id` columns, etc.) and a rename there is a breaking change requiring its own deprecation-path decision, explicitly deferred to Task 3 (a follow-up issue, not implemented here). Historical/proposal docs under `docs/` (the `*-human-agent-hybrid-workgroup-study.md` files, `docs/multi-agent-orchestration-proposal.md`) predate the Agent/Harness distinction (issue #859) and are excluded from the sweep — they're a record of what was proposed/studied at the time, not living documentation, and rewriting them to match later terminology would misrepresent that history (same principle already applied to not backfilling PR #1233's missing blog post).

**Tech Stack:** Python 3 stdlib (argparse help strings, docstrings, `#` comments). No new tests — this is a prose-consistency change with no behavioral surface to unit test; verification is a targeted grep sweep plus the existing full test suite (to confirm no accidental behavioral edit).

**Decisions locked for this plan:**
- **Canonical terms:** already decided in `docs/glossary-agent-vs-harness.md` (Agent = role/charter/identity; Harness = execution backend). This plan does not re-litigate that decision — it applies it.
- **In scope:** `--help` strings, docstrings, and `#` comments in `synlynk/*.py` that use "agent" to mean an execution backend (Claude/Agy/Codex/Grok/local) or "harness" to mean a role identity.
- **Out of scope (deferred to Task 3 follow-up issue):** renaming CLI subcommands/flags (`synlynk agent`, `--agent`, `--as-agent`, `agent configure`), DB column/table names (`agent` columns across `capability_ratings`, `daemon_jobs`, etc.), and any public API surface. These conflate both meanings today (e.g. `synlynk agent configure <name>` — "configure a specific agent's harness" — the subcommand noun and the object it configures use different senses of the word) and renaming them is a breaking change needing its own migration/deprecation plan.
- **Out of scope (excluded, not deferred):** `docs/*-human-agent-hybrid-workgroup-study.md`, `docs/multi-agent-orchestration-proposal.md` — historical documents, left as-is.

---

### Task 1: Sweep `synlynk/cli.py` help/docstring text

**Files:**
- Modify: `synlynk/cli.py`

- [ ] **Step 1: Inventory current misuses**

Run: `grep -n 'help=' synlynk/cli.py | grep -iE "\bagent\b"` and manually classify each hit into one of three buckets:
1. Refers to an execution backend (Claude/Agy/Codex/Grok/local) → reword to "harness"
2. Refers to the CLI subcommand/flag itself (`synlynk agent`, `--agent NAME` where NAME is a role like `qa`/`architect`) → leave as-is (out of scope per plan header)
3. Ambiguous / genuinely refers to a role identity → leave as-is (already correct)

From the survey done during planning, these lines are bucket 1 (execution-backend sense, need rewording):
- `synlynk/cli.py:225` — `help="Comma-separated agent set to generate files for (claude,agy,codex,grok)")` → `help="Comma-separated harness set to generate files for (claude,agy,codex,grok)")`
- `synlynk/cli.py:233` — `help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in agent files)")` → `help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in harness files)")`
- `synlynk/cli.py:256` — `"decide", help="Convene a multi-agent panel and optionally record a Decision"` → leave as-is: this refers to multiple role identities deliberating, not execution backends — bucket 3, already correct.
- `synlynk/cli.py:261` — `help="Comma-separated agent names, e.g. claude,agy,codex"` → `help="Comma-separated harness names, e.g. claude,agy,codex"`
- `synlynk/cli.py:338` — `"probe", help="Probe agent harness capability and record compatibility"` → `help="Probe harness capability and record compatibility"` (drop the redundant/conflated "agent")
- `synlynk/cli.py:347` — `help="Apply a targeted remediation for the named agent (agy only)")` → `help="Apply a targeted remediation for the named harness (agy only)")`
- `synlynk/cli.py:418` — `"agent", help="Configure a specific agent's harness")` → subcommand name out of scope; help text already correctly distinguishes agent (role) from harness — leave as-is.
- `synlynk/dispatch.py:423` — `"""Translate permission strings into agent-specific CLI flags."""` → `"""Translate permission strings into harness-specific CLI flags."""`

- [ ] **Step 2: Apply the reworded lines**

Edit the exact lines identified in Step 1 (buckets classified as 1) in `synlynk/cli.py` and `synlynk/dispatch.py`. Do not touch any subcommand names, flag names (`--agent`, `--as-agent`), or DB/schema identifiers.

- [ ] **Step 3: Full-file re-scan for remaining execution-backend misuses**

Run: `grep -n '#.*\bagent\b' synlynk/cli.py synlynk/dispatch.py synlynk/probe.py synlynk/quota.py synlynk/capability_sweep.py` and `grep -n '""".*\bagent\b' -r synlynk/*.py`. For each hit, classify per the same three buckets as Step 1. Reword any bucket-1 hits found. This step exists because the Step 1 inventory was done during planning and may not be exhaustive — re-verify against the current file state before treating the sweep as complete.

- [ ] **Step 4: Verify no CLI flag, subcommand, or DB identifier was touched**

Run: `git diff -- synlynk/*.py` and manually confirm every changed line is inside a `help=` string, a `"""docstring"""`, or a `#` comment — never inside `add_argument("--agent"`, `add_parser("agent"`, a dict key, a DB column reference, or a function/variable name.

- [ ] **Step 5: Run the full test suite to confirm zero behavioral change**

Run: `python3 -m pytest -q`
Expected: identical pass/fail/skip counts to the pre-existing baseline (2 pre-existing sqlite-locking flakes, all else passing) — a prose-only change should produce exactly zero test delta.

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/dispatch.py
git commit -m "docs: standardize harness vs agent terminology in CLI help/docstrings (#1202)"
```

---

### Task 2: Sweep remaining `synlynk/*.py` files (comments/docstrings only)

**Files:**
- Modify: `synlynk/probe.py`, `synlynk/quota.py`, `synlynk/capability_sweep.py`, `synlynk/__init__.py`, `synlynk/wizard.py`, `synlynk/jobs.py`, `synlynk/costs.py`, `synlynk/db.py` (only if Step 1 below finds real hits — do not touch files with none)

- [ ] **Step 1: Inventory per file**

For each file in the Files list, run: `grep -n '#.*\bagent\b\|""".*\bagent\b' <file>` and classify every hit per the same three buckets as Task 1 Step 1. Most hits will be bucket 2/3 (already correct — these files' heavy "agent" usage is largely the `--as-agent <role>` role-identity flag and DB `agent` columns, which are out of scope). Only reword genuine bucket-1 hits (a comment/docstring calling an execution backend an "agent").

- [ ] **Step 2: Apply reworded lines**

Edit only the confirmed bucket-1 hits found in Step 1. If a file has zero bucket-1 hits, skip it — do not make cosmetic edits for their own sake.

- [ ] **Step 3: Verify no identifiers touched**

Run: `git diff -- synlynk/*.py` and confirm every changed line is inside a comment or docstring, consistent with Task 1 Step 4's check.

- [ ] **Step 4: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: identical baseline counts, zero delta.

- [ ] **Step 5: Commit**

```bash
git add synlynk/probe.py synlynk/quota.py synlynk/capability_sweep.py synlynk/__init__.py synlynk/wizard.py synlynk/jobs.py synlynk/costs.py synlynk/db.py
git commit -m "docs: standardize harness vs agent terminology in remaining modules (#1202)"
```

(If Task 2 Step 1 finds zero bucket-1 hits across all listed files, skip Steps 2-5 and note in the PR description that the remaining modules were audited and found already consistent — no empty commit.)

---

### Task 3: File the deferred CLI/DB rename decision as a follow-up issue

**Files:** none (GitHub issue only)

- [ ] **Step 1: File the issue**

Title: "Decide: rename `synlynk agent`/`--agent`/`--as-agent` CLI surface and DB `agent` columns for Harness/Agent clarity (follow-up to #1202)"

Body must cover:
- The conflation found during #1202's sweep: `synlynk agent configure <name>` where `<name>` is actually a harness (claude/agy/codex/grok), while `--as-agent <role>` elsewhere takes an actual Agent role (qa/architect/etc.) — same CLI namespace, two different senses of "agent."
- That any rename here is a breaking CLI/schema change (existing scripts, muscle memory, DB migrations) and needs its own deprecation-path decision before a sweep, same caveat #1202 itself carried before this plan.
- Link back to #1202 and `docs/glossary-agent-vs-harness.md`.

Label: `tech-debt`.

No commit for this task — GitHub issue only.

---

## Self-Review Notes

- **Spec coverage:** #1202 asks to (1) decide the canonical terms — already done in `docs/glossary-agent-vs-harness.md` — and (2) sweep for inconsistent usage. Tasks 1-2 do the sweep, scoped to non-breaking prose; Task 3 explicitly tracks the breaking-surface decision #1202 flagged as a prerequisite ("This needs a decision before any rename sweep is dispatched") rather than silently skipping it.
- **No placeholders:** every reworded line in Task 1 is literal, from an actual current-state grep survey done during planning, not "similar edits."
- **Type/signature consistency:** N/A — no functions/types introduced or changed, prose-only.
- **Scope discipline:** explicitly excludes CLI flags/subcommands, DB columns, and historical proposal docs, with rationale for each exclusion stated in the Architecture section — matches this repo's own precedent (not backfilling PR #1233's blog post) for not rewriting history to look consistent after the fact.
