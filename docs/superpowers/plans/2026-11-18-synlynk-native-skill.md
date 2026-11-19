# synlynk-Native Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained `skills/synlynk/` plugin — 13 ceremony skills forked from the installed `superpowers` plugin with synlynk SOPs woven in, 4 new synlynk-unique skills, a `using-synlynk` meta-skill, per-harness manifest adapters, and a `SessionStart` hook — then collapse `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.cursorrules`'s duplicated shared-protocol content into thin pointers generated from that tree, closing issue #5367.

**Architecture:** One canonical markdown skill tree at `skills/synlynk/`, mirroring the proven shape of the installed superpowers plugin (`~/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/`) exactly: per-harness manifest files at the repo root pointing into the tree, one `SessionStart` hook forcibly injecting a meta-skill, and all synlynk CLI operations referenced as plain Bash shell-outs (no new runtime infrastructure — this is Stage 0 of `docs/superpowers/specs/2026-11-18-synlynk-native-skill-design.md`).

**Tech Stack:** Markdown (skills), JSON (plugin manifests, hooks), a small Python generator script (collapses duplication into the 4 instruction files), no application code changes.

---

## File Structure

```
skills/synlynk/
  using-synlynk/SKILL.md
  brainstorming/SKILL.md
  writing-plans/SKILL.md
  writing-skills/SKILL.md
  test-driven-development/SKILL.md
  systematic-debugging/SKILL.md
  using-git-worktrees/SKILL.md
  subagent-driven-development/SKILL.md
  dispatching-parallel-agents/SKILL.md
  finishing-a-development-branch/SKILL.md
  requesting-code-review/SKILL.md
  receiving-code-review/SKILL.md
  verification-before-completion/SKILL.md
  executing-plans/SKILL.md
  using-agent-studio/SKILL.md
  using-github/SKILL.md
  managing-work-items/SKILL.md
  using-memory-and-devlogs/SKILL.md
.claude-plugin/plugin.json
.codex-plugin/plugin.json
.cursor-plugin/plugin.json
gemini-extension.json
hooks/hooks.json
hooks/run-hook.sh
synlynk/instruction_sync.py          # new: generates the 4 thin pointer files from using-synlynk/SKILL.md
tests/test_instruction_sync.py       # new
CLAUDE.md                            # modified: shared-protocol section replaced by generated pointer
AGENTS.md                            # modified: same
GEMINI.md                            # modified: same
.cursorrules                         # created or modified: same (create if absent)
```

Each forked ceremony file has one responsibility (one ceremony); the 4 new skills are clustered by recurring task shape, not by subsystem, per the spec. `instruction_sync.py` is a single-purpose generator, kept separate from `db.py`'s existing `init()` file-writing so this plan doesn't touch `synlynk init`'s behavior.

---

### Task 1: Scaffold the skill tree directory and credit superpowers

**Files:**
- Create: `skills/synlynk/README.md`

- [ ] **Step 1: Create the directory and README**

```bash
mkdir -p skills/synlynk
cat > skills/synlynk/README.md << 'EOF'
# synlynk Skill Pack

Ceremony skills in this tree (`brainstorming`, `writing-plans`, `writing-skills`,
`test-driven-development`, `systematic-debugging`, `using-git-worktrees`,
`subagent-driven-development`, `dispatching-parallel-agents`,
`finishing-a-development-branch`, `requesting-code-review`, `receiving-code-review`,
`verification-before-completion`, `executing-plans`) are forked from the
[superpowers](https://github.com/obra/superpowers) plugin by Jesse Vincent (MIT
licensed), with synlynk's own SOPs woven into the relevant step of each. The remaining
skills (`using-synlynk`, `using-agent-studio`, `using-github`, `managing-work-items`,
`using-memory-and-devlogs`) are synlynk-original.

See `docs/superpowers/specs/2026-11-18-synlynk-native-skill-design.md` for the design
rationale and `docs/superpowers/plans/2026-11-18-synlynk-native-skill.md` for how this
tree was built.
EOF
```

Expected: `skills/synlynk/README.md` exists with the content above.

- [ ] **Step 2: Commit**

```bash
git add skills/synlynk/README.md
git commit -m "chore: scaffold skills/synlynk tree, credit superpowers origin"
```

---

### Task 2: Fork `test-driven-development`

**Files:**
- Create: `skills/synlynk/test-driven-development/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/test-driven-development/SKILL.md`

- [ ] **Step 1: Read the source file in full**

```bash
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/test-driven-development/SKILL.md
```

- [ ] **Step 2: Copy it verbatim to the destination, with no synlynk-specific insertion**

This skill is pure generic craft (red-green-refactor mechanics) with no synlynk SOP touching it. Copy unchanged except the YAML frontmatter `name:` field (change to the same slug, this is cosmetic) and append one line at the very end of the file:

```markdown

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
```

```bash
mkdir -p skills/synlynk/test-driven-development
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/test-driven-development/SKILL.md skills/synlynk/test-driven-development/SKILL.md
cat >> skills/synlynk/test-driven-development/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 3: Verify no stray superpowers-specific tool-path references**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/test-driven-development/SKILL.md
```

Expected: no output (this skill has no such references; if any appear, resolve each by replacing with the synlynk-tree-relative equivalent before proceeding).

- [ ] **Step 4: Commit**

```bash
git add skills/synlynk/test-driven-development/SKILL.md
git commit -m "feat: fork test-driven-development skill into synlynk tree"
```

---

### Task 3: Fork `systematic-debugging`

**Files:**
- Create: `skills/synlynk/systematic-debugging/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/systematic-debugging/SKILL.md`

- [ ] **Step 1: Copy verbatim (no synlynk SOP touches generic debugging method), append the same attribution footer as Task 2**

```bash
mkdir -p skills/synlynk/systematic-debugging
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/systematic-debugging/SKILL.md skills/synlynk/systematic-debugging/SKILL.md
cat >> skills/synlynk/systematic-debugging/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/systematic-debugging/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/systematic-debugging/SKILL.md
git commit -m "feat: fork systematic-debugging skill into synlynk tree"
```

---

### Task 4: Fork `brainstorming`

**Files:**
- Create: `skills/synlynk/brainstorming/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/brainstorming/SKILL.md`

No synlynk SOP touches this skill directly (the Brainstorm-First Policy is already the gate that invokes it, not content inside it). Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/brainstorming
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/brainstorming/SKILL.md skills/synlynk/brainstorming/SKILL.md
cat >> skills/synlynk/brainstorming/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/brainstorming/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/brainstorming/SKILL.md
git commit -m "feat: fork brainstorming skill into synlynk tree"
```

---

### Task 5: Fork `writing-plans` with GOVERNS-linkage step baked in

**Files:**
- Create: `skills/synlynk/writing-plans/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/writing-plans/SKILL.md`

- [ ] **Step 1: Copy the source file**

```bash
mkdir -p skills/synlynk/writing-plans
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/writing-plans/SKILL.md skills/synlynk/writing-plans/SKILL.md
```

- [ ] **Step 2: Insert a new `## synlynk GOVERNS Linkage` section immediately after the `## Scope Check` section and before `## File Structure`**

Find this exact text in the copied file:

```markdown
## File Structure

Before defining tasks, map out which files will be created or modified
```

Replace it with:

```markdown
## synlynk GOVERNS Linkage

Once this plan is committed, generate GOVERNS-linked stories for every task immediately
and autonomously — this does not require separate user approval. The milestone/
release-proposal review (Roadmap Studio) is the approval gate, and it acts granularly
on these stories (approve/hold/revise/drop/reorder/pin) — they must already exist for
that review to have anything to act on. Approval gates *dispatch* of a story, not its
creation. Every dispatched job behind this plan must be linked to a GOVERNS goal/story;
`synlynk pr check` and dispatch preflight enforce this gate.

## File Structure

Before defining tasks, map out which files will be created or modified
```

Use the Edit tool (or equivalent) to make this exact replacement in `skills/synlynk/writing-plans/SKILL.md`.

- [ ] **Step 3: Append attribution footer**

```bash
cat >> skills/synlynk/writing-plans/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0; synlynk GOVERNS Linkage section added.*
EOF
```

- [ ] **Step 4: Verify the insertion landed and nothing else changed**

```bash
grep -n '## synlynk GOVERNS Linkage' skills/synlynk/writing-plans/SKILL.md
diff <(grep -v 'synlynk' /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/writing-plans/SKILL.md) <(grep -v 'synlynk' skills/synlynk/writing-plans/SKILL.md)
```

Expected: the first command prints one matching line; the second `diff` shows only the
expected additions (File Structure heading relocated below the new section, footer
line) — no unrelated line changes.

- [ ] **Step 5: Commit**

```bash
git add skills/synlynk/writing-plans/SKILL.md
git commit -m "feat: fork writing-plans skill, bake in GOVERNS-linkage step"
```

---

### Task 6: Fork `writing-skills`

**Files:**
- Create: `skills/synlynk/writing-skills/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/writing-skills/SKILL.md`

No synlynk SOP applies (this governs how to author *any* skill, including the ones
this very plan is creating — generic). Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/writing-skills
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/writing-skills/SKILL.md skills/synlynk/writing-skills/SKILL.md
cat >> skills/synlynk/writing-skills/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/writing-skills/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/writing-skills/SKILL.md
git commit -m "feat: fork writing-skills skill into synlynk tree"
```

---

### Task 7: Fork `using-git-worktrees` with synlynk worktree-naming convention baked in

**Files:**
- Create: `skills/synlynk/using-git-worktrees/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/using-git-worktrees/SKILL.md`

- [ ] **Step 1: Copy the source file**

```bash
mkdir -p skills/synlynk/using-git-worktrees
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/using-git-worktrees/SKILL.md skills/synlynk/using-git-worktrees/SKILL.md
```

- [ ] **Step 2: Insert synlynk's worktree-naming convention into Step 1's directory-selection flow**

Find this exact text:

```markdown
### 1a. Native Worktree Tools (preferred)
```

Insert immediately before it:

```markdown
### synlynk Worktree Naming Convention

Before creating any worktree, invoke `superpowers:using-git-worktrees` (this skill) to
create a dedicated worktree for the feature branch. Never reuse an existing worktree
checked out to a different feature's branch — commits will land on the wrong branch.
The worktree name must match the feature branch, with `/` replaced by `+`
(e.g. `feat/document-timeline` → worktree `feat+document-timeline`). If the session
environment already placed you in a worktree, verify `git branch --show-current`
matches the intended feature branch before writing any code.

### 1a. Native Worktree Tools (preferred)
```

Use the Edit tool to make this exact insertion in `skills/synlynk/using-git-worktrees/SKILL.md`.

- [ ] **Step 3: Append attribution footer**

```bash
cat >> skills/synlynk/using-git-worktrees/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0; synlynk Worktree Naming Convention section added.*
EOF
```

- [ ] **Step 4: Verify**

```bash
grep -n '### synlynk Worktree Naming Convention' skills/synlynk/using-git-worktrees/SKILL.md
```

Expected: one matching line.

- [ ] **Step 5: Commit**

```bash
git add skills/synlynk/using-git-worktrees/SKILL.md
git commit -m "feat: fork using-git-worktrees skill, bake in synlynk naming convention"
```

---

### Task 8: Fork `subagent-driven-development`

**Files:**
- Create: `skills/synlynk/subagent-driven-development/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/subagent-driven-development/SKILL.md`

No synlynk SOP applies directly (the capability-based routing lives in
`dispatching-parallel-agents`, Task 9). Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/subagent-driven-development
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/subagent-driven-development/SKILL.md skills/synlynk/subagent-driven-development/SKILL.md
cat >> skills/synlynk/subagent-driven-development/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified. For synlynk's cross-harness dispatch rules, see `using-agent-studio` and `dispatching-parallel-agents`.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/subagent-driven-development/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/subagent-driven-development/SKILL.md
git commit -m "feat: fork subagent-driven-development skill into synlynk tree"
```

---

### Task 9: Fork `dispatching-parallel-agents` with capability-based harness routing baked in

**Files:**
- Create: `skills/synlynk/dispatching-parallel-agents/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/dispatching-parallel-agents/SKILL.md`

- [ ] **Step 1: Copy the source file**

```bash
mkdir -p skills/synlynk/dispatching-parallel-agents
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/dispatching-parallel-agents/SKILL.md skills/synlynk/dispatching-parallel-agents/SKILL.md
```

- [ ] **Step 2: Insert a new `## synlynk Capability-Based Routing` section immediately after `## Overview` and before `## When to Use`**

Find this exact text:

```markdown
## When to Use
```

(the first occurrence) and insert immediately before it:

```markdown
## synlynk Capability-Based Routing

Dispatch routes work by task type, not by role identity alone — "Harness" means the
execution backend (Claude/Agy/Grok/Codex) that runs a task, not the Agent (role) doing
the work. The current interim default routing table:

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| pm / review / deploy / brainstorm | Claude | pm, review, deploy, brainstorm |
| implement / test / css / templates / content / subpages | Agy | implement, test, css, templates, content, subpages |
| implement / test / canvas / js / infra | Grok | implement, test, canvas, js, infra |
| implement / test / refactor / cli-plumbing | Codex | implement, test, refactor, cli-plumbing |

Do not start a task outside your role column without explicit approval. This table is
an interim default under empirical reassessment, not a fixed grant — a harness×task-type
comparison needs ≥5 completed+merged jobs (median `pr_review_cycles` + `total_cost_usd`
from `capability_ratings`/`cost_entries`) before it's allowed to override this default.

**GitHub write routing:** route any task requiring GitHub write actions to Codex first,
then Grok, then Claude, then Agy (`_GH_WRITE_HARNESS_PRIORITY`). Pass
`--requires-gh-write` on `synlynk dispatch` to enforce this automatically.

## When to Use
```

Use the Edit tool to make this exact insertion in `skills/synlynk/dispatching-parallel-agents/SKILL.md`.

- [ ] **Step 3: Append attribution footer**

```bash
cat >> skills/synlynk/dispatching-parallel-agents/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0; synlynk Capability-Based Routing section added.*
EOF
```

- [ ] **Step 4: Verify**

```bash
grep -n '## synlynk Capability-Based Routing' skills/synlynk/dispatching-parallel-agents/SKILL.md
```

Expected: one matching line.

- [ ] **Step 5: Commit**

```bash
git add skills/synlynk/dispatching-parallel-agents/SKILL.md
git commit -m "feat: fork dispatching-parallel-agents skill, bake in capability-based routing"
```

---

### Task 10: Fork `finishing-a-development-branch` with worktree hygiene sweep baked in

**Files:**
- Create: `skills/synlynk/finishing-a-development-branch/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/finishing-a-development-branch/SKILL.md`

- [ ] **Step 1: Copy the source file**

```bash
mkdir -p skills/synlynk/finishing-a-development-branch
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/finishing-a-development-branch/SKILL.md skills/synlynk/finishing-a-development-branch/SKILL.md
```

- [ ] **Step 2: Insert synlynk's hygiene rules right after `### Step 6: Cleanup Workspace`'s heading, before its first paragraph**

Find this exact text:

```markdown
### Step 6: Cleanup Workspace

**Only runs for Options 1 and 4.**
```

Replace with:

```markdown
### Step 6: Cleanup Workspace

**synlynk worktree hygiene:** clean up a worktree and its branch the moment the PR that
owns them lands — same turn as the merge, not deferred. This includes worktrees nested
under a parent worktree (dispatch sub-jobs): when the parent's PR merges, sweep every
nested `worktrees/job-*` inside it too. Before deleting, confirm via `git status --short`
(no uncommitted changes) and via `git merge-base --is-ancestor <branch> origin/main` OR a
matching `gh pr ... state: MERGED` (squash merges break literal ancestry — PR state is
the source of truth in that case). If a branch's content is genuinely unmerged and has
no PR, archive it to `docs/archive/<topic>/` via its own small branch/PR before removing
the worktree — do not silently discard it.

**Only runs for Options 1 and 4.**
```

Use the Edit tool to make this exact replacement in `skills/synlynk/finishing-a-development-branch/SKILL.md`.

- [ ] **Step 3: Append attribution footer**

```bash
cat >> skills/synlynk/finishing-a-development-branch/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0; synlynk worktree hygiene rules added to Step 6.*
EOF
```

- [ ] **Step 4: Verify**

```bash
grep -n 'synlynk worktree hygiene' skills/synlynk/finishing-a-development-branch/SKILL.md
```

Expected: one matching line.

- [ ] **Step 5: Commit**

```bash
git add skills/synlynk/finishing-a-development-branch/SKILL.md
git commit -m "feat: fork finishing-a-development-branch skill, bake in worktree hygiene sweep"
```

---

### Task 11: Fork `requesting-code-review` with cross-harness+model review rule baked in

**Files:**
- Create: `skills/synlynk/requesting-code-review/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/requesting-code-review/SKILL.md`

- [ ] **Step 1: Copy the source file**

```bash
mkdir -p skills/synlynk/requesting-code-review
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/requesting-code-review/SKILL.md skills/synlynk/requesting-code-review/SKILL.md
```

- [ ] **Step 2: Insert the synlynk review rule immediately after `## How to Request` and before the next heading (`## Example`)**

Find this exact text:

```markdown
## Example
```

(the first occurrence) and insert immediately before it:

```markdown
## synlynk Cross-Harness+Model Review Requirement

The reviewer must differ from the implementer in both harness *and* model — a different
role on the same harness+model does not satisfy review. `synlynk pr check` hard-fails on
a harness+model match when `cross_harness_review_required_mode` is `enforce`. Assign a
non-authoring agent; from within the PR's own worktree/branch, the reviewer runs
`synlynk pr check` so it auto-detects the PR via git/gh context. qa `APPROVE` is the
default whenever the reviewer's GitHub login differs from the PR author's login — only
fall back to a formal comment-review checklist when the login is the same (GitHub
rejects self-approval). The reviewer's own dispatched job performs the merge itself, as
the final step of the same dispatch that posted the approval — never the interactive
home session.

## Example
```

Use the Edit tool to make this exact insertion in `skills/synlynk/requesting-code-review/SKILL.md`.

- [ ] **Step 3: Append attribution footer**

```bash
cat >> skills/synlynk/requesting-code-review/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0; synlynk Cross-Harness+Model Review Requirement section added.*
EOF
```

- [ ] **Step 4: Verify**

```bash
grep -n '## synlynk Cross-Harness+Model Review Requirement' skills/synlynk/requesting-code-review/SKILL.md
```

Expected: one matching line.

- [ ] **Step 5: Commit**

```bash
git add skills/synlynk/requesting-code-review/SKILL.md
git commit -m "feat: fork requesting-code-review skill, bake in cross-harness+model review rule"
```

---

### Task 12: Fork `receiving-code-review`

**Files:**
- Create: `skills/synlynk/receiving-code-review/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/receiving-code-review/SKILL.md`

No synlynk SOP applies to how feedback is *received* (that's `requesting-code-review`'s
concern, handled in Task 11). Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/receiving-code-review
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/receiving-code-review/SKILL.md skills/synlynk/receiving-code-review/SKILL.md
cat >> skills/synlynk/receiving-code-review/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/receiving-code-review/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/receiving-code-review/SKILL.md
git commit -m "feat: fork receiving-code-review skill into synlynk tree"
```

---

### Task 13: Fork `verification-before-completion`

**Files:**
- Create: `skills/synlynk/verification-before-completion/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/verification-before-completion/SKILL.md`

No synlynk SOP applies directly. Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/verification-before-completion
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/verification-before-completion/SKILL.md skills/synlynk/verification-before-completion/SKILL.md
cat >> skills/synlynk/verification-before-completion/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/verification-before-completion/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/verification-before-completion/SKILL.md
git commit -m "feat: fork verification-before-completion skill into synlynk tree"
```

---

### Task 14: Fork `executing-plans`

**Files:**
- Create: `skills/synlynk/executing-plans/SKILL.md`
- Source: `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/executing-plans/SKILL.md`

No synlynk SOP applies directly. Copy verbatim with attribution footer.

- [ ] **Step 1: Copy and append footer**

```bash
mkdir -p skills/synlynk/executing-plans
cp /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/executing-plans/SKILL.md skills/synlynk/executing-plans/SKILL.md
cat >> skills/synlynk/executing-plans/SKILL.md << 'EOF'

---
*Forked from [superpowers](https://github.com/obra/superpowers) 5.1.0, unmodified.*
EOF
```

- [ ] **Step 2: Verify**

```bash
grep -n 'CLAUDE_PLUGIN_ROOT\|superpowers/5.1.0' skills/synlynk/executing-plans/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/executing-plans/SKILL.md
git commit -m "feat: fork executing-plans skill into synlynk tree"
```

---

### Task 15: Author `using-agent-studio` (new, synlynk-original)

**Files:**
- Create: `skills/synlynk/using-agent-studio/SKILL.md`

- [ ] **Step 1: Write the file**

```bash
mkdir -p skills/synlynk/using-agent-studio
cat > skills/synlynk/using-agent-studio/SKILL.md << 'EOF'
---
name: using-agent-studio
description: Use when dispatching work to a harness, deciding which role/harness should do a task, or checking whether a task is linked to a GOVERNS goal/story before dispatch.
---

# Using Agent Studio

## Overview

Agent Studio is synlynk's role/charter system: a Role (or Agent) is a persistent persona
identity with a charter (pm, architect, tpm, dev, designer, qa, marketing, support) that
defines *who* is accountable for work. A Harness is the swappable execution backend
(Claude, Agy, Grok, Codex, local) that runs a dispatched task — *how* work gets executed.
See `docs/glossary-agent-vs-harness.md` for full definitions.

## When to Use

Before any `synlynk dispatch`, before accepting a task outside your own role column, and
before merging any PR — to confirm GOVERNS linkage.

## Capability-Based Task Allocation

The current interim default routing table (see `dispatching-parallel-agents` for the
full table and GitHub-write routing order). This table is generated from
`.synlynk/config.json` and is under empirical reassessment — a harness×task-type
comparison needs ≥5 completed+merged jobs (median `pr_review_cycles` + `total_cost_usd`
from `capability_ratings`/`cost_entries`) before it's allowed to override the interim
default. Do not retire or hand-edit the table based on a single job's outcome.

## 100% GOVERNS Adherence (dispatch-preflight gate)

No dispatched job may proceed without a linked GOVERNS goal/story. `synlynk pr check` and
dispatch preflight enforce this gate; `require_linked_goal_mode` in `.synlynk/policy.json`
may run this gate in `observe` mode while a clean-pass streak is established, but treat
`enforce` as the target state, not `observe`, for any new dispatch you initiate. If a task
has no GOVERNS goal/story yet, create and link one before dispatching — do not dispatch
first and backfill the link later.

## Design → Plan → Build Sequence

1. Design: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
2. Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
3. Build: code implementation

Spec not committed = do not write plan. Plan not committed = do not dispatch tasks. Plan
committed → generate GOVERNS-linked stories for every task immediately and autonomously;
this does not require separate user approval. The milestone/release-proposal review
(Roadmap Studio) is the approval gate on *dispatch* of a story, not its creation.

## Red Flags

- Dispatching a task with no GOVERNS goal/story linked — stop, create/link one first.
- Starting a task outside your role column without explicit approval.
- Treating the Capability-Based Task Allocation table as a fixed grant rather than an
  interim default open to empirical override once ≥5 samples exist.
EOF
```

- [ ] **Step 2: Verify the file is valid markdown with correct frontmatter**

```bash
head -4 skills/synlynk/using-agent-studio/SKILL.md
```

Expected:
```
---
name: using-agent-studio
description: Use when dispatching work to a harness, deciding which role/harness should do a task, or checking whether a task is linked to a GOVERNS goal/story before dispatch.
---
```

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/using-agent-studio/SKILL.md
git commit -m "feat: author using-agent-studio skill"
```

---

### Task 16: Author `using-github` (new, synlynk-original)

**Files:**
- Create: `skills/synlynk/using-github/SKILL.md`

- [ ] **Step 1: Write the file**

```bash
mkdir -p skills/synlynk/using-github
cat > skills/synlynk/using-github/SKILL.md << 'EOF'
---
name: using-github
description: Use before any gh CLI call, before requesting or performing a PR review, or before merging a PR — covers the gh role-shim, non-author review, cross-harness+model review, and merge authority gates.
---

# Using GitHub (synlynk)

## Overview

synlynk routes GitHub writes through role-scoped tokens, never the operator's personal
token, and gates merges behind both review-identity and policy checks.

## gh Role-Shim Pattern

In a harness/session shell, prepend the synlynk gh shim before any `gh` call requiring
GitHub auth:

```bash
eval "$(python3 bin/synlynk.py gh --role pm --shim-env)"
export SYNLYNK_GH_ROLE=pm
```

Raw `gh` is refused unless a role `GH_TOKEN` is already injected, `SYNLYNK_GH_ROLE` is
set, or `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`. Prefer `synlynk gh --role <role> -- …` for
session GitHub writes over the raw shim when available.

## Personal GitHub Token Is Strictly Off-Limits

Only agent-identity tokens may be used at any GOVERNS stage. The
`SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH` escape hatch requires an explicit, manual,
per-invocation operator opt-in — a dispatched job cannot see or self-set it. Every
exercise of this fallback must emit an audited log event.

## PR Review Discipline

1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer runs
   `synlynk pr check` so it auto-detects the PR via git/gh context.
3. The reviewer's own dispatched (headless) job performs the merge itself, as the final
   step of the same dispatch that posted the approval — not the interactive home session.
4. For a `BEHIND` or `DIRTY` PR, allow at most 2 `gh pr update-branch` → CI-wait cycles.
   If still `BEHIND`/`DIRTY` after the second cycle, stop and escalate.
5. **Cross-harness+model review required.** The reviewer must differ from the
   implementer in both harness *and* model, not just role identity.
6. **100% GOVERNS adherence required** on every dispatched job behind the PR.

## GitHub Identity Note

qa `APPROVE` (`gh pr review --approve`) is the default whenever the reviewer's GitHub
login differs from the PR author's login. **Fallback (same-identity collision only):**
post a formal `COMMENT` review with an explicit approve checklist when the reviewer login
equals the PR author login, since GitHub rejects self-approval.

## Merge Authority

A reviewer must run `synlynk policy check-merge --role <role>` before `gh pr merge`; a
non-zero exit means do not merge. `--requires-gh-write` on `synlynk dispatch` auto-implies
the `run:shell` permission grant and fails closed if no role is resolvable.

## Red Flags

- Using a personal GitHub token for any dispatched or GOVERNS-stage write.
- Merging without `synlynk policy check-merge` passing.
- Same-harness-different-role treated as satisfying cross-harness review — it does not.
- More than 2 `update-branch` → CI-wait cycles without escalating.
EOF
```

- [ ] **Step 2: Verify frontmatter**

```bash
head -4 skills/synlynk/using-github/SKILL.md
```

Expected: valid YAML frontmatter block as written above.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/using-github/SKILL.md
git commit -m "feat: author using-github skill"
```

---

### Task 17: Author `managing-work-items` (new, synlynk-original)

**Files:**
- Create: `skills/synlynk/managing-work-items/SKILL.md`

- [ ] **Step 1: Write the file**

```bash
mkdir -p skills/synlynk/managing-work-items
cat > skills/synlynk/managing-work-items/SKILL.md << 'EOF'
---
name: managing-work-items
description: Use before editing roadmap/todo/decisions content, before linking a decision or roadmap arc to a goal, or when a PR modifies project-docs/decisions/*.md — covers state.db authority, the Roadmap Drift Gate, and autonomous story generation.
---

# Managing Work Items

## Overview

`project-docs/roadmap.md`, `todo.md`, and `costs.md` are **not git-tracked**. `state.db`
is sole authority; GitHub Milestones/Issues are the shareable projection (synced via
`synlynk gh sync-roadmap`). Render a local copy on demand with `synlynk roadmap` /
`synlynk cost log` — do not hand-edit or commit the output. Decisions and devlogs remain
git-tracked.

## Never Hand-Edit todo.md

Use `synlynk story done <id>` and `synlynk checkpoint` to update task status in
`state.db` — do NOT hand-edit `todo.md`.

## Roadmap Drift Gate

A PR that modifies `project-docs/decisions/*.md` is checked for drift between
`decisions`, `goals`, and `roadmap_arcs` — e.g. a decision linking a goal that was never
placed on the roadmap, or a roadmap arc claiming a goal with no backing approved
decision. `synlynk pr check` runs this automatically and blocks when
`require_linked_goal_mode` is `enforce`. Inspect drift ad hoc with `synlynk roadmap
check`. There is no auto-repair command — a human must determine which goal a decision
or arc *should* reference (place it on the roadmap via `synlynk roadmap add`/`update`,
or correct the arc's `goal_id`).

## Autonomous GOVERNS-Linked Story Generation

Plan committed → generate GOVERNS-linked stories for every task immediately and
autonomously, without separate user approval. The Roadmap Studio milestone/
release-proposal review is the approval gate, acting granularly (approve/hold/revise/
drop/reorder/pin) on stories that must already exist for that review to mean anything.
Approval gates *dispatch* of a story, not its creation.

## Multi-Task & Multi-Goal Series Tracking

Every multi-task series or epic must have a dedicated parent tracking GitHub issue,
leading with **Intent**, **Context**, and **Associated Tickets & PRs**. Post a
conversational status rollup as a comment on the parent issue after every task
completion or PR merge.

## Red Flags

- Hand-editing `todo.md` or `roadmap.md` instead of using `synlynk story done`/
  `synlynk checkpoint`/`synlynk roadmap add`.
- A decision referencing a goal not on the roadmap, or a roadmap arc with no backing
  decision — run `synlynk roadmap check` before committing either.
- Treating "plan committed" as requiring a separate user approval before story
  generation — it does not; approval gates dispatch, not creation.
EOF
```

- [ ] **Step 2: Verify frontmatter**

```bash
head -4 skills/synlynk/managing-work-items/SKILL.md
```

Expected: valid YAML frontmatter block as written above.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/managing-work-items/SKILL.md
git commit -m "feat: author managing-work-items skill"
```

---

### Task 18: Author `using-memory-and-devlogs` (new, synlynk-original)

**Files:**
- Create: `skills/synlynk/using-memory-and-devlogs/SKILL.md`

- [ ] **Step 1: Write the file**

```bash
mkdir -p skills/synlynk/using-memory-and-devlogs
cat > skills/synlynk/using-memory-and-devlogs/SKILL.md << 'EOF'
---
name: using-memory-and-devlogs
description: Use at session start, at ~25K-token checkpoints, when statusline context usage exceeds 75%, or whenever presenting a numbered list of fixes/options/recommendations — covers the anti-amnesia checkpoint protocol and devlog format.
---

# Using Memory and Devlogs

## Overview

`/clear` and `/compact` lose all in-session context if devlog + memory are only written
at session end. Write checkpoints **throughout** every session, not just at the end.

## Checkpoint Cadence

- **Phase 1 (statusline ≤ 75% used):** every ~25,000 tokens of new context — write a
  devlog entry + memory update. Commit: `docs: mid-session checkpoint [N] — <topic>`.
- **Phase 2 (statusline > 75% used):** every ~5,000 tokens — same, plus add a
  `⚠️ Compaction imminent:` rescue bullet listing open threads and "about to do X" states.
- **Any numbered list of fixes/options/recommendations:** write to devlog in the *same
  response* that presents them — never wait. These are the most commonly lost pieces of
  context.

## Session Start

Read the last 3 devlog entries. Surface any `⚠️ Compaction imminent:` notes to the user
before starting new work. Read `project-docs/.synlynk_config.json` for mode
(`single`/`team`); identify the current user via `git config user.name`; in team mode,
surface recent entries from teammates' devlogs.

## Devlog and Memory Conventions

Devlog entries live in `project-docs/devlogs/<username>.md`; attribute memory decisions
with `[@username]`. `project-docs/devlogs/*.md` keeps `merge=union` in `.gitattributes`
for concurrent-append safety — never force-resolve a devlog conflict by dropping one
side.

## Periodic Maintenance

At natural pause points: sync roadmap status, devlog, and memory if anything significant
happened since the last update. Before cutting a named release, confirm all project docs
are current.

## Red Flags

- Reaching a numbered recommendations list and moving on without writing it to devlog
  first.
- Letting statusline cross 75% without switching to the tighter Phase 2 checkpoint
  cadence.
- Resolving a devlog merge conflict by picking one side instead of respecting
  `merge=union`.
EOF
```

- [ ] **Step 2: Verify frontmatter**

```bash
head -4 skills/synlynk/using-memory-and-devlogs/SKILL.md
```

Expected: valid YAML frontmatter block as written above.

- [ ] **Step 3: Commit**

```bash
git add skills/synlynk/using-memory-and-devlogs/SKILL.md
git commit -m "feat: author using-memory-and-devlogs skill"
```

---

### Task 19: Author `using-synlynk` meta-skill (new, synlynk-original)

**Files:**
- Create: `skills/synlynk/using-synlynk/SKILL.md`

This is the thin meta-skill injected by the `SessionStart` hook (Task 21). It must stay
a map of *what exists and when to reach for it* — not a copy of CLAUDE.md's full content,
which now lives in the individual skills authored/forked in Tasks 2–18.

- [ ] **Step 1: Write the file**

```bash
mkdir -p skills/synlynk/using-synlynk
cat > skills/synlynk/using-synlynk/SKILL.md << 'EOF'
---
name: using-synlynk
description: Use when starting any conversation in a synlynk-managed repo — establishes how to find and use the synlynk skill tree, modeled on superpowers' using-superpowers skill.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Using synlynk

If there is even a 1% chance a skill below might apply to what you are doing, invoke it
via the Skill tool before responding — including before asking a clarifying question.

## Skill Map

| Skill | Reach for it when... |
|---|---|
| `brainstorming` | turning an idea into a design, before any spec/plan/code |
| `writing-plans` | a design is approved and needs an implementation plan |
| `writing-skills` | authoring or editing any skill, including ones in this tree |
| `test-driven-development` | writing or modifying application code |
| `systematic-debugging` | investigating a bug or unexpected behavior |
| `using-git-worktrees` | starting work that needs an isolated workspace |
| `subagent-driven-development` | executing a plan's tasks via fresh subagents |
| `executing-plans` | executing a plan's tasks in a parallel/handed-off session |
| `dispatching-parallel-agents` | dispatching work to another harness/role |
| `requesting-code-review` | a PR needs review before merge |
| `receiving-code-review` | feedback has come back on your own work |
| `verification-before-completion` | about to report a task as done |
| `finishing-a-development-branch` | implementation work on a branch is complete |
| `using-agent-studio` | deciding which role/harness should do a task, or checking GOVERNS linkage |
| `using-github` | any `gh`/`synlynk gh`/PR-review/merge action |
| `managing-work-items` | touching roadmap/todo/decisions content |
| `using-memory-and-devlogs` | session start, ~25K-token checkpoints, or presenting a numbered list |

## Instruction Priority

1. User's explicit instructions (CLAUDE.md, direct requests) — highest priority.
2. synlynk skills — override default system behavior where they conflict.
3. Default system prompt — lowest priority.

## Platform Adaptation

This tree uses Claude Code tool names. On another harness, consult that harness's own
tool-name mapping (see the per-harness manifest adapters alongside this tree) before
assuming a tool name used in these skills exists verbatim.
EOF
```

- [ ] **Step 2: Verify frontmatter**

```bash
head -4 skills/synlynk/using-synlynk/SKILL.md
```

Expected: valid YAML frontmatter block as written above.

- [ ] **Step 3: Verify the skill map lists all 17 other skills exactly once**

```bash
grep -oE '^\| `[a-z-]+`' skills/synlynk/using-synlynk/SKILL.md | sort | uniq -c | awk '$1 != 1 {print "DUPLICATE:", $0}'
grep -oE '^\| `[a-z-]+`' skills/synlynk/using-synlynk/SKILL.md | wc -l
```

Expected: no `DUPLICATE:` lines printed, and the count is `17`.

- [ ] **Step 4: Commit**

```bash
git add skills/synlynk/using-synlynk/SKILL.md
git commit -m "feat: author using-synlynk meta-skill"
```

---

### Task 20: Author per-harness manifest adapters

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.codex-plugin/plugin.json`
- Create: `.cursor-plugin/plugin.json`
- Create: `gemini-extension.json`
- Source (structural templates): `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `gemini-extension.json`

- [ ] **Step 1: Read the superpowers template files to confirm exact shape**

```bash
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/.claude-plugin/plugin.json
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/.codex-plugin/plugin.json
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/.cursor-plugin/plugin.json
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/gemini-extension.json
```

- [ ] **Step 2: Write `.claude-plugin/plugin.json`**

```bash
mkdir -p .claude-plugin
cat > .claude-plugin/plugin.json << 'EOF'
{
  "name": "synlynk",
  "description": "synlynk's own ceremony and process skills, forked from superpowers with synlynk SOPs baked in, plus synlynk-specific skills for Agent Studio, GitHub, work-item management, and memory/devlog hygiene.",
  "version": "0.1.0",
  "author": {
    "name": "synlynk"
  },
  "homepage": "https://github.com/synlynk/synlynk",
  "repository": "https://github.com/synlynk/synlynk",
  "license": "Apache-2.0",
  "keywords": ["skills", "workflow", "governance", "multi-agent", "dispatch"]
}
EOF
```

- [ ] **Step 3: Write `.codex-plugin/plugin.json` (mirror the same fields Codex's own template declares)**

```bash
mkdir -p .codex-plugin
cat > .codex-plugin/plugin.json << 'EOF'
{
  "name": "synlynk",
  "description": "synlynk's own ceremony and process skills, forked from superpowers with synlynk SOPs baked in, plus synlynk-specific skills for Agent Studio, GitHub, work-item management, and memory/devlog hygiene.",
  "version": "0.1.0"
}
EOF
```

- [ ] **Step 4: Write `.cursor-plugin/plugin.json` (mirror the same fields Cursor's own template declares)**

```bash
mkdir -p .cursor-plugin
cat > .cursor-plugin/plugin.json << 'EOF'
{
  "name": "synlynk",
  "description": "synlynk's own ceremony and process skills, forked from superpowers with synlynk SOPs baked in, plus synlynk-specific skills for Agent Studio, GitHub, work-item management, and memory/devlog hygiene.",
  "version": "0.1.0"
}
EOF
```

- [ ] **Step 5: Write `gemini-extension.json`**

```bash
cat > gemini-extension.json << 'EOF'
{
  "name": "synlynk",
  "description": "synlynk's own ceremony and process skills, forked from superpowers with synlynk SOPs baked in, plus synlynk-specific skills for Agent Studio, GitHub, work-item management, and memory/devlog hygiene.",
  "version": "0.1.0",
  "contextFileName": "GEMINI.md"
}
EOF
```

- [ ] **Step 6: Verify all four are valid JSON**

```bash
python3 -c "import json; [json.load(open(f)) for f in ['.claude-plugin/plugin.json', '.codex-plugin/plugin.json', '.cursor-plugin/plugin.json', 'gemini-extension.json']]; print('all valid')"
```

Expected: `all valid`.

- [ ] **Step 7: Commit**

```bash
git add .claude-plugin/plugin.json .codex-plugin/plugin.json .cursor-plugin/plugin.json gemini-extension.json
git commit -m "feat: add per-harness manifest adapters for synlynk skill tree"
```

---

### Task 21: Author the `SessionStart` hook

**Files:**
- Create: `hooks/hooks.json`
- Create: `hooks/run-hook.sh`
- Source (structural template): `/Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/hooks/hooks.json`

- [ ] **Step 1: Read the superpowers template for exact shape**

```bash
cat /Users/nikhilsoman/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/hooks/hooks.json
```

- [ ] **Step 2: Write `hooks/hooks.json`, same structure, pointed at synlynk's own hook script**

```bash
mkdir -p hooks
cat > hooks/hooks.json << 'EOF'
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.sh\" session-start",
            "async": false
          }
        ]
      }
    ]
  }
}
EOF
```

- [ ] **Step 3: Write `hooks/run-hook.sh`**

```bash
cat > hooks/run-hook.sh << 'EOF'
#!/bin/sh
set -e
case "$1" in
  session-start)
    echo "synlynk skill tree active. Read skills/synlynk/using-synlynk/SKILL.md before responding."
    ;;
  *)
    echo "unknown hook action: $1" >&2
    exit 1
    ;;
esac
EOF
chmod +x hooks/run-hook.sh
```

- [ ] **Step 4: Verify the hook JSON is valid and the script is executable**

```bash
python3 -c "import json; json.load(open('hooks/hooks.json')); print('valid json')"
test -x hooks/run-hook.sh && echo "executable"
sh hooks/run-hook.sh session-start
```

Expected: `valid json`, `executable`, then the session-start message printed with exit
code 0.

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json hooks/run-hook.sh
git commit -m "feat: add SessionStart hook injecting using-synlynk meta-skill"
```

---

### Task 22: Write the instruction-file generation script

**Files:**
- Create: `synlynk/instruction_sync.py`
- Test: `tests/test_instruction_sync.py`

This closes issue #5367 structurally: `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.cursorrules`
stop being hand-duplicated and become generated pointers into
`skills/synlynk/using-synlynk/SKILL.md`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_instruction_sync.py
import json
from pathlib import Path

from synlynk.instruction_sync import render_pointer, POINTER_TARGETS


def test_render_pointer_contains_skill_path_and_marker():
    result = render_pointer(harness_label="Claude")
    assert "skills/synlynk/using-synlynk/SKILL.md" in result
    assert "<!-- synlynk:instruction-pointer:start -->" in result
    assert "<!-- synlynk:instruction-pointer:end -->" in result
    assert "Claude" in result


def test_pointer_targets_cover_all_four_files():
    assert set(POINTER_TARGETS) == {"CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules"}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_instruction_sync.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.instruction_sync'`.

- [ ] **Step 3: Write the implementation**

```python
# synlynk/instruction_sync.py
"""Generates thin pointer blocks for CLAUDE.md/AGENTS.md/GEMINI.md/.cursorrules
from the synlynk skill tree, replacing hand-duplicated shared-protocol content.
See docs/superpowers/specs/2026-11-18-synlynk-native-skill-design.md.
"""
from pathlib import Path

START_MARKER = "<!-- synlynk:instruction-pointer:start -->"
END_MARKER = "<!-- synlynk:instruction-pointer:end -->"

POINTER_TARGETS = {
    "CLAUDE.md": "Claude",
    "AGENTS.md": "Codex",
    "GEMINI.md": "Gemini",
    ".cursorrules": "Cursor",
}


def render_pointer(harness_label: str) -> str:
    return (
        f"{START_MARKER}\n"
        f"# synlynk Shared Protocol ({harness_label})\n\n"
        "This section is generated. Do not hand-edit it — edit "
        "`skills/synlynk/using-synlynk/SKILL.md` and the relevant skill under "
        "`skills/synlynk/`, then re-run `python3 -m synlynk.instruction_sync`.\n\n"
        "Read `skills/synlynk/using-synlynk/SKILL.md` for the full skill map and "
        "invoke the relevant skill under `skills/synlynk/` for any task it covers.\n"
        f"{END_MARKER}\n"
    )


def sync_file(path: Path, harness_label: str) -> None:
    """Replace the marked block in `path` with a freshly rendered pointer.

    If the file exists and contains both markers, only the content between them
    is replaced. If the file doesn't exist, it is created containing only the
    pointer block. If the file exists but has no markers, the pointer block is
    appended.
    """
    pointer = render_pointer(harness_label)
    if not path.exists():
        path.write_text(pointer)
        return

    text = path.read_text()
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1:
        separator = "\n\n" if text and not text.endswith("\n\n") else ""
        path.write_text(text + separator + pointer)
        return

    end += len(END_MARKER)
    path.write_text(text[:start] + pointer.rstrip("\n") + text[end:])


def sync_all(repo_root: Path) -> None:
    for filename, harness_label in POINTER_TARGETS.items():
        sync_file(repo_root / filename, harness_label)


if __name__ == "__main__":
    sync_all(Path(__file__).resolve().parent.parent)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/test_instruction_sync.py -v
```

Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add synlynk/instruction_sync.py tests/test_instruction_sync.py
git commit -m "feat: add instruction_sync generator for CLAUDE.md/AGENTS.md/GEMINI.md/.cursorrules pointers"
```

---

### Task 23: Migrate the 4 instruction files

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `GEMINI.md`
- Create or modify: `.cursorrules`

- [ ] **Step 1: Capture current state of all four files for the round-trip check**

```bash
mkdir -p /tmp/synlynk-instr-before
cp CLAUDE.md AGENTS.md GEMINI.md /tmp/synlynk-instr-before/ 2>/dev/null
test -f .cursorrules && cp .cursorrules /tmp/synlynk-instr-before/ || echo "no .cursorrules yet"
```

- [ ] **Step 2: Run the generator**

```bash
python3 -m synlynk.instruction_sync
```

- [ ] **Step 3: Verify each file now contains exactly one pointer block, and nothing outside the markers was touched**

```bash
for f in CLAUDE.md AGENTS.md GEMINI.md .cursorrules; do
  echo "=== $f ==="
  grep -c '<!-- synlynk:instruction-pointer:start -->' "$f"
  grep -c '<!-- synlynk:instruction-pointer:end -->' "$f"
done
```

Expected: each file prints `1` twice (start marker once, end marker once).

```bash
diff <(grep -v -A100000 '<!-- synlynk:instruction-pointer:start -->' /tmp/synlynk-instr-before/CLAUDE.md | grep -v -B100000 '<!-- synlynk:instruction-pointer:end -->') /dev/null || true
```

(This diff is advisory — the point of this step is manual spot-check, since the "Harness
Instructions (synlynk-managed — do not edit)" block in the pre-migration `CLAUDE.md` is
exactly what the pointer block now replaces. Confirm by eye that content *above* where
that block started — the project-specific sections like "Identity & Attribution",
"Operating Mode", "What This Project Is", etc. — is unchanged in the new `CLAUDE.md`.)

```bash
diff /tmp/synlynk-instr-before/CLAUDE.md CLAUDE.md | head -60
```

Expected: the diff shows only the previously-hand-duplicated shared-protocol / Harness
Instructions section replaced by the generated pointer block — no unrelated sections
changed.

- [ ] **Step 4: Confirm the generator is idempotent (running it twice produces no further diff)**

```bash
python3 -m synlynk.instruction_sync
git diff --stat CLAUDE.md AGENTS.md GEMINI.md .cursorrules
```

Expected: no output from `git diff --stat` (second run is a no-op).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md AGENTS.md GEMINI.md .cursorrules
git commit -m "fix: collapse CLAUDE.md/AGENTS.md/GEMINI.md/.cursorrules duplication via instruction_sync (closes #5367)"
```

---

### Task 24: Final verification pass

**Files:** none (verification only)

- [ ] **Step 1: Confirm all 18 skill files exist with valid frontmatter**

```bash
for f in using-synlynk brainstorming writing-plans writing-skills test-driven-development systematic-debugging using-git-worktrees subagent-driven-development dispatching-parallel-agents finishing-a-development-branch requesting-code-review receiving-code-review verification-before-completion executing-plans using-agent-studio using-github managing-work-items using-memory-and-devlogs; do
  test -f "skills/synlynk/$f/SKILL.md" && head -1 "skills/synlynk/$f/SKILL.md" | grep -q '^---$' && echo "OK: $f" || echo "MISSING OR MALFORMED: $f"
done
```

Expected: `OK: <name>` for all 18, no `MISSING OR MALFORMED` lines.

- [ ] **Step 2: Confirm no file in the new tree still references the superpowers plugin's own runtime path**

```bash
grep -rn 'CLAUDE_PLUGIN_ROOT' skills/synlynk/ || echo "none found"
```

Expected: `none found` — `hooks/hooks.json` (Task 21) is the only place this variable
belongs, and it refers to synlynk's own plugin root, not superpowers'.

- [ ] **Step 3: Run the full existing test suite to confirm nothing broke**

```bash
pytest tests/test_instruction_sync.py -q
```

Expected: all passing (2 tests from Task 22). Do not run the full project suite here —
this plan touches no application code paths outside `synlynk/instruction_sync.py`, so a
targeted run is sufficient; the full suite's pre-existing 5 unrelated failures (noted in
PR #5369's checklist) are out of scope for this plan.

- [ ] **Step 4: Commit any final cleanup if needed, otherwise proceed to finishing-a-development-branch**

No code change expected at this step — this is a checkpoint, not a commit, unless Step 1
or Step 2 above surfaced something to fix.

---

## Self-Review Notes (completed during plan authoring)

**Spec coverage:** every Stage 0 bullet in the spec maps to a task — skill tree (Tasks
1–19), manifest adapters (Task 20), SessionStart hook (Task 21), generation mechanism +
migration (Tasks 22–23), no-new-infrastructure constraint (verified throughout — every
skill's CLI references are plain Bash shell-outs, no MCP/daemon content introduced).

**Placeholder scan:** no "TBD"/"TODO"/"add appropriate X" patterns — every insertion
step quotes exact anchor text and exact replacement content; every new skill has full
real content, not a stub.

**Type/name consistency:** the 4 new skill directory names (`using-agent-studio`,
`using-github`, `managing-work-items`, `using-memory-and-devlogs`) match exactly between
the spec, the File Structure section above, Tasks 15–18's filenames, and the skill map
table in Task 19's `using-synlynk/SKILL.md` content — checked by the count-based
verification in Task 19 Step 3.
