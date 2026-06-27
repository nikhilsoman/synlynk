# BS-7: Skill Pack Interoperability + Benchmarks

**Date:** 2026-06-27  
**Status:** Design approved — benchmark execution week of 2026-06-30  
**Story:** story-bs7-interop  
**Scope:** Benchmark framework + instruction coexistence spec. Projects A (Trio Demo), B (PulseScape), G (MCP Server) are separate sessions.

---

## The Claim

Skill packs (Superpowers, GStack) operate at the **prompt/workflow layer** — TDD discipline, code quality gates, prompt engineering. synlynk operates at the **process/state layer** — persistent memory, context injection, cost control, flatline sentinel, dispatch and consensus. They solve different problems and never compete for the same instruction surface *when configured correctly*.

> **synlynk = coordination OS. Skill packs = domain expertise modules. Different layers → better together.**

The failure mode: when both inject into `CLAUDE.md` / `.cursorrules` without a priority contract, agents see contradicting instructions and exhibit non-adherence or unpredictable behaviour. This is the AB-11 problem. `git-drift` prevents it.

### Layer Stack

```
┌────────────────────────────────────────────────────┐
│  Application Layer                                  │
│  Superpowers · GStack · GSD · Everything-CC        │
│  (domain expertise modules — advisory)              │
├────────────────────────────────────────────────────┤
│  OS Layer — synlynk                                 │
│  memory · context injection · flatline · costs     │
│  dispatch · consensus · budget enforcement          │
├────────────────────────────────────────────────────┤
│  AI CLI Layer                                       │
│  claude · agy · codex · grok                       │
└────────────────────────────────────────────────────┘
```

---

## Section 1 — Coexistence Theory (AB-11)

### The Instruction Surface Overlap

All three (synlynk, Superpowers, GStack) write to overlapping files:

| File | synlynk | Superpowers | GStack |
|------|---------|-------------|--------|
| `CLAUDE.md` | ✅ OS preamble | ✅ skill hooks | ✅ quality rules |
| `.cursorrules` | ✅ OS block | — | ✅ lint rules |
| `settings.json` | — | ✅ hooks | — |
| `AI_INSTRUCTIONS.md` | ✅ | — | — |
| `GEMINI.md` | ✅ | — | — |

**Overlap zone:** `CLAUDE.md` and `.cursorrules` — primary conflict surface.

> **Note:** Conflict taxonomy is based on assumed behaviour. Phase 0 (validation) must confirm actual install output before benchmark runs.

### Conflict Taxonomy

| Type | Example | Symptom | Resolution |
|------|---------|---------|------------|
| **Direct contradiction** | synlynk: "always run tests before commit" · GStack: "never block on tests in draft PRs" | Agent skips tests randomly or asks for clarification every run | synlynk block = authoritative; skill pack rule = advisory |
| **Scope bleed** | Superpowers TDD skill injected into a `synlynk exec agy` session not scoped for TDD | Token bloat; agent runs TDD steps for a 2-line config change | Context scoping: only inject skill hooks matching current story's role |
| **Format collision** | GStack adds its own `## Code Quality` section; synlynk already has one | Duplicate sections; one silently ignored by agent | `git-drift` flags duplicate headings at commit time |
| **Authority ambiguity** | Both synlynk and Superpowers claim "you MUST follow these rules" | Agent paralysis or arbitrary priority selection | `synlynk:start/end` fencing declares OS-level authority explicitly |

### The Resolution Protocol

**`synlynk:start/end` fencing** in `CLAUDE.md`:

```markdown
<!-- synlynk:start -->
# OS Layer Instructions
[persistent memory, budget limits, dispatch rules, flatline policy]
<!-- synlynk:end -->

# Skill Pack Zone
[Superpowers / GStack rules go here — advisory, not authoritative]
```

Agents treat content within the fence as non-overridable OS instructions. Skill pack content below the fence is advisory. This is enforced mechanically by `git-drift` at commit time.

---

## Section 2 — `git-drift` (Enforcement Artifact)

`git-drift` is a pre-commit hook + config scanner that makes the coexistence strategy machine-checkable. It ships as part of synlynk and as a standalone public utility.

### Manifest Schema

`.synlynk/instruction-manifest.json` declares ownership of every section:

```json
{
  "version": "1.0",
  "files": {
    "CLAUDE.md": {
      "fence": {
        "start": "<!-- synlynk:start -->",
        "end": "<!-- synlynk:end -->"
      },
      "zones": {
        "os": "within_fence",
        "skill_pack": "below_fence",
        "user": "below_fence"
      },
      "checks": [
        "no_duplicate_headings",
        "fence_intact",
        "skill_pack_below_fence"
      ]
    },
    ".cursorrules": {
      "zones": { "os": "synlynk_block", "skill_pack": "remainder" },
      "checks": ["no_duplicate_rules"]
    }
  }
}
```

### Check Outcomes

| Outcome | Condition | Action |
|---------|-----------|--------|
| ✅ Pass | All sections in declared zones, no duplicates, fence intact | Allow commit |
| ⚠️ Warn | Skill pack content detected above the synlynk fence | Print warning, allow commit |
| ❌ Block | OS-zone content modified without manifest update; fence removed | Block commit, print remediation |

### Install

- **Via synlynk:** `synlynk init` writes the manifest and installs the pre-commit hook automatically.
- **Standalone:** `pip install git-drift && git-drift install` — works in any repo, no synlynk required. Manifest defaults to synlynk conventions but is fully configurable.

### Benchmark Role

R4 is the only benchmark round with `git-drift` active. The token savings in R4 vs R2 (Superpowers only) are attributable to two factors: (1) synlynk's scoped context injection, and (2) zero instruction conflict overhead enforced by `git-drift`. This makes `git-drift` a measurable variable in the experiment, not just a convenience.

### Scope for BS-7

**In spec:** manifest schema, 4 check types, install via `synlynk init`, standalone pip package.  
**Future:** CI/CD integration, auto-fix mode (`git-drift fix`), VSCode extension, registry of known skill pack manifests.

---

## Section 3 — Benchmark Design

### Skill Packs in Scope

Two packs, two roles:

- **Superpowers** — benchmark rounds (R2 + R4). Primary proof point for "better together." Used daily, highest adoption, brainstorming + TDD skills most relevant to the `flatline` build.
- **GStack** — coexistence theory only (conflict taxonomy + Phase 0 validation). Provides a second data point for the instruction surface overlap table and conflict examples. Not a separate benchmark round — isolating three variables (bare / Superpowers / synlynk+Superpowers) is cleaner than four.

GSD and Everything-ClaudeCode: deferred. `git-connectome` overlaps with BS-6 (`synlynk viz`) — excluded.

### The Target: `flatline`

A standalone Python CLI circuit-breaker. `flatline <cmd>` wraps any shell command, hashes stdout on failure, and kills the process after 3 consecutive identical failures — saving developers from runaway agent token bills.

- **~150 lines of Python, stdlib only, pip-installable**
- **Self-referential story:** building the loop-defense tool *with* the tool that defends against loops
- **3-session build:** S1 = design CLI + spec, S2 = implement stdout hashing + exit logic, S3 = tests + package

### Phase 0 — Validation (prerequisite)

Before running any benchmark round:

1. **Dispatch** Agy to install Superpowers in a sandboxed temp repo; capture diff of all instruction files before/after
2. **Dispatch** Codex to do the same for GStack
3. **Manually review** both diffs and confirm the actual instruction surface
4. **Update conflict taxonomy** (Section 1) if real installs differ from assumed behaviour
5. Lock round definitions and proceed to benchmark

### The 4 Rounds

| Round | Stack | Description |
|-------|-------|-------------|
| **R1 — Bare** | Claude Code only | Baseline. No skill packs, no synlynk. 3 sessions. |
| **R2 — Superpowers** | Claude Code + Superpowers | Skill pack overhead + quality lift. No synlynk. |
| **R3 — synlynk only** | Claude Code + synlynk | Context injection + flatline sentinel in isolation. No skill packs. |
| **R4 — synlynk + Superpowers** | Claude Code + synlynk + Superpowers + `git-drift` | The "better together" round. Expected: lowest token spend, highest coverage. |

All rounds use the same starting prompt, the same task definition, and the same Claude model at the same temperature. Each round runs `flatline` from scratch — no shared state between rounds.

### Metrics

**Primary (objective):**

| Metric | Source | Notes |
|--------|--------|-------|
| Total token spend (3 sessions combined) | `project-docs/costs.md` | synlynk captures automatically in R3+R4; manual for R1+R2 |
| Session count to working CLI | Git commit log | Did R1/R2 need a 4th session to fix breakage? |

**Secondary (directional):**

| Metric | Source | Notes |
|--------|--------|-------|
| Test coverage % | `pytest --cov` output | Quality sanity check; not definitive given agent variance |
| Retry / loop incidents | `.synlynk/telemetry.json` (R3+R4), manual count (R1+R2) | Counts agent loops interrupted by flatline sentinel or human |

### Expected Narrative

```
R1: baseline cost, moderate coverage, manual loop detection
R2: +N% token overhead from skill pack prompts, higher coverage
R3: -X% token spend via scoped context, similar coverage to R2
R4: lowest token spend, highest coverage, zero instruction conflicts
```

The HN headline: **"R4 cost 60% less than R1 at equal or better test coverage."**

---

## Section 4 — Separate Sessions (out of BS-7 scope)

| Project | Session | Why excluded from BS-7 |
|---------|---------|------------------------|
| **A — Trio Orchestration Demo** | Separate | Qualitative narrative showcase; no benchmark methodology needed |
| **B — PulseScape** | Separate | 6-session end-to-end product build; own planning session |
| **G — MCP Registry contribution** | Separate | Distribution play / ecosystem surface; own spec |
| **`git-connectome`** | BS-6 | Overlaps `synlynk viz` — already scoped in BS-6 |

---

## Execution Timeline

| Date | Activity |
|------|----------|
| 2026-06-27 | BS-7 design approved (this doc) |
| 2026-06-30 | Phase 0 — validation dispatches (Agy + Codex) |
| 2026-06-30 | Review validation output; update conflict taxonomy if needed |
| 2026-07-01 | R1 + R2 benchmark runs |
| 2026-07-02 | R3 + R4 benchmark runs |
| 2026-07-03 | Scorecard compiled; narrative drafted for HN post |

---

## Done Criteria

- [ ] Phase 0 dispatches complete and conflict taxonomy validated against real installs
- [ ] R1–R4 runs complete; token spend and session count recorded for all rounds
- [ ] Test coverage captured for all rounds via `pytest --cov`
- [ ] Retry incidents logged for all rounds
- [ ] Scorecard table written to `docs/proposals/blog/bs7-benchmark-results.md`
- [ ] `git-drift` manifest schema committed to synlynk repo
- [ ] `git-drift` pre-commit hook wired into `synlynk init`
- [ ] BS-7 narrative incorporated into HN launch post
