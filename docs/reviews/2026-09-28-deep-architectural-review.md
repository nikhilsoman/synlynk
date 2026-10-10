# synlynk — Deep Architectural Review

**Date:** 2026-09-28 · **Commit:** `c35a42e2` · **Version:** 0.23.0-dev
**Scope:** 151 modules / 75,873 LOC package · 3,390 tests / 63,798 LOC · 774 docs / 9.3 MB

> *Note on framing:* the brief asked for three POVs but enumerated two (Principal Architect
> for Developer Engagement; GM of Product). I've delivered both in full and treated
> "find opportunities to improve performance" as the third lens — an engineering
> performance audit with measured numbers, in Part 3.

---

## Part 0 — What I actually measured

Everything below is instrumented, not inferred. Key raw numbers:

| Probe | Result |
|---|---|
| `synlynk --version` | 0.10 s |
| `synlynk status` | **3.76 s** (2.32 s in `sys` — syscall/fork bound) |
| `status` hot path | 2.34 s of 2.81 s inside `worktree._worktree_status_hint` |
| subprocess forks per `status` | **92** (`fork_exec` 0.74 s, `poll()` 1.36 s) |
| state.db on disk | **287.2 MB** |
| state.db freelist | **62,906 of 70,128 pages = 89.7 % dead space** |
| real data after VACUUM | 28.8 MB |
| total rows, all tables | ~40,000 |
| Read-only connect (`_get_db`) | 0.102 s, called 3× per `status` |
| Subcommands | 77 top-level / 212 subparsers |
| Subcommands with `--json` | **16 / 212 (7.5 %)** |
| `print()` calls in package | 1,251 · modules using `logging`: **2** |
| Function-level `synlynk` imports | **570** · `_pkg()` shim copies: 15 |
| Harness instruction files at repo root | 5 files, 145 KB, **71 % duplicated lines** |
| `synlynk init` writes into a fresh repo | **106 KB ≈ 26,000 tokens** |
| Active sentinels | **261**, oldest 25 days, never aged out |
| Sentinel-flagged waste | **149.2 M tokens** / **$628.91**; 35 jobs touched 0 files |
| Local worktrees | 77 (61 flagged stale) |

---

## Part 1 — Principal Architect, Developer Engagement

*Lens: would I put my platform's developers on this? Does it make my model look good?*

### 1.1 The strategic read

synlynk is solving a problem my org genuinely has and has not solved: **multi-harness
orchestration with verifiable effects**. The five "Invariants" landed in the last five
commits are the most interesting thing in the repo, and they're interesting because
they're *adversarial toward the models themselves*:

- **Invariant 1** — Effect-Verified Completion Contract (`verify_effects.py`, `gh_verify.py`)
- **Invariant 2** — hard in-flight token circuit breakers + runaway worker killer
- **Invariant 3** — fail-closed capability-probed routing
- **Invariant 4** — single-writer WAL ledger with leased worktree locks
- **Invariant 5** — compressed default surface, role+harness doc sync

That set encodes a thesis most agent frameworks refuse to state: **an agent's self-report
is not evidence.** The repo has the receipts to prove the thesis was earned, not theorized
— the memory index alone records "never trust `synlynk jobs` status alone (#202)",
a job-status false-negative RCA (#1377), and Grok's silent-no-op sandbox denial where a
"OK, exit 0" job produced a zero-byte diff. That is hard-won, and it is exactly the
failure class my own dispatch tooling papers over.

**This is the defensible core.** Everything in my critique below is about the 90 % of the
repo that isn't this.

### 1.2 The engagement blocker: this is a TTY product pretending to be a substrate

The positioning is "Universal Context Switchboard" / substrate for agents. The
implementation is a human-facing terminal app. The gap is not stylistic, it's structural:

- **16 of 212 subcommands emit `--json` (7.5 %).** `status --json` exists and is good —
  it's the documented Vizor data contract. It's also nearly alone.
- **1,251 `print()` calls; 2 modules import `logging`.** There is no log stream to
  attach to, no levels, no structured events for an operator or an LLM to consume.
- **132 raw ANSI escape literals** inline in logic modules, so output is
  presentation-coupled at the point of computation.
- **One `__all__` in the whole package.** There is no library surface — an agent that
  wants to *use* synlynk must shell out and screen-scrape.
- **Exit codes are `sys.exit(1)` in 19 places, `0` in 3.** No typed failure taxonomy,
  so a caller cannot distinguish "policy denied" from "git failed" from "crash"
  without parsing English.

The irony an architect will name immediately: **the tool that sells context minimization
is the loudest context consumer in the room.** `synlynk init` on a one-commit empty repo
deposits 106 KB — roughly 26,000 tokens — of instruction files, of which
`AGENTS.md` / `GEMINI.md` / `GROK.md` are ~23 KB near-identical siblings.
Measured across the 5 root instruction files in this repo: **977 substantive lines,
283 unique — 71 % duplication.**

Every dispatched job pays that tax on every cold start, for every harness, forever.

### 1.3 Onboarding: `init` blocks on stdin

`synlynk init` has `--force`, `--wizard`, `--quickstart`, `--brownfield`, `--dry-run`
— and **no `--yes` / `--non-interactive`.** On a fresh repo it prompted three times
(LLM-enrichment `y/N`, collaborator email, industry vertical). It only completed in my
harness because stdin was EOF. In CI, or under a dispatched agent with a pipe,
that is a hang or a silently-defaulted config.

This directly contradicts the repo's own doctrine — `AGENTS.md` mandates
`--print` / non-interactive contracts for dispatched harnesses, and the user's global
instructions require `--yes`/`--non-interactive` on CLI tools. The product doesn't
follow its own rule at its single most important entry point.

### 1.4 Topology: `__init__.py` is a god module

`synlynk/__init__.py` is 3,924 lines and is simultaneously the package root, the
shared-state holder, and the util grab-bag. The consequence is visible in the metrics:

- **570 function-level `from synlynk import …` statements** — deferred imports used to
  dodge cycles.
- **15 independent copies of a `_pkg(name)` dynamic-attribute shim**, called 500+ times
  (`jobs.py` 93, `dispatch.py` 65, `wizard.py` 47…).

`_pkg()` is a runtime `getattr` against the package. It defeats static analysis, IDE
go-to-definition, type checkers, and refactoring tools. It is also *why* the repo needed
to ship its own circular-import detector (`synlynk heal`). The tool exists to manage a
problem the topology creates.

The other monolith: **`viz.py` at 11,354 lines** — 15 % of the package in one file,
for what is described as one of several surfaces.

### 1.5 Verdict — Developer Engagement

**Would I evangelize this today? No. Would I fund the core? Yes.**

The Invariants + effect-verification layer is genuinely ahead of the field and would make
any frontier model look *more* trustworthy in agentic settings, because it stops
attributing fabricated successes to the model. That's a story I want to tell.

But I cannot put external developers in front of 77 commands, a 26,000-token init
footprint, a CLI that hangs on stdin, and a 7.5 % machine-readable surface. The
adoption unit here isn't the CLI — it's the verification kernel.

---

## Part 2 — GM of Product Management

*Lens: adversarial first, then honest evaluation for fit.*

### 2.1 The cynical pass (what I'd say in the first ten minutes)

**"This is one person's workflow, promoted to a platform."**

- **77 top-level commands** for a pre-1.0 tool with one production user. `governs`,
  `mesh`, `spike`, `testbed`, `charters`, `credit`, `swarm`, `marketing`, `media`,
  `connector`, `type`, `score`… Surface area is the *inverse* of product conviction.
  A tool that does 77 things has not yet decided what it is.
- **219 specs, 188 plans, 774 docs, 9.3 MB.** More specification than most shipped
  products, at version 0.23.0-dev. The process has become the product.
- **The dogfood metrics are damning, and they're self-reported.** By synlynk's own
  sentinels: **149.2 M tokens flagged as bloat**, **$628.91 in cost-inflation alerts**,
  and **35 flagged jobs that touched zero files.** 77 local worktrees, 61 stale.
  A 287 MB database that is 90 % dead space.
- **The "Role vs Harness" abstraction is unproven.** Nine roles × five harnesses is a
  45-cell matrix maintained by hand in `policy.json` + four instruction files, and the
  repo's own memory index records those artifacts *diverging* (#426 hardening,
  the #718 fence-marker mismatch, the #884/#899 GEMINI.md revert recurrence).
  An abstraction whose config drifts from itself is not yet an abstraction.
- **Nothing consumes the telemetry.** 261 sentinels, oldest 25 days, no aging, no
  aggregation, no dedupe — 86 COST_INFLATION + 74 TOKEN_BLOAT + 59 TASK_RECEIPT_WARN
  entries piled in a 48 KB markdown file. An alert nobody clears is a log line with
  ambition. The system's most valuable output is its least actioned.

**"And the moat?"** Git worktrees, SQLite, subprocess, argparse. Zero dependencies —
laudable discipline, but it means every capability is reimplementable. The moat isn't
the code.

### 2.2 The objective pass (where it actually fits my product)

Now: the cynical read is about *packaging*, and I was wrong to stop there. Three things
survive scrutiny, and one of them I would buy outright.

**(a) The Effect-Verified Completion Contract — this is the asset.**

Every agent platform in market, including mine, reports success from the agent's own
claim. synlynk has independently rediscovered, documented, and *hard-coded against* the
failure mode where a harness returns exit 0 having done nothing — with specific
receipts (Grok sandbox silent no-op; job-status false-negative RCA #1377, closed with
5 fixes, then a 6th fingerprint found on the regression test itself and refiled as #1429).

That last detail is the tell. A team that finds the bug *in its own regression test for
that bug* is operating at a level of epistemic rigor I would hire for. **Fit: this is a
verification layer for any agentic product. It belongs under my dispatch API, not beside it.**

**(b) Capability-probed fail-closed routing.**

`capability_probe.py` + `capability_baseline.json` + a 1,506-row `capability_ratings`
table with time-decayed scoring (`0.85^weeks`). This is empirical routing: which harness
is actually good at which task, measured, decayed, and enforced fail-closed. My product
routes on a hand-written table. **Fit: direct — this is a model-router substrate, and the
time-decay is the part I'd copy verbatim.**

**(c) The hostile-harness test corpus.**

3,390 tests encoding real multi-agent failure modes — sandbox denials, token staleness,
self-approval classifier collisions, uncommitted-transaction lock cascades, base-branch
bugs, PTY fallbacks. You cannot synthesize this; it's 1,800+ PRs of scar tissue.
**Fit: as an eval suite for agentic reliability, this is more valuable than the CLI it tests.**

### 2.3 What I'd say to the founder

> The 77 commands are not the product. The verification kernel is the product, and you've
> buried it under a personal operating system. Three of your subsystems —
> effect-verification, capability-probed routing, and your failure corpus — are ahead of
> what my team has. The other 74 commands are why nobody knows that.

**Recommendation:** extract `verify_effects` + `capability_probe` + `wal_ledger` +
`circuit_breaker` into a dependency-free library with a typed API and JSON contracts.
That's ~4 modules and a fraction of the LOC. It is adoptable, evaluable, and embeddable.
The CLI becomes a reference consumer of it, not its container.

**Positioning shift:** stop selling "universal context switchboard" (undifferentiated,
crowded, unfalsifiable). Sell **"agent work is not done until it's verified — and we
prove it."** That claim is falsifiable, you can demo it in 30 seconds, and you have
149 M tokens of receipts showing why it matters.

---

## Part 3 — Performance opportunities (measured, ranked)

### P0 — `status` forks 77 git processes serially · **–2.1 s, 8.3× on the hot path**

`worktree._worktree_status_hint()` is documented as a *"Cheap local-only pre-pass"*.
It is O(N) serial `subprocess.run(["git","status","--short"])`, one fork per worktree,
77 of them, on every `synlynk status`. Measured: **2.34 s of `status`'s 2.81 s.**

I benchmarked the fix in-place:

```
serial:            2.01 s
ThreadPoolExecutor(16):  0.24 s     → 8.3× speedup
```

These are I/O-bound `fork`+`wait` calls, so threads are correct and the GIL is a non-issue.

```python
from concurrent.futures import ThreadPoolExecutor

live = [e for e in entries if os.path.isdir(e.path)]
stale = len(entries) - len(live)
with ThreadPoolExecutor(max_workers=min(16, len(live) or 1)) as ex:
    stale += sum(1 for dirty, _ in ex.map(lambda e: _git_status_dirty(e.path), live)
                 if not dirty)
```

**Secondary, and more important:** the staleness heuristic is *"a clean worktree is
stale."* That is wrong — a merged-and-pushed worktree is clean and correct; an abandoned
dirty one is stale and invisible to this check. It's why `status` reports "61 look stale"
with no actionable signal. A cached `git worktree list --porcelain` + mtime check would
be both correct *and* a single fork. Best fix: **don't compute this on `status` at all** —
cache it with a TTL and refresh in `synlynk watch`/daemon.

### P1 — 287 MB database is 89.7 % dead space · **–258 MB, 8.4× on every read connect**

`freelist_count = 62,906` of `page_count = 70,128`. `auto_vacuum = 0`. ~40,000 total
rows. Largest real tables are `workspace_view_edges` (9.4 MB) and `daemon_jobs` (5.8 MB)
— so the live data is ~28 MB and 258 MB is reclaimable.

This compounds because `_get_db(read_only=True)` **copies the entire database into memory
via `source_conn.backup()` on every call** (necessary, since `immutable=1` would hide WAL
frames — the code is right about that). `status` opens 3 such connections.

Measured:

```
VACUUM:                     0.15 s    287.2 MB → 28.8 MB
in-memory backup, bloated:  0.109 s
in-memory backup, vacuumed: 0.013 s   → 8.4×
```

Fixes, in order:
1. **Run `VACUUM` now.** 0.15 s, reclaims 258 MB.
2. **`PRAGMA auto_vacuum=INCREMENTAL`** + periodic `incremental_vacuum` in the daemon,
   so it never regresses. (Full `auto_vacuum` needs to be set before tables exist, so
   this requires a VACUUM to apply — do it in the same maintenance pass.)
3. **Retention policy.** `workspace_view_nodes`/`_edges` (25,931 rows combined) are a
   *derived* graph cache and account for the churn driving freelist growth. They should
   be rebuildable and pruned by `view_id`, not accumulated.
4. **Cache the read-only snapshot per process.** Three full 28 MB copies per `status` is
   still three too many — one memoized connection would do.

### P2 — 212 subparsers built eagerly on every invocation · **~0.25 s**

`argparse.add_parser` × 382 calls = 0.253 s, plus 0.152 s in `Action.__init__`, on *every*
command including `--version`. That's ~40 % of the 0.10 s floor and pure waste for a tool
whose every invocation uses exactly one subcommand.

Fix: lazy subparser registration — dispatch on `sys.argv[1]` to build only the matched
subparser, with the full tree constructed only for `--help` / completion. This is the
single change that makes the CLI feel instant.

### P3 — Structural: `_pkg()` + 570 deferred imports

Not a wall-clock problem (imports are cached) but a **velocity** problem, and it has a
second-order perf cost: 500+ runtime `getattr` lookups on the package, and no ability for
a type checker or tree-shaker to reason about the graph.

Fix: break the `__init__.py` god module. Extract shared state/constants into
`synlynk/_core.py` (or `state.py`) that leaves import cleanly, make `__init__.py` a thin
re-export façade with a real `__all__`, and delete `_pkg()` in favor of static imports.
This is the prerequisite for the library extraction in §2.3 — you cannot ship
`verify_effects` standalone while it reaches back into a 3,924-line package root.

### P4 — Sentinel table has no lifecycle · **48 KB of un-actioned signal**

261 alerts, 25 days deep, appended to a markdown file with no aging, dedupe, or
aggregation. 86 COST_INFLATION + 74 TOKEN_BLOAT are almost certainly a handful of root
causes fanned out across jobs.

Fix: TTL + severity-based auto-expiry, dedupe by `(alert_type, root_cause_fingerprint)`
with an occurrence counter, and a top-3 rollup in `status` instead of a raw count.
`status` reporting "261 active" is indistinguishable from reporting nothing.

### P5 — Instruction-file duplication · **~26,000 tokens per cold start**

71 % duplication across 5 root files; `init` writes 106 KB. Every dispatched job pays it.

Fix: one canonical `.synlynk/instructions/` source of truth with per-harness *includes*
or generated thin stubs, rather than four ~23 KB full copies. The repo's own
Invariant 5 ("Compressed Default Surface, Role+Harness & Doc Sync") is aimed at exactly
this — it hasn't reached the generated artifacts yet. This is also the root of the
recurring drift incidents (#718, #884/#899): four copies of a thing will diverge.

---

## Bottom line

**Combined effect of P0 + P1 + P2:** `synlynk status` goes from **3.76 s → ~0.4 s**,
the state ledger from 287 MB → 29 MB, and the CLI floor from 0.10 s → ~0.06 s.
All three are contained, measurable, and low-risk.

**The strategic call is bigger than the perf work.** synlynk has built something the
frontier labs have not: a working, scar-tissue-informed **verification kernel** for
agentic work — effect-verified completion, capability-probed fail-closed routing, a
single-writer ledger, and circuit breakers that assume the agent is lying. That is
fundable, adoptable, and differentiated.

It is currently packaged inside a 77-command personal operating system with a
26,000-token onboarding footprint and a 7.5 % machine-readable surface, which is why
neither of the two personas above would adopt it as-is — and why both would want the
kernel the moment it stood alone.

---
---

# Addendum — Three Ratings

*Caveat I need to state up front: my knowledge cutoff is May 2026 and today is
2026-09-28. The multi-agent orchestration category moves monthly. Treat the
competitive placement below as a framework with a four-month blind spot, not a
current market survey.*

---

## Part 4 — Rating vs. the developer-tool landscape (assuming Part 1–3 are fixed)

### 4.1 The uncomfortable answer first

**Fixing everything in Parts 1–3 does not materially improve synlynk's competitive
position.** That needs saying plainly, because it's the most useful thing in this
addendum.

Every issue I found is **hygiene**: a slow `status`, a bloated DB, a hanging `init`,
duplicated instruction files, a 7.5 % JSON surface. Fixing them moves synlynk from
*"nobody else can use this"* to *"someone else could use this."* That is table stakes,
not advantage. You'd be paying down debt to reach the starting line, not to win.

The advantage is in §2.3 — extracting the verification kernel and repositioning around
it. That is a **product decision**, not an engineering one, and no amount of the
perf work above substitutes for it.

### 4.2 Where it lands, by category

| Category | synlynk's position | Rating |
|---|---|---|
| **Agent-work verification** (is the agent's "done" true?) | Effectively uncontested. I know of no tool that treats harness self-reports as untrusted and enforces effect-verification with a diff+test gate. | **9/10 — best in class** |
| **Empirical capability routing** (which harness for which task, measured) | Rare. Most routers use hand-maintained tables. The time-decayed (`0.85^weeks`) scoring over 1,506 observations is genuinely sophisticated. | **8/10 — differentiated** |
| **Multi-harness dispatch + worktree isolation** | Crowded. Worktree-per-agent managers, TUI/GUI orchestrators, and IDE-native multi-agent panes all occupy this. synlynk is more rigorous but far less accessible. | **5/10 — mid-pack** |
| **Cost/telemetry for agent work** | Real capability (1,376 cost entries, per-job attribution), but the data is un-actioned (261 orphan sentinels) and the category is filling fast. | **5/10** |
| **Onboarding / time-to-value** | Bottom quartile even after the fixes. 77 commands and a vocabulary of roles × harnesses × goals × stories × epics × GOVERNS stages is a genuine learning cliff. | **3/10** |
| **Distribution & community** | 1 star, 0 forks, 4.5 months public, no PyPI listing (`pipx install git+https://…` only). | **1/10** |

### 4.3 Honest composite

- **As a technical artifact:** top decile. Zero dependencies, 3,390 tests, five
  hard-enforced invariants, 23 named releases in 4.5 months. This is better-engineered
  than most funded developer tools.
- **As an adoptable product:** bottom quartile. The thing that makes it powerful for one
  operator (total surface area, encoded personal workflow) is exactly what makes it
  unadoptable by a second.
- **As a competitor to name a category king:** not yet, and not on this shape.

**The structural problem:** the incumbents win on *proximity* — they're already inside
the editor or the harness the developer uses. A standalone 77-command CLI that must be
learned before it pays out cannot beat proximity. Which is why the kernel-as-library
path matters: a verification library **embeds into** the incumbents instead of
competing with them for the developer's attention. That's a far better hand than
trying to out-CLI the CLIs.

---

## Part 5 — Launch odds: Hacker News and Product Hunt

### 5.1 Hacker News

**As currently positioned: ~10 % chance of front page. With the right framing: ~35–40 %.**

The current pitch — *"the coordination OS for multi-agent development"* — hits three HN
allergies simultaneously: "OS for X" framing, AI-agent orchestration hype, and a
solo-author framework with no users. Predictable top comments:

> *"77 commands and 219 spec documents for a tool with one user."*
> *"The docs are 9 MB and the code is 76 K lines. What is the actual insight here?"*
> *"This is a Makefile and some git worktrees."*

Those comments would be **fair**, and they'd bury the thread.

**But HN is genuinely receptive to what's actually here**, if you lead with the finding
instead of the framework. HN rewards: zero dependencies, stdlib-only Python,
a falsifiable measurement, and a contrarian truth backed by data. You have all four.

The post that works is not a product launch. It's a **finding**:

> **"I ran ~1,800 AI agent jobs over four months. 149M tokens were flagged as waste,
> $629 of it, and 35 jobs reported success having changed zero files."**

That title is data-first, self-critical, immediately falsifiable, and names a problem
every HN reader using agents has felt but not measured. The tool becomes the *answer*
in paragraph four rather than the *ask* in the headline. Your Grok "exit 0 on a
zero-byte diff" story and the #1377 → #1429 chain (finding the bug *in the regression
test for that bug*) are the strongest technical anecdotes in the repo and belong in
that post.

**Concrete blockers I found, all fixable before launch:**

| Blocker | State |
|---|---|
| No demo GIF or video anywhere in the repo | 0 found — this is the #1 conversion asset and it's missing |
| Not on PyPI | Install is `pipx install git+https://…`; HN readers distrust it and `pipx install synlynk` fails |
| README badge drift | Says `v0.22.0` / `3213 tests`; actual is `0.23.0-dev` / **3390**. Your own `release --check-docs` exists to catch this |
| Social proof at t=0 | 1 star, 0 forks. A launch off zero is a cold start |
| 77 commands in `--help` | First thing a curious visitor runs. It reads as unfocused |

**Sustained traction after the spike:** low without a hosted playground or a
60-second "watch it catch a lying agent" demo. HN gives you one day; the demo is what
converts that day into stars.

### 5.2 Product Hunt

**~5–10 % chance of a meaningful outcome. My recommendation: skip it, or defer.**

PH is a visual, prosumer-leaning surface that rewards screenshots, a clear before/after,
and a maker narrative. A terminal CLI for multi-agent engineering governance is close to
a worst-case fit. Worse, PH traffic for a tool like this converts into low-intent
signups that generate support load without generating users.

**The one exception:** Vizor. A browser HUD showing a live multi-agent fleet, cost burn,
and a workspace graph is *genuinely* PH-shaped — it's visual, instantly legible, and
demoable in a single screenshot. If you want PH, **launch Vizor as the product and the
CLI as the engine.** Not before Vizor is polished enough to be the front door.

Note your own roadmap already contains *"prepare HN and Product Hunt copy"* as a P0
under "Release candidate and announcement." The sequencing instinct is right; I'd
split that item — HN with the findings post, PH deferred to a Vizor-led launch.

---

## Part 6 — Roadmap rating: **7/10**

Decomposed, because the average hides the story:

| Dimension | Score | Why |
|---|---|---|
| Execution velocity | **9/10** | 29 shipped vs 7 planned; 23 named releases in 4.5 months |
| Intellectual honesty | **9/10** | Explicit `superseded` / `deferred` / rescoping notes |
| Problem diagnosis | **8/10** | Already names time-to-wow, drop-off, test runtime |
| Document quality | **3/10** | Unordered, colliding version namespace |
| Date realism | **2/10** | rc1 is 3 days out with 4 untouched P0s |
| Post-1.0 sequencing | **4/10** | Enterprise ladder before single-user proof |
| Subtraction discipline | **2/10** | No removal lane anywhere across 29 releases |

### 6.1 What's genuinely strong

**The shipped-to-planned ratio is inverted from the norm, in the good direction.**
29 `[shipped]` against 7 `[planned]`. The typical solo project has five shipped and
forty aspirational. This is a roadmap that describes work *done*, and that is the
single most credible signal in the document.

**It self-corrects in writing.** Two `[superseded]`, one `[deferred]`, and prose that
admits things like *"rescoped from planned v0.14.0 — held back as incomplete/inactive
per PM review"* and, on B2, *"closed as investigation-complete… root-caused to Codex
workspace-write sandbox blocking api.github.com egress structurally, not an
identity/token bug. Recommended design, not yet implemented as code."* That last entry
is a model of honest status reporting — it distinguishes *understood* from *fixed*,
which almost no roadmap does.

**The right things are release-gated.** The five Invariants are marked
*"Release-blocking gate for v1.0.0 Dev Preview."* Gating the launch on the
differentiator rather than on feature count is the correct instinct.

**It already knows about the onboarding problem.** v1.0.0-rc1 contains
*"15-Minute Time-to-Wow,"* *"install-to-first-PR in <15 minutes,"* and
*"measure… user drop-off."* I flagged the 26,000-token init footprint in Part 1 as a
finding; the roadmap had already identified the symptom. Credit where due.

### 6.2 What's broken

**1. The generated document is unordered — a defect in the generator.**
Header says *"generated — source of truth is state.db."* Actual render order:
v1.0.0 (L109) → v1.1.0 → v1.2.0 → v1.3.0 → Future → **v0.13.1 (L161)** → 1.0.0 Preview →
**v0.20.0 (L216)** → v1.0.0-rc1 → **v0.21.0 (L242)** → v0.22.0 → v0.23.0.
Nobody but the author can read this. That matters the moment you want a contributor.
Fix: sort by semver (or target date) in the generator — a small change to
`synlynk roadmap`'s renderer.

**2. Three colliding 1.0.0 entries.**
- `v1.0.0 — GA: Community Layer + Public Launch` (target: post-preview)
- `1.0.0 — Developer Preview Public Launch` (target: 2026-10-01)
- `v1.0.0-rc1 — 15-Minute First Win…` (target: **2026-10-01** — same day as the preview)

An outside reader cannot determine what "1.0" means or when it lands. Pick one
numbering: `v1.0.0-rc1` → `v1.0.0` (Developer Preview) → `v1.1.0` (Community/GA).
Never ship a preview and its own release candidate on the same date.

**3. The nearest date is not survivable.**
v1.0.0-rc1 targets **2026-10-01 — three days from now** — with four open P0s: pipx
distribution, autonomous deep-scan brief, 15-minute field trials across three repos,
and test-runtime remediation. That is a quarter of work. Slipping it silently is how
roadmaps stop being believed, including by their author. Re-date it now, visibly.

**4. The post-1.0 arc is an org-chart ladder, not a demand curve.**
v1.1.0 Cross-Workgroup (Q4 2026) → v1.2.0 Enterprise Workspace (Q1 2027) →
v1.3.0 Domain Communities + Tokq convergence (Q2 2027). Team → org → enterprise →
community entitlements, sequenced across three quarters, **with 1 star and 0 forks and
no evidence a second human has ever run the tool.**

This is the largest strategic risk in the document. Every one of those tiers is
expensive, and each is premised on adoption that hasn't been demonstrated at n=1→2.
The honest next milestone after the preview is not "Cross-Workgroup" — it's
**"ten developers installed it and five came back in week two."** Nothing on the
roadmap measures that, and no amount of enterprise governance matters until it's true.

**5. There is no subtraction lane.**
Across 29 shipped releases, every entry adds. Nothing removes a command, deprecates a
concept, or retires a subsystem. Invariant 5 (*"Compressed Default Surface"*) is the
sole gesture toward subtraction, and it's bundled into a one-time release gate rather
than owned as a standing discipline. A 77-command tool with no removal lane is a
100-command tool in two quarters. **Recommendation: add a permanent "Surface Reduction"
lane with a hard budget — e.g. no net-new top-level commands before v1.0, and a named
owner for deprecations.**

### 6.3 The roadmap's real problem, in one sentence

It is an *excellent* record of what was built and a *poor* instrument for deciding
what to build next — because it optimizes for completeness of the author's mental model
rather than for the next unproven assumption. The most valuable thing you could add to
it is not a feature. It's an **adoption milestone with a number on it**, placed before
v1.1.0, that the enterprise tiers are not allowed to start until it passes.

---
---

# Part 7 — Test suite: runtime, and a CI/local divergence

*This section resolves the pending item from Part 6. It also contains the most
operationally urgent finding in the whole review.*

## 7.1 Runtime — the rc1 P0 is closer than it looks, but `--dist loadfile` caps it

Full suite, serial, this machine (Python 3.14, macOS):

```
2 failed, 3385 passed, 1 skipped, 2 deselected in 488.48s (8:08)
```

CI runs `-n 4 --dist loadfile`, so expect roughly **150–200 s** — right at the edge of
the roadmap's `#1492` P0 target of **<180 s**.

The problem is that **`--dist loadfile` pins a whole file to one worker**, and the two
slowest tests live in the same file:

| Duration | Test |
|---|---|
| **43.33 s** | `test_platform_ops.py::test_format_platform_report_contains_layers` |
| **42.27 s** | `test_platform_ops.py::test_collect_platform_report_shape` |
| 32.02 s | `test_ecosystem_status.py::test_probe_writes_status_and_cycle_capability` |
| 25.47 s | `test_roles.py::test_cmd_agent_add_onboards_agent` |

`test_platform_ops.py` alone is an **~85 s single-worker floor**. Adding workers cannot
go below it. So the `<180 s` target is not a parallelism problem — it's a
*four-tests* problem.

**The recommendation is not "add more workers."** It's:
1. Find out why four tests take 25–43 s each. At these durations they are almost
   certainly paying real `subprocess` spawns or SQLite `busy_timeout` waits, not
   doing 40 s of computation.
2. Either fix the underlying waits or split `test_platform_ops.py` so
   `--dist loadfile` can spread its two 40-second tests across workers.

That is a much smaller piece of work than the P0 implies, and it gets under 180 s
without touching the other 3,386 tests.

## 7.2 Two tests fail on main, deterministically — while CI reports green

At `c35a42e2` (current `main`, clean tree):

```
FAILED tests/test_ecosystem_status.py::test_probe_writes_status_and_cycle_capability
FAILED tests/test_probe.py::test_probe_extracts_claude_version_from_descriptive_output
```

**CI is green on this exact SHA.** `gh run list` shows `success` for `c35a42e2`, and
`test.yml` has no `|| true` and no `continue-on-error` — the step would genuinely fail.

### What I ruled out

I tried to make these pass and could not. Each of these was a hypothesis, tested and
falsified:

| Hypothesis | Test | Result |
|---|---|---|
| Parallel test pollution | Ran the 2 alone | **Still fails** |
| A stranded process write-locking the ledger | `BEGIN IMMEDIATE` on real DB | **DB not locked** — hypothesis wrong |
| Test stub omits production pragmas | Forced WAL + `busy_timeout=30000` | **Still fails** (waits 30 s, then locks) |
| Local harness binaries alter the path | Ran with `claude/codex/agy/grok` hidden from `PATH` | **Still fails** |
| xdist changes the outcome | Ran exact CI `-n 4 --dist loadfile` | **Still fails** |
| Python version (CI is 3.10/3.12, local is 3.14) | Ran on Python 3.12.3 | **Still fails** |

**I could not determine why CI is green, and I am not going to guess.** The remaining
untested variables are macOS vs. `ubuntu-latest` and the presence of a populated
`~/.synlynk/` on this machine. That's the next thing to check, and it should be
checked — because one of two things is true, and both are bad:

- **Either** these tests encode a real bug that CI's environment hides, in which case
  the green badge is false comfort; **or**
- **they are environment-sensitive**, in which case they fail for every developer whose
  machine resembles the maintainer's — including the maintainer.

Both outcomes undermine the same thing: *CI green is currently not evidence that the
suite passes.* For a project whose entire thesis is **"a status report is not evidence,
verify the effect"** (Invariant 1), a green CI badge that disagrees with the
maintainer's own machine is the sharpest possible irony — and the most important thing
on this list to fix before a public launch.

### The mechanism, which is real regardless

The failure is a **nested writer**, and the call chain is unambiguous:

```
probe.py:1626  cmd_probe
probe.py:784     _probe_agent
probe.py:301       _diff_and_queue_new_models   ← holds an OPEN write conn
probe.py:310         _queue_calibration_sweep(conn)
capability_sweep.py:214  _dispatch_calibration_task
                           → dispatch_agent(...)
quota.py:555                 _open_reservation  ← opens a SECOND conn, INSERTs
                             sqlite3.OperationalError: database is locked
```

Two things about this are worth separating from the CI question:

**1. `busy_timeout` cannot fix it.** I proved this: with `busy_timeout=30000` the test
waits the full 30 seconds and *still* fails. A second writer in the same process,
blocked behind a transaction that can only commit after the second writer returns, is
a **self-deadlock**. No timeout resolves it — it just converts an instant failure into
a 30-second stall. That stall is very likely a contributor to the 25–43 s tests in §7.1.

**2. A probe can trigger a dispatch.** `synlynk probe` — a diagnostic, read-shaped
command — transitively reaches `dispatch_agent()`, i.e. it can spend money and spawn an
agent, while holding an open write transaction on the ledger. Even setting the deadlock
aside, that is a surprising amount of authority for a command named `probe`, and it is
precisely the coupling **Invariant 4 (One ledger, one writer)** was shipped three
commits ago to eliminate. The invariant is enforced at the connection layer but the
nested-writer *call pattern* survived it.

**Fix:** pass the existing `conn` down the whole chain rather than re-acquiring, and
make the quota-reservation path accept a caller-supplied connection (it already has an
`own_conn` idiom at lines 255, 479, 987 — line 555's caller just isn't using it).
Longer term, `probe` should queue calibration work rather than dispatch it inline.

## 7.3 Unrelated but worth knowing: a stranded `init` is holding the ledger open

While tracing the above I found:

```
PID 34436   started Sun Sep 27 16:20:02   STAT S+   cwd /Users/nikhilsoman/dev/synlynk
  stdin → /dev/ttys006  (a live TTY, blocked at a prompt)
  holds  ~/.synlynk/workspaces/synlynk/state.db  (fd 3u, 9u)
```

This is an interactive `synlynk init` that has been **sitting at a prompt for ~8 hours**
in another terminal, holding the canonical 287 MB ledger open the whole time.

It is *not* the cause of the test failures — I checked, the DB is not write-locked.
But it is organic, independent corroboration of the Part 1.3 finding: **`init` blocks
on stdin and has no `--yes`/`--non-interactive`.** A prompt nobody answers becomes a
process nobody notices, holding a handle on the single source of truth. Add the flag,
and add a timeout or non-TTY detection on the prompts.

## 7.4 Where this lands the launch readiness

Part 5 estimated HN odds assuming the engineering held up. §7.2 changes the
prerequisite list. Before any public launch:

1. **Reconcile CI with local.** Until `pytest` passes on the maintainer's machine, the
   test count in the README badge is a number, not an assurance. (The badge is also
   stale: `3213` vs. an actual `3390` collected.)
2. **Fix or quarantine the 2 failures.** A first-time contributor who clones, runs the
   suite, and sees 2 red is gone. That is the single highest-leverage pre-launch fix,
   above every performance item in Part 3.
3. **Then** do the §7.1 runtime work to clear the `<180 s` P0.
