# BS-17 FTUE Onboarding Design
*`synlynk init --wizard` + `synlynk scan`*

**Status:** Design approved  
**Milestone:** v0.10.0  
**Replaces:** `story-v010-firstrun` (first-run polish) — expanded scope supersedes it

---

## 1. Goal

First-time users hit `synlynk init` and leave with a configured workspace, a populated `state.db`, working agent dispatch, and a concrete next command — in under two minutes. Returning users can re-run `synlynk scan` at any time to refresh context, add repos, or adapt to a changed environment.

The core constraint: **scan runs first, mandatory, no skip option.** Every subsequent screen uses scan-discovered facts to personalise its choices and explain its "why." synlynk is a new concept for most users; the wizard must guide, educate, and evangelise — not just configure.

---

## 2. Two Stories

### Story A — `synlynk init --wizard`
FTUE wizard invoked on first `synlynk init` in a new environment (or explicitly with `--wizard`). A full 8-screen typeform-style TUI that walks the user through:
- Repo topology detection and workspace creation
- Home harness selection (which AI CLI is "primary")
- Agent fleet discovery and role assignment
- Skills/plugins scan and coexistence messaging
- Launch cheat sheet

### Story B — `synlynk scan`
Re-runnable standalone command that:
- Detects/re-detects repo topology
- Fingerprints stack per repo/package
- Parses README, CLAUDE.md, GEMINI.md, AGENTS.md
- Maps to workspace in `state.db`
- Rebuilds/refreshes `context.md`
- Runs silently in ~2s; prints a summary on finish

`synlynk scan` is called internally by the wizard (Phase 0) and can be run independently at any time with `--refresh` or `--add <path>`.

---

## 3. Wizard Screen Sequence

```
Landing ──► [Phase 0: silent scan] ──► Screen 1  ──► Screen 2
                                        (harness)    (topology/workspace)
                                                          │
                                              single/mono ├──► Screen 3
                                              multi-repo  └──► Screen 2ab ──► Screen 2c ──► Screen 3
                                                          
Screen 3 ──► Screen 4 ──► Screen 5 ──► Screen 6
(skills)    (agents)    (roles)     (launch cheat sheet)
```

Progress indicator: `step N/6` with dot trail. Teal dots = multi-repo sub-flow; purple dots = main flow. Dot trail: filled past, active current (wider pill), hollow future.

---

## 4. Screen Designs

### Landing
**Purpose:** Brand intro + explain what synlynk is and why synaptic links matter.

Contents:
- Hero: full S-glyph SVG + wordmark (`syn` white, `l` #5B8DEF, `y` #A259F7, `n` #2EC4A0, `k` white; Courier New font)
- Tagline: `synaptic link for AI development`
- **Synaptic link explainer block** (left-border-purple): *"In the brain, a synaptic link is the tiny gap where one neuron passes its signal to the next. Alone, neurons are just cells. Connected, they produce thought. Your AI tools are the same — powerful in isolation, transformative when they share a signal. synlynk is the gap that makes them think together."*
- Product description: *"You already have great AI tools. The problem is they don't know about each other — or your project. synlynk fixes that: it injects shared context before every dispatch, routes tasks to the right agent, and keeps score on what's working. Your fleet, finally coordinated."*
- 3 value props: "One brain" / "4× efficiency" / "Always watching"
- Prompt: `press enter to start setup — takes about 2 minutes`

No "skip" option. Enter is the only action.

---

### Phase 0 — Silent Scan (not a numbered step)
Runs immediately after Enter on landing. No user interaction. Prints one animated line:

```
› scanning your environment...
  repos found: 3  ·  harnesses: claude, gemini  ·  stacks: Python, TypeScript, React
```

Then transitions to Screen 1. Total target: ≤ 2 seconds.

Scan discovers:
- Git roots in `~/dev/`, `~/projects/`, and `cwd`
- Installed harnesses (claude, gemini, codex, grok) via PATH lookup
- Agent CLIs available
- Skills/plugins paths (`~/.claude/plugins/`, `~/.config/gstack/`, etc.)
- Repo topology per root: single / monorepo (packages/, apps/, services/) / multi-repo (multiple roots)
- Stack fingerprint per root (see §7)
- README, CLAUDE.md, GEMINI.md, AGENTS.md content per root

Scan results stored in memory; written to `state.db` after wizard completes.

---

### Screen 1 — Home Harness
**Title:** *Choose your home harness*  
**Why it matters:** *"Your home harness is the AI CLI synlynk treats as the primary — its terminal is how synlynk orchestrates jobs, reads costs, and runs doctor checks. You can dispatch to any agent regardless of this choice; this is about where synlynk lives."*

Scan discovery block:
```
  scan found these harnesses installed:
  ● claude code  v1.x  ·  /usr/local/bin/claude
  ● gemini cli   v2.x  ·  /usr/local/bin/gemini
```

Choices (numbered): one per discovered harness. If only one found, it is pre-selected and user just confirms.

Stores: `config.home_harness = <name>`

---

### Screen 2 — Repo Topology + Workspace
**Title:** *How are your repos arranged?*  
**Why it matters:** *"synlynk organises your work into workspaces — named containers that share a context database, agent fleet, and budget. One workspace can span a single repo, a monorepo, or a whole portfolio of repos. Getting this right means your agents always have the right picture."*

Scan discovery block:
```
  scan found 3 git repos nearby:
  ● ~/dev/synlynk  (Python · CLI)
  ● ~/dev/rxcc     (TypeScript · Next.js)
  ● ~/dev/playblazer-ng  (TypeScript · React)
```

Choices:
1. **Single repo** — just this repo, workspace keyed to `cwd`
2. **Monorepo** — one git root with packages/ or apps/ sub-packages *(shown only if scan found packages/)*
3. **Multi-repo** — multiple separate repos sharing a workspace *(leads to sub-flow 2ab → 2c)*

---

### Screen 2ab — Name + Pick Repos (multi-repo sub-flow)
**Title:** *Name your workspace and pick your repos*  
**Why it matters:** *"All selected repos share one state.db, agent fleet, and budget. synlynk found these git roots nearby — include everything your agents need to see together."*

Two-section layout on one screen:

**Top — Workspace name:**
- Text input field
- Suggestion chips: auto-inferred from parent dir + repo names (e.g. `dev-workspace`, `nikhil-dev`)
- Live path preview: `~/.synlynk/workspaces/<name>/state.db`

**Bottom — Repo picker:**
- Checkbox list of discovered git roots
- Per-repo: name + path + stack fingerprint line
- Dotfiles repo pre-unchecked (heuristic: path = `~/dotfiles`, `~/.config`)
- `+ add repo from another path…` opens inline path input

Keymap: `tab` to move between name/repos, `space` to toggle, `enter` to continue.

---

### Screen 2c — Confirm Workspace (multi-repo sub-flow)
**Title:** *Here's your workspace*  
**Why it matters:** *"One shared brain for N repos. Context, jobs, costs and agents roll up together."*

Shows:
- Workspace tree (ASCII): `dev-workspace/ ├─ state.db ├─ config.json └─ repos ✓ <each repo>`
- 4 key facts grid: repos included · add more later (`synlynk scan --add`) · state path · remove later (`synlynk scan --remove`)

Choices: `↵ Create workspace` / `e Edit`  
`e` returns to 2ab without losing entries.

---

### Screen 3 — Skills & Plugins
**Title:** *synlynk and your skill packs work together*  
**Why it matters:** *"synlynk injects project context before skills run, never overrides them. If you use Superpowers or GStack, your skill routes stay intact — synlynk adds the layer below: shared project state, dispatch coordination, cost tracking."*

Scan discovery block:
```
  scan found:
  ● superpowers  v5.1.0  ·  ~/.claude/plugins/cache/superpowers-marketplace/
  ● gstack       v2.x    ·  ~/.config/gstack/
```

This is an **education/evangelism screen** — no required choice. User just reads and presses enter to continue. If no skill packs found, shows: *"No skill packs found. You can install them later — synlynk works fine without them."*

---

### Screen 4 — Agent Fleet
**Title:** *Your agent fleet*  
**Why it matters:** *"Each agent has different strengths. synlynk's dispatch command routes tasks to the right agent and tracks what they cost you. Here's what's installed."*

Shows a card per discovered agent CLI: name + version + PATH + one-line capability summary.

```
  [robot-svg]  claude code   v1.x   reasoning, PM, code review
  [robot-svg]  gemini cli    v2.x   implementation, large context
  [robot-svg]  codex         v0.x   CLI plumbing, refactoring
```

No input required. Enter to continue.

---

### Screen 5 — Agent Roles
**Title:** *Who does what?*  
**Why it matters:** *"Consistent role assignment stops agents from stomping on each other's work. synlynk writes a brief role block into each agent's directive file (CLAUDE.md, GEMINI.md, AGENTS.md) so every agent knows its lane from the first token."*

Pre-filled role table from scan (reads existing CLAUDE.md ##Your Role if present):

```
  claude       →  PM · code review · deployments
  gemini       →  implementation · testing · templates
  codex        →  CLI plumbing · refactoring
```

Options: `↵ use these roles` / `e edit` (opens role editor, one line per agent).  
Stores roles in `config.agent_roles`; wizard writes directive file blocks after Screen 6.

---

### Screen 6 — Launch Cheat Sheet
**Title:** *You're set up.*

Shows:
- S-glyph + wordmark at small size
- 6 essential commands with one-line descriptions:
  ```
  synlynk dispatch claude   "ask claude something"
  synlynk dispatch gemini   "ask gemini something"
  synlynk scan --refresh    re-scan all repos
  synlynk status            platform health + agent availability
  synlynk jobs              list running/recent jobs
  synlynk help              full command reference
  ```
- A workspace summary line: `workspace: dev-workspace · 3 repos · claude home harness`

Prompt: `↵ done · open docs at synlynk.dev/docs`

After Enter: writes all config to `state.db`, generates `context.md`, writes agent directive role blocks.

---

## 5. Workspace Model

### Data location
```
~/.synlynk/workspaces/<name>/
  state.db        # SQLite — stories, arcs, memory, costs, agents, scan results
  config.json     # budget limits, home harness, agent roles, repo paths
```

### state.db key change
Current: 8-char MD5 of `git rev-parse --show-toplevel`  
New: workspace name (human-readable string, unique per user machine)

Migration: `synlynk migrate` (v0.10.0 P0 story, already in todo.md) handles the key transition for existing installs.

### Workspace topologies

| Topology | Detection | state.db |
|----------|-----------|---------|
| Single repo | one git root, no packages/ | `~/.synlynk/workspaces/<repo-name>/` |
| Monorepo | one git root + packages/ or apps/ or services/ sub-dirs | `~/.synlynk/workspaces/<repo-name>/` |
| Multi-repo | multiple git roots selected by user | `~/.synlynk/workspaces/<chosen-name>/` |

For multi-repo, `config.json` stores a `repos` array of absolute paths. `synlynk scan` iterates all of them when regenerating `context.md`.

---

## 6. `synlynk scan` Command

### Invocation modes

```bash
synlynk scan                   # first-time: detect topology, create workspace, write state.db
synlynk scan --refresh         # re-run all detection on existing workspace
synlynk scan --add ~/dev/newrepo   # add a repo to existing multi-repo workspace
synlynk scan --remove ~/dev/oldrepo  # remove repo (non-destructive, leaves state.db)
synlynk scan --dry-run         # print what would change without writing
```

### What it does

1. **Topology detection**: walk `~/dev/`, `~/projects/`, `cwd` for git roots (max depth 2); detect monorepo markers (packages/, apps/, services/); build candidate list
2. **Stack fingerprinting** per repo/package (see §7)
3. **Context file parsing**: read README.md, CLAUDE.md, GEMINI.md, AGENTS.md — extract `## Context`, `## Architecture`, `## Your Role` sections
4. **Harness probe**: `which claude gemini codex grok aider` — version via `<cmd> --version`; check process parent for "live in" harness detection
5. **Skills scan**: glob `~/.claude/plugins/cache/*/`, `~/.config/gstack/`, known plugin paths; read name+version from manifest
6. **Write context.md**: structured summary of workspace, repos, stacks, roles, active agents — same format `exec_command` prepends today

### Output (non-wizard)
```
› synlynk scan
  scanning...
  ✓ workspace: dev-workspace
  ✓ repos: synlynk (Python·CLI), rxcc (TS·Next.js), playblazer-ng (TS·React)
  ✓ harnesses: claude v1.x, gemini v2.x
  ✓ skills: superpowers v5.1.0
  ✓ context.md updated (1,842 chars)
  
  next: synlynk dispatch claude "what's the current task?"
```

---

## 7. Stack Fingerprinting

Per repo or package dir, detect stack from file presence (no content read):

| File(s) found | Stack label |
|---------------|-------------|
| `pyproject.toml` / `setup.py` | Python |
| `package.json` + `tsconfig.json` | TypeScript |
| `package.json` (no tsconfig) | JavaScript |
| `next.config.*` | Next.js |
| `Pulumi.yaml` | Pulumi / IaC |
| `*.go` files | Go |
| `Cargo.toml` | Rust |
| `go.mod` | Go (module) |
| `Dockerfile` | Docker |
| `*.sql` / `migrations/` | SQL |
| `.github/workflows/` | CI/CD |

Multiple labels per repo allowed (e.g. `TypeScript · Next.js · Docker`). Shown on Screen 2ab repo picker and in `context.md`.

---

## 8. Home Harness Detection

Heuristic order (first match wins):
1. `SYNLYNK_HOME_HARNESS` env var
2. Inspect process parent chain: if invoked from inside a `claude` session, `claude` is home harness
3. `which claude` → if found, default to `claude`
4. First entry in `discovered_harnesses` list
5. Fallback: user selects on Screen 1

Detection runs during Phase 0 scan. Screen 1 pre-selects the result but always lets user override.

---

## 9. TUI Implementation

### Approach
Pure Python stdlib — no `rich`, `questionary`, `curses`, or third-party deps. This is a hard constraint (synlynk has zero deps beyond stdlib).

### Screen rendering
Each screen is a function that:
1. `os.system('clear')` to clear terminal
2. Print header (progress indicator, step label)
3. Print body (title, why block, scan discovery, choices)
4. Read a single keystroke via `termios`/`tty` on Unix (no Enter required for single-key choices)
5. Return user selection

### Single-keystroke input
```python
import sys, tty, termios

def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
```

For text fields (workspace name, role editor): fall back to `input()` — readline gives standard editing behaviour.

### Progress indicator
```python
def progress_bar(current, total, sub_active=False):
    dots = []
    for i in range(total):
        if i < current - 1:
            dots.append('\033[35m●\033[0m')   # done: purple
        elif i == current - 1:
            color = '\033[36m' if sub_active else '\033[35m'
            dots.append(f'{color}━━\033[0m')   # active: wider pill
        else:
            dots.append('\033[90m·\033[0m')    # future: dim
    return '  '.join(dots)
```

### Cursor animation
Not available in plain print. The `cursor` blinking effect shown in the visual is cosmetic/mockup only. In the TUI: use a static `›` arrow before the prompt line. Optionally blink via a `time.sleep(0.5)` loop if we add a loading indicator to Phase 0 scan.

---

## 10. Visual Design Spec

Defined by the visual companion files in `docs/brainstorm/bs17-ftue-onboarding/`. Key constants:

| Element | Value |
|---------|-------|
| Background | `#080b12` |
| Card bg | `#0d1117` |
| Border | `#1e293b` |
| Purple accent | `#A259F7` |
| Blue accent | `#5B8DEF` |
| Teal accent | `#2EC4A0` (multi-repo sub-flow) |
| Body text | `#e2e8f0` |
| Muted text | `#64748b` |
| Code / mono font | JetBrains Mono |
| UI font | Inter |
| Wordmark font | Courier New |

**S-glyph SVG** (canonical, must not be modified):
```svg
<svg width="28" height="28" viewBox="0 0 28 28" fill="none">
  <path d="M 9 6 C 9 6 3 6 3 11 C 3 16 12 16 12 21" fill="none" stroke="#A259F7" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M 12 21 C 12 21 18 21 18 16 C 18 11 9 11 9 6" fill="none" stroke="#5B8DEF" stroke-width="3.5" stroke-linecap="round"/>
  <line x1="12" y1="21" x2="12" y2="26" stroke="#2EC4A0" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="9" cy="6" r="2.5" fill="#5B8DEF"/>
  <circle cx="12" cy="26" r="2.5" fill="#2EC4A0"/>
</svg>
```

**Wordmark** (Courier New, rendered as styled text spans):  
`syn` → `#e2e8f0` · `l` → `#5B8DEF` · `y` → `#A259F7` · `n` → `#2EC4A0` · `k` → `#e2e8f0`

**Agent icon** — custom robot SVG (not Apple emoji), specified in visual companion `wizard-v3.html`.

In the terminal TUI: brand elements are rendered as ASCII/Unicode. The S-glyph becomes `>·<` in monochrome terminals. The wizard does not depend on colour terminal support — all choices are keyboard-navigated regardless.

---

## 11. `synlynk init --wizard` Entry Point

`synlynk init` without `--wizard`: existing behaviour (creates project-docs/ structure).  
`synlynk init --wizard`: runs the FTUE wizard.  
`synlynk init` in a workspace-less directory for the first time: prompt `"First time? Run synlynk init --wizard for guided setup."` then proceed with current init logic.

Wizard writes config ONLY on Screen 6 Enter (commit-on-complete pattern). If user Ctrl-C at any point before Screen 6: no state written, terminal restored cleanly.

---

## 12. context.md Format Post-Scan

After scan, `context.md` is replaced with a structured header:

```markdown
# synlynk context — <workspace-name>
generated: <ISO timestamp>

## workspace
name: <workspace-name>
home harness: <harness>
repos: <count>

## repos
### <repo-name>
path: <abs-path>
stack: <labels>
readme excerpt: <first 200 chars of README>
<key sections from CLAUDE.md / AGENTS.md if present>

## agent fleet
<name>: <version> — <role one-liner>

## skills
<name>: <version> — <path>

## active stories (top 5)
<from state.db stories WHERE status = 'in-progress' ORDER BY updated_at DESC LIMIT 5>
```

This replaces the current `generate_context()` flat concatenation. The structured format gives agents faster lookup for the most relevant facts.

---

## 13. Scope Boundary (v0.10.0 vs post)

### v0.10.0 (this spec)
- `synlynk scan` standalone command (all modes)
- `synlynk init --wizard` FTUE (all 8 screens + multi-repo sub-flow)
- Workspace model + `state.db` key migration (via `synlynk migrate`)
- Stack fingerprinting
- Home harness detection
- Agent discovery + role writing
- Skills scan
- New `context.md` structured format

### Post-v0.10.0
- Remote workspace sync (team mode — multiple machines, one `state.db`)
- Workspace web UI (synlynk.dev dashboard)
- Cross-workspace agent routing
- Workspace templates (e.g. "solo · multi-agent · enterprise")

---

## 14. Test Plan

| Test | Method |
|------|--------|
| Scan finds git roots in `~/dev/` fixture | Unit — mock `os.walk` with temp dir tree |
| Stack fingerprinting returns correct labels | Unit — temp dir with known file sets |
| Harness detection from PATH mock | Unit — mock `shutil.which` return values |
| Workspace creation writes correct `config.json` | Unit — temp dir |
| `synlynk scan --add` appends repo without losing existing | Integration — real temp git repos |
| `synlynk scan --dry-run` prints diff, no writes | Integration |
| Wizard Ctrl-C at screen 3 leaves no state | Integration — subprocess + signal |
| Wizard completes end-to-end, all screens, single-repo path | Integration — automate keystrokes via subprocess stdin |
| Wizard completes multi-repo path (2ab → 2c) | Integration |
| context.md structured format passes schema check | Unit — parse output, assert sections present |
| `synlynk init --wizard` in existing-workspace dir: shows "already set up" message | Integration |

---

## 15. Open Questions (deferred)

1. **Windows support** — `termios`/`tty` are Unix-only. Windows path for `read_key()` needs `msvcrt.getch()` shim. Defer to post-v0.10.0 unless Codex picks it up cheaply.
2. **XDG compliance** — `~/.synlynk/` vs `~/.config/synlynk/` vs `$XDG_DATA_HOME`. Lock in v0.10.0 to avoid painful migration later.
3. **Workspace discovery** — if user runs `synlynk scan` from a repo already in an existing workspace, should it merge or create a new one? Proposed: detect existing workspace membership, offer merge.
