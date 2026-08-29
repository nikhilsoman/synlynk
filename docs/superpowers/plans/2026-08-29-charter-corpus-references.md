# Charter Corpus References Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For each of the 6 non-pm role charters (architect, tpm, dev, qa, designer, marketing), validate/derive charter content against the actual corpus of that role's work — devlog entries, commit history, project memory — instead of the generic spec-derived prose currently in `SEED_CHARTERS`, and document the sourcing in `docs/charters/corpus-references.md`.

**Architecture:** Charter content lives in two places: (1) `synlynk/agent_cli.py`'s `SEED_CHARTERS` dict — the durable, git-tracked source of truth used to seed a brand-new agent (`cmd_agent_init`); (2) each live agent's `~/.synlynk/workspaces/<id>/agents/<agent_id>/charter.md`, written by `agent_store.propose_charter_revision()` — not git-tracked, workspace-local runtime state. This PR only touches (1) plus the new reference doc. Bumping the 6 already-provisioned live agents' charters to match is a separate, no-PR operational step performed by Claude (PM/deploy role) after merge, mirroring how PR #1196 handled its own "migrate the 7 live charters to revision 3" step.

**Tech Stack:** Python stdlib only (matches project convention — see `synlynk/charter_schema.py`).

**Source material to mine (already present in the repo, read-only for this plan):**
- `project-docs/devlogs/nikhilsoman.md` (1223 lines) — the canonical record of who-did-what
- `project-docs/memory.md` (226 lines)
- `git log --oneline` (1329 commits) — filterable by keyword per role (e.g. `git log --oneline --grep="review\|merge" -i` for architect/qa signal)
- `docs/blog/*.md` — PR-level narrative detail devlog entries sometimes summarize away
- Existing charter content itself, `synlynk/agent_cli.py:12-183` (`SEED_CHARTERS`), as the "before" baseline

**Non-goals (explicitly out of scope, do not touch):**
- `pm`'s charter — already restored/grounded in PR #1196, do not re-derive
- `synlynk-bot`'s charter — infra catch-all with no real corpus of "decisions" to mine; leave as-is unless the audit finds it's actually inaccurate (unlikely — it's intentionally minimal)
- Bumping the live `~/.synlynk/workspaces/...` charter.md files — that's a post-merge operational step, not part of this PR (see Task 3)
- Renaming `--as-agent`/`SEED_CHARTERS` identifiers — out of scope, unrelated to #1255

---

### Task 1: Audit + update dev, qa, architect

**Files:**
- Create: `docs/charters/corpus-references.md`
- Modify: `synlynk/agent_cli.py:13-101` (the `"dev"`, `"qa"`, `"architect"` entries in `SEED_CHARTERS`)
- Test: `tests/test_agent_cli.py` (existing tests must still pass; see note below)

- [ ] **Step 1: Read the corpus**

Read `project-docs/devlogs/nikhilsoman.md` and `project-docs/memory.md` in full. Run these to find role-specific signal in commit history:

```bash
git log --oneline --grep="review\|merge\|architect" -i | head -60
git log --oneline --grep="qa\|test\|verify" -i | head -60
git log --oneline --grep="dispatch\|implement\|codex\|grok\|agy" -i | head -60
```

For each of `dev`, `qa`, `architect`, note concrete evidence of what the role has actually done in this project — not generic job-title duties. Example of the kind of gap to look for (this is the pattern PR #1196 found and fixed for `pm`): the current `architect` charter (`synlynk/agent_cli.py:82-101`) says "writes and approves both the Spec and the Plan... does PR code review" — but the actual devlog record (see `project-docs/devlogs/nikhilsoman.md`'s 2026-08-24 and 2026-08-09 entries) shows *Claude*, operating in the pm-adjacent PM/reviewer role defined by this repo's own `CLAUDE.md`, has been doing spec-approval, PR review, and merge — not a separate "architect" identity that has ever actually run. Document whether `architect`'s charter should note it is provisioned-but-largely-unexercised so far, if that's what the corpus shows, rather than writing prose that implies a track record that doesn't exist yet.

- [ ] **Step 2: Write `docs/charters/corpus-references.md`**

Create the file with this structure (fill in `<...>` with what Step 1 actually found — do not invent history):

```markdown
# Charter Corpus References

For each role below: what corpus (devlog entries, commit ranges, memory files) was
consulted to validate or update that role's charter content in `synlynk/agent_cli.py`'s
`SEED_CHARTERS`, and what (if anything) changed as a result. Use this to check future
charter edits against real evidence rather than plausible-sounding prose.

Excluded: `pm` (already grounded via PR #1196) and `synlynk-bot` (infra catch-all,
no meaningful corpus of independent decisions to mine).

## dev

**Sources consulted:** <devlog date ranges>, <commit grep/range used>, <memory.md
sections if any>

**Findings:** <what the corpus shows dev has actually done — e.g. "every dispatched
Codex/Agy/Grok implementer job in the devlog record matches the charter's
'dispatch-triggered only, no autonomous loop' framing; no evidence of dev
self-initiating work">

**Charter changes made:** <none | specific line(s) changed and why>

## qa

...

## architect

...

## tpm

...

## designer

...

## marketing

...
```

- [ ] **Step 3: Update `SEED_CHARTERS["dev"]`, `SEED_CHARTERS["qa"]`, `SEED_CHARTERS["architect"]` in `synlynk/agent_cli.py`**

Only change the `## Instructions` / `## Authority & Escalation` / `## Workflow Ownership` body text where Step 1's findings support a change. Do not touch the YAML frontmatter block (`schema_version`, `role`, `description`, `durability`, `tools`, `credentials`) — those are structural, not corpus-derived. Preserve the existing `\n`-joined Python string literal style used throughout the dict.

If a role's existing text already matches the corpus (a real possibility — these charters were restored once already in #1196 and may already be accurate), leave it unchanged and say so explicitly in `corpus-references.md`'s "Charter changes made" line — do not force a change just to show work.

- [ ] **Step 4: Validate against the schema**

```bash
python3 -c "
from synlynk import charter_schema
from synlynk.agent_cli import SEED_CHARTERS
for role in ('dev', 'qa', 'architect'):
    charter_schema.validate_charter(SEED_CHARTERS[role])
    print(f'{role}: OK')
"
```
Expected: all three print `OK`, no `CharterValidationError`.

- [ ] **Step 5: Run the existing test suite**

```bash
python3 -m pytest tests/test_agent_cli.py -q
```
Expected: all pass (the `test_cmd_agent_init_seeds_charter`-style test at `tests/test_agent_cli.py:371` compares against `agent_cli.SEED_CHARTERS["dev"]` itself, so it stays green regardless of content changes — confirm this holds).

- [ ] **Step 6: Commit**

```bash
git add docs/charters/corpus-references.md synlynk/agent_cli.py
git commit -m "docs: ground dev/qa/architect charters in project corpus (#1199)"
```

---

### Task 2: Audit + update tpm, designer, marketing

**Files:**
- Modify: `docs/charters/corpus-references.md` (append `tpm`, `designer`, `marketing` sections — file already exists from Task 1)
- Modify: `synlynk/agent_cli.py:102-163` (the `"tpm"`, `"designer"`, `"marketing"` entries in `SEED_CHARTERS`)
- Test: `tests/test_agent_cli.py`

- [ ] **Step 1: Read the corpus for these 3 roles**

Same devlog/memory read as Task 1 Step 1 (already read once — re-skim with these roles' lens). Additional targeted greps:

```bash
git log --oneline --grep="tpm\|sweep\|dispatch\|ticket" -i | head -60
git log --oneline --grep="blog\|marketing\|designer\|css\|ui" -i | head -60
```

`tpm` has real, extensive corpus signal — `synlynk/tpm_sweep.py` and the 2026-08-24 devlog entry (ticket-driven approval auto-resume) are concretely tpm's domain per the charter's own "consuming GOVERNS' existing lifecycle-enforcement event contract" line. Confirm this framing still matches current `tpm_sweep.py` behavior. `designer` and `marketing` are dispatch-only roles routed to Agy — check whether the corpus shows any dispatched work actually landing under those charters specifically (as opposed to generic "content"/"docs" dispatch tasks that were never tagged to a role), and say so plainly in the doc if the corpus is thin — a charter for a role with little track record yet should say what it's *for*, not fabricate a history.

- [ ] **Step 2: Append `tpm`, `designer`, `marketing` sections to `docs/charters/corpus-references.md`**

Same structure as Task 1 Step 2's template, filled in for these 3 roles.

- [ ] **Step 3: Update `SEED_CHARTERS["tpm"]`, `SEED_CHARTERS["designer"]`, `SEED_CHARTERS["marketing"]` in `synlynk/agent_cli.py`**

Same constraints as Task 1 Step 3 (body text only, preserve frontmatter and string style, no-op is a valid outcome).

- [ ] **Step 4: Validate against the schema**

```bash
python3 -c "
from synlynk import charter_schema
from synlynk.agent_cli import SEED_CHARTERS
for role in ('tpm', 'designer', 'marketing'):
    charter_schema.validate_charter(SEED_CHARTERS[role])
    print(f'{role}: OK')
"
```

- [ ] **Step 5: Run the full test suite**

```bash
python3 -m pytest -q
```
Expected: same pre-existing baseline as before this PR (2 `database is locked` flakes in `test_agent_quota_tracking.py`/`test_roles.py`, 0 new failures).

- [ ] **Step 6: Commit**

```bash
git add docs/charters/corpus-references.md synlynk/agent_cli.py
git commit -m "docs: ground tpm/designer/marketing charters in project corpus (#1199)"
```

---

### Task 3 (post-merge, performed by Claude directly — not dispatched): Bump live charter revisions

This is an operational/deploy step, not implementation — it does not touch any file in the PR, so it runs after merge, on `main`, using the already-provisioned local workspace's live agents. It is a deploy action within the PM role, same category as `gh pr merge` itself.

```bash
python3 -c "
from synlynk import agent_store
from synlynk.agent_cli import SEED_CHARTERS

for role in ('dev', 'qa', 'architect', 'tpm', 'designer', 'marketing'):
    entries = agent_store.list_agents()
    entry = next(
        (e for e in entries
         if any(a['kind'] == 'role_slug' and a['value'] == role for a in e['aliases'])),
        None,
    )
    if entry is None:
        print(f'{role}: no live agent provisioned, skipping')
        continue
    content, revision = agent_store.read_charter(entry['agent_id'])
    if content == SEED_CHARTERS[role]:
        print(f'{role}: unchanged, skipping')
        continue
    new_rev = agent_store.propose_charter_revision(
        entry['agent_id'], SEED_CHARTERS[role], actor='pm', parent_revision=revision,
    )
    print(f'{role}: revision {revision} -> {new_rev}')
"
```

Confirm each updated role's new charter renders correctly:

```bash
python3 -c "
from synlynk.charter_injection import render_charter_section
print(render_charter_section('.')[:500])
"
```
(Only meaningfully checks whichever role is the current `human_authority_role` — spot check others via `agent_store.read_charter(<agent_id>)` directly if needed.)

Note the before/after revision numbers in the PR's merge commentary or a devlog entry — this is the same kind of "migrated all N live charters to revision M" note PR #1196 made.

---

## Self-Review Notes

- **Spec coverage:** Issue #1199 asks for (a) derive/validate content against the real corpus for the 6 non-pm/non-bot roles — Tasks 1-2; (b) document which sources informed each role — `docs/charters/corpus-references.md`, built incrementally across Tasks 1-2; (c) update charter content where gaps are found — Tasks 1-2 Step 3, explicitly allowing "no change" as a valid finding. Bumping the live (non-git) charter store isn't literally asked for by the issue text, but is necessary for the audit to have any real effect beyond the next `synlynk agent init` — included as Task 3, scoped as a post-merge operational step so it doesn't block PR review.
- **Placeholder scan:** No TBD/"add appropriate"/deferred steps — every step has concrete commands or a concrete template. The `<...>` placeholders in Task 1 Step 2's template are explicitly for the *implementer* to fill from their own corpus research, not for a future pass — consistent with the "No Placeholders" rule since a doc's actual prose content, by definition, cannot be written before the research step that precedes it in the same task.
- **Type/consistency:** `SEED_CHARTERS` dict key names, `agent_store.propose_charter_revision`/`read_charter`/`list_agents` signatures, and `charter_schema.validate_charter` all verified against current source (`synlynk/agent_cli.py`, `synlynk/agent_store.py`, `synlynk/charter_schema.py`) before writing this plan — no invented APIs.
