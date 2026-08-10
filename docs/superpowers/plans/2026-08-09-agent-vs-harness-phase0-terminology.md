# Agent vs Harness — Phase 0 Terminology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize the distinction between **Agent** (a persistent identity+role+charter — the 8 roles in `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §2: pm, architect, tpm, dev, designer, qa, marketing, synlynk-bot) and **Harness** (a swappable execution backend — Claude, Agy, Grok, Codex, local) across this repo's docs and auto-generated instruction files, with no new code infrastructure.

**Architecture:** This is a docs-and-generator-template fix, not a new subsystem. One Python function (`synlynk/probe.py`'s `_repair_capability_allocation_sop()` and its static fallback `_CAPABILITY_ALLOCATION_SOP`) currently generates a table titled `| Role | Agent | Tasks |` where the "Agent" column actually lists Harnesses (Claude/Agy/Grok/Codex) — this is the single largest source of the terminology conflation, since it's synced into every harness's directive file (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md) via `synlynk doctor --fix` / `roles --fix`. Everything else in this plan is a hand-edited doc: a new glossary doc, a hand-maintained (non-fenced) terminology section in CLAUDE.md, a comment in `.synlynk/roles.yaml`, and two one-line wording fixes in README.md/SYNLYNK_GUIDE.md.

**Tech Stack:** Python 3 stdlib, pytest, Markdown, YAML.

**Role split note:** Per this repo's Default Agent Role policy, Claude (pm/architect) does design, plan-writing, and review only. Every task below is written to be executed by a dispatched implementer (Codex for the Python/test task; Agy for the Markdown/YAML doc tasks), not by Claude directly. Claude's job after this plan is committed is to dispatch each task, then review.

---

## File Structure

| File | Change | Why |
|---|---|---|
| `docs/glossary-agent-vs-harness.md` | **Create** | Canonical, linkable definition of Agent vs Harness. Every other doc change in this plan links back here instead of re-explaining the distinction inline. |
| `synlynk/probe.py` | **Modify** (`_repair_capability_allocation_sop`, `_CAPABILITY_ALLOCATION_SOP`) | Source of the auto-generated `## Capability-Based Task Allocation` table synced into CLAUDE.md/GEMINI.md/AGENTS.md/GROK.md. Column header `Agent` → `Harness`; add a one-line terminology note + glossary link into the generated block. |
| `tests/test_synlynk.py` | **Modify** (add test) | Lock in the corrected column header so a future edit can't silently reintroduce the conflation. |
| `CLAUDE.md` | **Modify** (hand-maintained section, not the `synlynk-managed` fence) | Add a short "Terminology: Agent vs Harness" section near the top, linking to the glossary. |
| `.synlynk/roles.yaml` | **Modify** (add header comment) | Clarify that this file's `roles:` list is the Agent roster (§2 of the design spec), not a Harness list. |
| `README.md` | **Modify** (2 lines) | Add a terminology callout near the top; fix line 260's "every AI tool, every agent" phrasing which conflates both concepts in one sentence. |
| `SYNLYNK_GUIDE.md` | **Modify** (1 line) | Line 3 says "your AI agent" when it means the harness reading the instructions (Claude/Gemini/Codex CLI) — reword to "AI harness". |

**Explicitly out of scope for this phase** (per spec §10 Phase 0: "no new infrastructure" and per the user's own scoping to docs/terminology, not a code rename):
- Renaming Python identifiers, function names, module names, or CLI flags that use "agent" (e.g. `AGENT_CAPABILITY_BASELINES`, `--force-agent`, `synlynk/support_engineer.py`, `dispatch_agent()`). These are internal/API surface — renaming them is a breaking-change-shaped refactor that belongs to a later phase if ever, not Phase 0.
- Rewriting every "agent" mention in `README.md`'s roadmap table (lines 260-274) or in `docs/*hybrid-agent-workgroup-study*.md` files — these are historical/narrative content, not living instructions; a full copy pass belongs to marketing's Phase-0-adjacent follow-up, not this plan (see Task 5's note).
- The user's personal `~/.claude/CLAUDE.md` (global config) — out of scope; this plan only touches project-scoped files.
- Fixing the `#426` GitHub-write-routing text baked into `_repair_capability_allocation_sop()`'s generated block (it still says "Route any task that requires GitHub write actions to Grok by default", which §3.2 of the design spec retired). This is a **policy content** fix, not a terminology fix — it belongs to whichever future plan implements §3's dispatch-policy code change (already listed as out of scope in the design spec's §11). Task 2 below explicitly leaves this sentence's content untouched and only fixes the column header around it — see Task 2 Step 6 for the follow-up issue this plan files instead of fixing it inline.

---

### Task 1: Create the Agent vs Harness glossary doc

**Files:**
- Create: `docs/glossary-agent-vs-harness.md`

- [ ] **Step 1: Write the glossary doc**

```markdown
# Glossary: Agent vs Harness

synlynk uses two related but distinct terms. Getting them right matters because the design spec at
`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` builds an entire dispatch
and calibration model on the distinction.

## Agent

An **Agent** is a persistent identity: a role, a charter, and (per the design spec's §10 roadmap)
eventually memory and access grants of its own. Agents are *what* work happens under and *who* is
accountable for it.

synlynk's 8 Agents (defined in the design spec's §2) are:

| Agent | Charter |
|---|---|
| pm | Represents the human user; owns major decisions and Named Release sign-off |
| architect | Owns Spec + Plan; does PR review and holds merge authority |
| tpm | Tasking, tracking, and reporting |
| dev | Implementation |
| designer | UI/UX |
| qa | Test coverage, CI/CD, IaC, deployments |
| marketing | End-user-facing comms, including every PR's blog post |
| synlynk-bot | Shared automation identity for durable Agents' scheduled writes (not itself a role) |

Each Agent has a GitHub App identity (provisioned under issue #859), so its actions attribute to the
Agent, not to whichever Harness happened to execute them.

## Harness

A **Harness** is a swappable *execution backend* — the AI CLI tool that actually runs a dispatched
task. synlynk's harnesses today are:

- Claude
- Agy (Gemini)
- Grok
- Codex
- local

Harnesses have no charter and no standing accountability of their own — they're selected per-task by
capability fit (see the design spec's §3, "Role → Tool-Agent Dispatch Policy"). The same Agent's work
(e.g. `dev`) can be executed by different Harnesses on different tasks.

## Why the distinction matters

Before issue #859, synlynk had no Agent identity layer — every GitHub write from every Harness
attributed to one shared personal identity (issue #569). Conflating "Agent" and "Harness" in
docs/config made it easy to write policy (like issue #426's "route GitHub writes to Grok by default")
that was really compensating for a missing Agent-identity layer, not a real Harness-capability
constraint. The design spec's §3.2 retires that policy now that Agent identity is real.

**Rule of thumb:** if you're asking "who is accountable for this and what's their charter," you mean
Agent. If you're asking "which AI CLI tool should execute this," you mean Harness.

## Related docs

- `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` — full Agent role design,
  dispatch policy, and the Phase 0-4 roadmap this glossary is Phase 0 of.
- `CLAUDE.md`'s "Terminology: Agent vs Harness" section — the short in-repo pointer to this doc.
```

- [ ] **Step 2: Commit**

```bash
git add docs/glossary-agent-vs-harness.md
git commit -m "docs: add Agent vs Harness glossary (Phase 0 terminology)"
```

---

### Task 2: Fix the auto-generated Capability-Based Task Allocation table's terminology

**Files:**
- Modify: `synlynk/probe.py:53-58` (static `_CAPABILITY_ALLOCATION_SOP` fallback block)
- Modify: `synlynk/probe.py:862-887` (`_repair_capability_allocation_sop()`, the dynamic/live generator)
- Test: `tests/test_synlynk.py`

This is the single highest-leverage fix: `_repair_capability_allocation_sop()` is what `synlynk doctor --fix` / `roles --fix` writes into the `synlynk-managed` fence of **every** harness's directive file (CLAUDE.md, GEMINI.md, AGENTS.md, GROK.md), so fixing it here fixes the conflation everywhere it's auto-synced, in one place.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_synlynk.py` (place near `test_sop_section_headers_defined`, using the same import style already in the file):

```python
def test_capability_allocation_table_uses_harness_not_agent_header():
    from synlynk.probe import _CAPABILITY_ALLOCATION_SOP, _repair_capability_allocation_sop

    assert "| Role | Harness | Tasks |" in _CAPABILITY_ALLOCATION_SOP
    assert "| Role | Agent | Tasks |" not in _CAPABILITY_ALLOCATION_SOP

    cfg = {
        "roles": {
            "codex": ["implement", "test", "refactor"],
            "agy": ["css", "templates", "content"],
        },
        "workgroup_agents": ["codex", "agy"],
    }
    generated = _repair_capability_allocation_sop(cfg)
    assert "| Role | Harness | Tasks |" in generated
    assert "| Role | Agent | Tasks |" not in generated
    assert "docs/glossary-agent-vs-harness.md" in generated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py::test_capability_allocation_table_uses_harness_not_agent_header -v`
Expected: FAIL — `_CAPABILITY_ALLOCATION_SOP` still contains `| Role | Agent | Tasks |`, and the generated table has no glossary link.

- [ ] **Step 3: Fix the static fallback block**

In `synlynk/probe.py`, find `_CAPABILITY_ALLOCATION_SOP` (around line 53):

```python
_CAPABILITY_ALLOCATION_SOP = """\
## Capability-Based Task Allocation
| Role | Agent | Tasks |
| :--- | :--- | :--- |
| Python/CLI/tests | Codex | Python, CLI, tests |
| HTML/CSS/content/docs | Agy | HTML, CSS, content, docs |
| canvas/JS/infra | Grok | canvas, JS, infra |
| PM/review/deploy/brainstorm | Claude | PM, review, deploy, brainstorm |
| GitHub write actions | **Grok only** | `gh pr review`, `gh pr merge`, `gh pr create`, `gh issue comment` (Agy is viable only when an operator has already confirmed scoped allow-rules in `~/.gemini/antigravity-cli/settings.json`) |
```

Replace the header line and the "Agent" column header only — leave every row's content and the GitHub-write-routing row's text untouched (that's a policy question, not a terminology question, and out of scope per this plan's "File Structure" section):

```python
_CAPABILITY_ALLOCATION_SOP = """\
## Capability-Based Task Allocation

**Note:** "Harness" below means the execution backend (Claude/Agy/Grok/Codex) that runs a task, not
the Agent (role) doing the work. See `docs/glossary-agent-vs-harness.md`.

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| Python/CLI/tests | Codex | Python, CLI, tests |
| HTML/CSS/content/docs | Agy | HTML, CSS, content, docs |
| canvas/JS/infra | Grok | canvas, JS, infra |
| PM/review/deploy/brainstorm | Claude | PM, review, deploy, brainstorm |
| GitHub write actions | **Grok only** | `gh pr review`, `gh pr merge`, `gh pr create`, `gh issue comment` (Agy is viable only when an operator has already confirmed scoped allow-rules in `~/.gemini/antigravity-cli/settings.json`) |
```

Do not modify anything after this block in the same triple-quoted string (the closing `"""` and whatever follows it) — only the header line and the two lines shown above change.

- [ ] **Step 4: Fix the dynamic generator**

In `synlynk/probe.py`, find `_repair_capability_allocation_sop()` (around line 862):

```python
def _repair_capability_allocation_sop(cfg: dict) -> str:
    cfg_roles = cfg.get("roles") or {}
    ordered_agents = _repair_config_agents(cfg)
    if not ordered_agents:
        ordered_agents = [agent for agent in cfg_roles.keys()]

    rows = []
    for agent in ordered_agents:
        role_list = _repair_role_list(cfg_roles.get(agent))
        if not role_list:
            continue
        role_label = " / ".join(role_list)
        rows.append(f"| {role_label} | {_repair_agent_label(agent)} | {', '.join(role_list)} |")

    if not rows:
        return (
            "## Capability-Based Task Allocation\n"
            "No repo-specific roles are recorded in `.synlynk/config.json`; keep work scoped to the "
            "agent you were assigned and follow the repo's own routing notes.\n"
        )

    escalation_target = _repair_escalation_target(cfg) or "the configured PM/reviewer"
    table = "\n".join([
        "## Capability-Based Task Allocation",
        "| Role | Agent | Tasks |",
        "| :--- | :--- | :--- |",
        *rows,
        f"Do not start a task outside your role column without explicit approval from {escalation_target}.",
        "",
        "**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).",
        "",
        "This table is generated from `.synlynk/config.json` so it tracks the repo's own routing "
        "rather than synlynk's default fleet assumptions.",
    ])
    return table + "\n"
```

Replace with (only the header string, the empty-table fallback wording, and the closing note change — the `#426` GitHub-write-routing paragraph's content is untouched, per this plan's scope):

```python
def _repair_capability_allocation_sop(cfg: dict) -> str:
    cfg_roles = cfg.get("roles") or {}
    ordered_agents = _repair_config_agents(cfg)
    if not ordered_agents:
        ordered_agents = [agent for agent in cfg_roles.keys()]

    rows = []
    for agent in ordered_agents:
        role_list = _repair_role_list(cfg_roles.get(agent))
        if not role_list:
            continue
        role_label = " / ".join(role_list)
        rows.append(f"| {role_label} | {_repair_agent_label(agent)} | {', '.join(role_list)} |")

    if not rows:
        return (
            "## Capability-Based Task Allocation\n"
            "No repo-specific roles are recorded in `.synlynk/config.json`; keep work scoped to the "
            "harness you were assigned and follow the repo's own routing notes.\n"
        )

    escalation_target = _repair_escalation_target(cfg) or "the configured PM/reviewer"
    table = "\n".join([
        "## Capability-Based Task Allocation",
        "",
        "**Note:** \"Harness\" below means the execution backend (Claude/Agy/Grok/Codex) that runs a "
        "task, not the Agent (role) doing the work. See `docs/glossary-agent-vs-harness.md`.",
        "",
        "| Role | Harness | Tasks |",
        "| :--- | :--- | :--- |",
        *rows,
        f"Do not start a task outside your role column without explicit approval from {escalation_target}.",
        "",
        "**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).",
        "",
        "This table is generated from `.synlynk/config.json` so it tracks the repo's own routing "
        "rather than synlynk's default fleet assumptions.",
    ])
    return table + "\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py::test_capability_allocation_table_uses_harness_not_agent_header -v`
Expected: PASS

- [ ] **Step 6: Run the full existing test suite to check for regressions**

Run: `python3 -m pytest tests/test_synlynk.py -v`
Expected: All pass, including `test_sop_section_headers_defined` and `test_directive_templates_contain_sop_headers` (these check header text presence like `"## Capability-Based Task Allocation"`, which is unchanged — only the `Agent`→`Harness` column label changed, so they should be unaffected; if any fails, read its assertion and confirm it isn't asserting the literal old column text before changing test code).

- [ ] **Step 7: File a follow-up issue for the stale #426 policy text**

The generated table's `#426` GitHub-write-routing paragraph still says "Route any task that requires GitHub write actions to **Grok by default**", which the design spec's §3.2 retired (`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`). This plan intentionally does not change that paragraph's content — it's a policy fix, not a terminology fix, and belongs to whichever future plan implements §3's dispatch-policy code change. File it so it isn't silently forgotten:

```bash
gh issue create --title "Auto-generated Capability-Based Task Allocation table still states retired #426 Grok-default GitHub-write policy" \
  --body "synlynk/probe.py's _repair_capability_allocation_sop() (synced into every harness's directive file via 'synlynk doctor --fix') still generates a paragraph reading 'Route any task that requires GitHub write actions to Grok by default'. Design spec docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md §3.2 retired this policy: GitHub-write tasks now route by ordinary per-role capability fit, with Codex excluded only on execution-capability grounds (workspace-write sandbox blocks api.github.com egress). Update _repair_capability_allocation_sop()'s generated paragraph to reflect the new policy once the dispatch-policy code change from §3 lands. Not fixed in the Phase 0 terminology plan (docs/superpowers/plans/2026-08-09-agent-vs-harness-phase0-terminology.md) because it's a policy content change, not a terminology fix." \
  --label bug
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/probe.py tests/test_synlynk.py
git commit -m "fix: rename Agent to Harness in auto-generated capability allocation table (Phase 0 terminology)"
```

---

### Task 3: Sync the fixed template into this repo's own directive files

**Files:**
- Modify: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md` (the `synlynk-managed` fenced sections only — these are regenerated, not hand-edited)

Task 2 fixed the *generator*. This task runs it so the fix actually lands in this repo's own directive files (otherwise Task 2's fix only takes effect the next time someone unrelated runs `doctor --fix`).

- [ ] **Step 1: Run the repair in dry-run mode first to preview the diff**

Run: `python3 bin/synlynk.py doctor --fix --dry-run`
Expected: Output shows the `## Capability-Based Task Allocation` section in each directive file changing from `| Role | Agent | Tasks |` to `| Role | Harness | Tasks |`, plus the new glossary-link note line. No other sections should be listed as changing.

- [ ] **Step 2: Apply the fix for real**

Run: `python3 bin/synlynk.py doctor --fix`
Expected: Exits 0. Directive files are modified in place.

- [ ] **Step 3: Verify the fence content changed correctly**

Run: `grep -A 5 "## Capability-Based Task Allocation" CLAUDE.md`
Expected: Shows `| Role | Harness | Tasks |` and the glossary-note line, inside the `synlynk-managed` fence (between the `# Harness Instructions (synlynk-managed — do not edit)` header and `<!-- /synlynk:harness -->`).

- [ ] **Step 4: Verify no unrelated fence content changed**

Run: `git diff CLAUDE.md GEMINI.md AGENTS.md GROK.md`
Expected: Only the `## Capability-Based Task Allocation` section's header line and the new note line differ per file; `## PR Review Discipline`, `## Brainstorm-First Policy`, `## Design → Plan → Build Sequence`, `## Cost Visibility`, `## Repo Hygiene` are unchanged. If any of those sections show unrelated diffs (e.g. a stale-timestamp regen), revert just that hunk before committing — this task's scope is the capability table only.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md GEMINI.md AGENTS.md GROK.md
git commit -m "chore: regenerate directive files with Harness terminology fix (Phase 0)"
```

---

### Task 4: Add a hand-maintained terminology section to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (hand-maintained area — insert after the `## What This Project Is` section, before `## Running the CLI`; this is outside the `synlynk-managed` fence, so it will not be touched or removed by `doctor --fix`)

- [ ] **Step 1: Insert the new section**

In `CLAUDE.md`, find the end of the `## What This Project Is` section (it ends right before the line `## Running the CLI`). Insert this new section immediately before `## Running the CLI`:

```markdown
## Terminology: Agent vs Harness

synlynk distinguishes two concepts that are easy to conflate:

- **Agent** — a persistent role identity with a charter (pm, architect, tpm, dev, designer, qa,
  marketing, synlynk-bot). Agents are *who* is accountable for work.
- **Harness** — a swappable execution backend (Claude, Agy, Grok, Codex, local) that runs a
  dispatched task. Harnesses are *how* work gets executed, selected per-task by capability fit.

Full definitions and rationale: `docs/glossary-agent-vs-harness.md`. Full role design: `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`.

```

- [ ] **Step 2: Verify placement**

Run: `grep -n "^## " CLAUDE.md | head -10`
Expected: `## Terminology: Agent vs Harness` appears between `## What This Project Is` and `## Running the CLI` in the output order.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Terminology: Agent vs Harness section to CLAUDE.md (Phase 0)"
```

---

### Task 5: Fix ambiguous "agent" wording in roles.yaml, README.md, and SYNLYNK_GUIDE.md

**Files:**
- Modify: `.synlynk/roles.yaml`
- Modify: `README.md:15`, `README.md:260`
- Modify: `SYNLYNK_GUIDE.md:3`

- [ ] **Step 1: Add a header comment to roles.yaml**

Current content of `.synlynk/roles.yaml`:

```yaml
roles:
  - dev
  - qa
  - pm
  - architect
  - synlynk-bot
  - tpm
  - designer
  - marketing
```

Replace with:

```yaml
# This is the Agent roster (persistent role identities), not a Harness list.
# See docs/glossary-agent-vs-harness.md and docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md §2.
roles:
  - dev
  - qa
  - pm
  - architect
  - synlynk-bot
  - tpm
  - designer
  - marketing
```

- [ ] **Step 2: Fix README.md line 15**

Current text (line 15):

```
synlynk is a Python CLI that turns your terminal into a hybrid workgroup — one human, multiple AI agents, shared project state. It injects scoped project context into every agent dispatch, routes tasks to the best available agent using a live capability ledger, and tracks costs and hallucination loops. A shared `project-docs/` directory keeps every tool in sync: Claude Code, Codex, and AGY all read the same context, decisions, and progress.
```

Replace with (the intro is describing Harnesses — Claude Code, Codex, AGY, Grok — being dispatched, so "AI agents" here should read "AI harnesses"; the rest of the sentence is unchanged):

```
synlynk is a Python CLI that turns your terminal into a hybrid workgroup — one human, multiple AI harnesses, shared project state. It injects scoped project context into every dispatch, routes tasks to the best available harness using a live capability ledger, and tracks costs and hallucination loops. A shared `project-docs/` directory keeps every tool in sync: Claude Code, Codex, and AGY all read the same context, decisions, and progress.
```

- [ ] **Step 3: Fix README.md line 260**

Current text (line 260):

```
synlynk's goal is to become the OS for multi-agent development — the substrate that keeps every AI tool, every agent, and every developer in sync across the full project lifecycle.
```

Replace with:

```
synlynk's goal is to become the OS for multi-agent development — the substrate that keeps every AI harness, every Agent role, and every developer in sync across the full project lifecycle.
```

- [ ] **Step 4: Fix SYNLYNK_GUIDE.md line 3**

Current text (line 3):

```
Apply these instructions to your AI agent (Global System Prompt, Gemini Custom Instructions, or Claude Project Instructions).
```

Replace with:

```
Apply these instructions to your AI harness (Global System Prompt, Gemini Custom Instructions, or Claude Project Instructions).
```

- [ ] **Step 5: Verify no other lines on the same files were touched**

Run: `git diff .synlynk/roles.yaml README.md SYNLYNK_GUIDE.md`
Expected: Exactly the 4 hunks described above (1 in roles.yaml, 2 in README.md, 1 in SYNLYNK_GUIDE.md) — nothing else changed. README's roadmap table (lines 260-274 in the original numbering, now shifted by the line-15 edit) and the historical `docs/*hybrid-agent-workgroup-study*.md` files are explicitly out of scope per this plan's File Structure section — do not touch them.

- [ ] **Step 6: Commit**

```bash
git add .synlynk/roles.yaml README.md SYNLYNK_GUIDE.md
git commit -m "docs: fix ambiguous agent/harness wording in roles.yaml, README, SYNLYNK_GUIDE (Phase 0)"
```

---

## Self-Review

**1. Spec coverage.** §10 Phase 0 requires: (a) terminology definitions — Task 1 (glossary) + Task 4 (CLAUDE.md section). (b) code/docs/roles.yaml/CLAUDE.md capability table updated — Task 2 (generator fix), Task 3 (regenerate this repo's own files), Task 5 (roles.yaml + README + SYNLYNK_GUIDE). (c) "no new infrastructure" — confirmed: no new modules, no new config schema, no new CLI commands anywhere in this plan. All 3 requirements are covered.

**2. Placeholder scan.** No TBD/TODO. Every step shows exact before/after code or exact file content. The one follow-up issue (Task 2 Step 7) is filed via a real `gh issue create` command with full body text, not left as a bare TODO.

**3. Type consistency.** `_repair_capability_allocation_sop(cfg: dict) -> str` signature is unchanged in Task 2 — only its internal string content changes, so no caller elsewhere in `synlynk/probe.py` needs updating. Verified via the earlier `grep -n "_repair_capability_allocation_sop"` survey (only one call site, inside `_build_repair_sop_block`, which passes through the return value unchanged).

**Scope check.** This is a single, small, docs-and-one-generator-function subsystem — appropriately sized for one plan, not decomposed further. Phases 1-4 each get their own plan when their turn comes, per the design spec's §10/§11.
