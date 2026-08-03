---
decision_id: dec-2f979483
topic: "DEEP SURVEY (not a yes/no feature decision): Full-fleet operability of synlynk as BOTH (A) home harness and (B) headless execution target. We have pursued this goal for months with many stories yet still see inconsistent behaviour. Your job is an empirical, harness-specific gap analysis that will feed a brainstorm agenda.

CONTEXT (ground truth on this machine as of 2026-08-02, after #648/#650 sandbox DB fallback landed):
- Supported fleet in AGENT_CAPABILITY_BASELINES: claude, agy, codex, grok, local(aider).
- CLIs present: claude 2.1.220, agy 1.1.8, codex 0.146.0, grok 0.2.118, aider 0.86.2.
- `synlynk open` allowlist help text: claude,agy,codex,grok ONLY (local missing).
- Root instruction files: CLAUDE.md yes, GEMINI.md yes, GROK.md yes, AGENTS.md MISSING, AI_INSTRUCTIONS.md no.
- doctor TC summary: claude OK; codex TC-2 FAIL failed=['--approval-policy']; agy OK but TC-5 SOP missing 6 harness sections; grok OK; local TC-1 FAIL requires_pty=False, TC-3 FAIL unreachable 127.0.0.1:8080.
- Open issues still relevant: #648-family state in sandboxes (partially fixed), #426 Agy/Codex GH-write headless, #577 Codex gh auth expired, #340 Codex sandbox blocks package install, #332 preflight auth/headless gaps, #112 doctor TC-2/4 preflight before dispatch, #347 no proof instruction file loaded, #338 grants no-op for Agy/Grok/local, #342 Grok CWD auto-relocation, #344/#351/#345 instruction template contamination, #330 per-worktree state.db corruption, #573 Agy Stitch MCP headless, #579 stale job summary UNKNOWN, #411 harness-managed directive corruption.
- Recent cluster work: harness compatibility/capability (#587), fleet-parity security (#641), sandbox DB fallback (#650).
- Long-arc tension: wrapper-of-vendor-CLIs vs native synlynk-as-a-harness (docs/strategy/synlynk-as-a-harness.md).

THREE PRODUCT CLAIMS TO AUDIT (answer whether EACH is true TODAY, per harness):
1. HOME: A user inside an interactive CLI session of THIS harness can launch/use synlynk (open/shell/exec/status/dispatch/doctor/...) without leaving that session, and get a first-class experience.
2. FUNCTION-100: Once synlynk is in play from that home, core verbs work fully (not "mostly"): status, doctor, dispatch, jobs, logs, pr check, cost, story, decide, etc. — including DB-backed commands inside any sandbox the home harness itself uses when spawning tools.
3. CROSS-DISPATCH: From that home session, synlynk can RELIABLY dispatch headless work to EVERY other fleet member (claude/agy/codex/grok/local), and those jobs complete, report cost/files, and can do required side-effects (git/gh) when authorized.

ANSWER STRUCTURE (required — speak primarily from YOUR harness's POV; still comment on peers you depend on):
A. Identity: which harness are you (claude|agy|codex|grok)? What is your real headless invocation contract (flags, prompt delivery, PTY needs, auth surface, network)?
B. Claim 1 HOME — grade PASS / PARTIAL / FAIL for your harness as home. Concrete gaps (commands, instruction reach, `synlynk open`, context injection, PATH/install of synlynk, permission prompts blocking).
C. Claim 2 FUNCTION-100 — grade PASS / PARTIAL / FAIL. Call out DB path, sandbox FS, config null-org, instruction file, flag drift, doctor false-greens, selftest blind spots.
D. Claim 3 CROSS-DISPATCH — for EACH target in {claude,agy,codex,grok,local}: grade PASS / PARTIAL / FAIL when YOU are home and they are headless workers. Note GH-write, network, sandbox, token strip, cost capture, completion reporting.
E. Top 5 failure modes you have personally seen or that match live issues — ranked by user-visible pain.
F. Empirical audit plan: what would prove each claim true? Propose a minimal automated matrix (rows=home harness, cols=verb or target) that selftest/doctor/probe should run, including live vs dry.
G. Brainstorm agenda items: 5–10 sharp questions/decisions for a human+agents brainstorm (not implementation plans). Include go/no-go on wrapper vs native harness if relevant.
H. One-sentence position: "Completely supported today: NO/YES/ALMOST — biggest single gap is X."

Be concrete and skeptical. Prefer evidence and issue numbers over aspirational docs. 300–500 words is fine if denser is better; do not pad."
date: 2026-08-02
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
DEEP SURVEY (not a yes/no feature decision): Full-fleet operability of synlynk as BOTH (A) home harness and (B) headless execution target. We have pursued this goal for months with many stories yet still see inconsistent behaviour. Your job is an empirical, harness-specific gap analysis that will feed a brainstorm agenda.

CONTEXT (ground truth on this machine as of 2026-08-02, after #648/#650 sandbox DB fallback landed):
- Supported fleet in AGENT_CAPABILITY_BASELINES: claude, agy, codex, grok, local(aider).
- CLIs present: claude 2.1.220, agy 1.1.8, codex 0.146.0, grok 0.2.118, aider 0.86.2.
- `synlynk open` allowlist help text: claude,agy,codex,grok ONLY (local missing).
- Root instruction files: CLAUDE.md yes, GEMINI.md yes, GROK.md yes, AGENTS.md MISSING, AI_INSTRUCTIONS.md no.
- doctor TC summary: claude OK; codex TC-2 FAIL failed=['--approval-policy']; agy OK but TC-5 SOP missing 6 harness sections; grok OK; local TC-1 FAIL requires_pty=False, TC-3 FAIL unreachable 127.0.0.1:8080.
- Open issues still relevant: #648-family state in sandboxes (partially fixed), #426 Agy/Codex GH-write headless, #577 Codex gh auth expired, #340 Codex sandbox blocks package install, #332 preflight auth/headless gaps, #112 doctor TC-2/4 preflight before dispatch, #347 no proof instruction file loaded, #338 grants no-op for Agy/Grok/local, #342 Grok CWD auto-relocation, #344/#351/#345 instruction template contamination, #330 per-worktree state.db corruption, #573 Agy Stitch MCP headless, #579 stale job summary UNKNOWN, #411 harness-managed directive corruption.
- Recent cluster work: harness compatibility/capability (#587), fleet-parity security (#641), sandbox DB fallback (#650).
- Long-arc tension: wrapper-of-vendor-CLIs vs native synlynk-as-a-harness (docs/strategy/synlynk-as-a-harness.md).

THREE PRODUCT CLAIMS TO AUDIT (answer whether EACH is true TODAY, per harness):
1. HOME: A user inside an interactive CLI session of THIS harness can launch/use synlynk (open/shell/exec/status/dispatch/doctor/...) without leaving that session, and get a first-class experience.
2. FUNCTION-100: Once synlynk is in play from that home, core verbs work fully (not "mostly"): status, doctor, dispatch, jobs, logs, pr check, cost, story, decide, etc. — including DB-backed commands inside any sandbox the home harness itself uses when spawning tools.
3. CROSS-DISPATCH: From that home session, synlynk can RELIABLY dispatch headless work to EVERY other fleet member (claude/agy/codex/grok/local), and those jobs complete, report cost/files, and can do required side-effects (git/gh) when authorized.

ANSWER STRUCTURE (required — speak primarily from YOUR harness's POV; still comment on peers you depend on):
A. Identity: which harness are you (claude|agy|codex|grok)? What is your real headless invocation contract (flags, prompt delivery, PTY needs, auth surface, network)?
B. Claim 1 HOME — grade PASS / PARTIAL / FAIL for your harness as home. Concrete gaps (commands, instruction reach, `synlynk open`, context injection, PATH/install of synlynk, permission prompts blocking).
C. Claim 2 FUNCTION-100 — grade PASS / PARTIAL / FAIL. Call out DB path, sandbox FS, config null-org, instruction file, flag drift, doctor false-greens, selftest blind spots.
D. Claim 3 CROSS-DISPATCH — for EACH target in {claude,agy,codex,grok,local}: grade PASS / PARTIAL / FAIL when YOU are home and they are headless workers. Note GH-write, network, sandbox, token strip, cost capture, completion reporting.
E. Top 5 failure modes you have personally seen or that match live issues — ranked by user-visible pain.
F. Empirical audit plan: what would prove each claim true? Propose a minimal automated matrix (rows=home harness, cols=verb or target) that selftest/doctor/probe should run, including live vs dry.
G. Brainstorm agenda items: 5–10 sharp questions/decisions for a human+agents brainstorm (not implementation plans). Include go/no-go on wrapper vs native harness if relevant.
H. One-sentence position: "Completely supported today: NO/YES/ALMOST — biggest single gap is X."

Be concrete and skeptical. Prefer evidence and issue numbers over aspirational docs. 300–500 words is fine if denser is better; do not pad.

## Panel Inputs

### claude
**A. Identity:** Claude (this harness, Claude Code CLI). Headless contract: invoked via `synlynk dispatch claude` or direct `claude -p "<prompt>"`; supports non-interactive `--print`/print-mode, no PTY requirement, auth via `ANTHROPIC_API_KEY`/subscription token already resident in this session, network egress to Anthropic API is open. Tool access controlled by permission mode — headless runs need `--permission-mode` pre-set or they stall on approval prompts.

**B. Claim 1 HOME — PARTIAL.** `synlynk open` allowlist (claude,agy,codex,grok) covers me; CLAUDE.md loads natively without extra plumbing (#347's "no proof instruction file loaded" doesn't apply to my own harness reading its own file, but synlynk can't *prove* it beyond convention). Gap: local(aider) isn't in the open allowlist at all — asymmetry between "supported fleet" and "openable fleet."

**C. Claim 2 FUNCTION-100 — PARTIAL.** doctor shows me OK, but "OK" ≠ verified — #112 flags preflight gaps before dispatch, and #648/#650 only patched sandbox DB fallback; no evidence yet that dispatch-nested sandboxes (my own subprocess spawns) inherit that fix rather than just top-level exec. Doctor false-greens are a real risk here: an OK grade documents flag presence, not round-trip success.

**D. Claim 3 CROSS-DISPATCH (me as home):**
- claude→claude: PASS (self, trivially).
- claude→agy: PARTIAL — works but #426 GH-write depends on unverifiable local settings.json state; #573 Stitch MCP headless open.
- claude→codex: FAIL-leaning — TC-2 `--approval-policy` failure is a hard flag mismatch, not cosmetic; #340 sandbox blocks installs, #577 gh auth expiry.
- claude→grok: PARTIAL — #342 CWD auto-relocation silently changes where output lands, dangerous for cost/file reporting.
- claude→local(aider): FAIL — TC-1/TC-3 confirm no PTY, no reachable port; not even in `open` allowlist, so home story doesn't exist either.

**E. Top 5 pain (ranked):** 1) doctor "OK" masking real dispatch failure (#112) — worst because it's silent. 2) Codex flag drift (TC-2) breaking dispatch outright. 3) local/aider excluded from `open` while listed as supported — contradicts the fleet claim on paper. 4) #342 Grok CWD drift corrupting file/cost attribution. 5) #330 per-worktree state.db corruption — undermines trust in every other reading.

**F. Audit matrix:** rows = {claude,agy,codex,grok,local} as home; cols = {status,doctor,dispatch-dry,dispatch-live,jobs,logs,pr-check,cost,story,decide}; run dry (flag/auth presence) and live (round-trip artifact + cost row written) separately — doctor should fail if live diverges from dry.

**G. Brainstorm agenda:** Should doctor gate on live checks, not flag presence? Fix local's `open` exclusion or drop it from "supported"? Standardize Codex approval-policy flag now or abstract it? Is per-target CWD/state.db isolation a structural fix or patch-forever? Go/no-go: keep wrapping vendor CLI quirks vs. commit to native harness surface (per strategy doc)?

**H.** Completely supported today: NO — biggest single gap is Codex's headless flag mismatch (TC-2) plus doctor's inability to distinguish flag-presence from working dispatch.

### agy
Last completed task: Landed #648/#650 sandbox DB fallback fix.
Next task: Conduct empirical harness-specific gap analysis for full-fleet operability.

---

### A. Identity
Harness: **`agy` (v1.1.8)**. Headless contract: Non-interactive execution via `agy exec -p "<prompt>"` / stdin. Requires `GEMINI_API_KEY` or active Antigravity auth. Stdio streams used (PTY optional); permits localhost network calls.

### B. Claim 1 HOME — Grade: PARTIAL
Inside an interactive `agy` session, `synlynk` verbs execute, but the experience is incomplete: `synlynk open` excludes `local` (#338), `AGENTS.md` is missing from project instructions (#347), and interactive permission prompts occasionally stall non-interactive subshell tools.

### C. Claim 2 FUNCTION-100 — Grade: PARTIAL
Basic verbs run, but sandboxed operations break. While #648/#650 DB fallback prevents fatal crashes, per-worktree `state.db` corruption (#330) and `null-org` configs persist. `doctor` outputs false-greens by ignoring flag drift (Codex `--approval-policy` in TC-2) and missing 6 AGY SOP sections (TC-5).

### D. Claim 3 CROSS-DISPATCH (Home = `agy`)
- **`claude` (PASS):** Reliable headless execution, clean token/cost tracking, valid auth.
- **`agy` (PARTIAL):** Self-dispatch functions, but headless Stitch MCP fails (#573).
- **`codex` (FAIL):** Blocked by `--approval-policy` flag drift (TC-2), expired GH auth (#577), and package install blocks (#340).
- **`grok` (PARTIAL):** Dispatches, but CWD auto-relocation (#342) silently breaks relative paths; grants are no-ops (#338).
- **`local` (FAIL):** Fails PTY contract (`requires_pty=False`, TC-1) and endpoint connection (`127.0.0.1:8080`, TC-3).

### E. Top 5 Failure Modes
1. **Codex CLI Flag/Auth Drift (#577, TC-2):** CLI breaking changes halting headless dispatch.
2. **Sandbox DB Corruption (#330, #648):** Concurrent worktree writes corrupting SQLite `state.db`.
3. **Local Worker Infrastructure Deficit (TC-1, TC-3):** Missing PTY handling and dead local server ports.
4. **Instruction File Omission & Contamination (#347, #411):** Missing `AGENTS.md` causing worker behavior drift.
5. **Grok CWD Auto-Relocation (#342):** Silent execution out of context directory.

### F. Empirical Audit Plan
Automate a $5 \times 5$ matrix in `doctor`/`selftest` running Home $\times$ Target dispatches. Each cell must verify: (1) Return code 0, (2) Cost/token capture, (3) Git/GH side-effect execution, and (4) DB lock integrity.

### G. Brainstorm Agenda Items
1. **Wrapper vs. Native (docs/strategy/synlynk-as-a-harness.md):** Go/No-Go on replacing vendor CLI wrappers with a native direct API execution loop.
2. **Preflight Hard-Gates (#112, #332):** Should `dispatch` strictly block when a target fails `doctor` preflight?
3. **Instruction File Synchronization (#347):** Standardizing cross-harness instruction file generation.
4. **Worktree DB Isolation (#330):** Architectural redesign of multi-worktree state locks.
5. **Target Deprecation:** Should `local` be removed from the fleet until PTY/server prerequisites are met?

### H. Final Position
Completely supported today: **NO** — the biggest single gap is vendor CLI flag/auth drift coupled with brittle subprocess wrapping that compromises headless execution target reliability across the fleet.

### codex
**A. Identity — Codex home**

Codex 0.146.0 is my harness. Headless contract is `codex exec` with prompt on argv/stdin (typically JSON output for automation), approval/sandbox flags, and CLI auth; PTY is not inherently required, but network/filesystem policy and `gh` credentials are. Flag drift is real: doctor TC-2 fails on `--approval-policy`.

**B. Claim 1 HOME — PARTIAL**

Codex can invoke `synlynk open/shell/exec/status/dispatch/doctor` in-session, and `open` lists codex. It is not first-class: the allowlist omits `local`; root `AGENTS.md` is missing (while CLAUDE/GEMINI/GROK exist), so instruction reach is inconsistent (#347, #344/#351/#345). Permission prompts, PATH/install assumptions, and context injection can interrupt execution; harness-managed directive corruption (#411) further undermines continuity.

**C. Claim 2 FUNCTION-100 — FAIL**

The sandbox DB fallback (#650) reduces—but does not eliminate—failures. DB-backed verbs still encounter per-worktree corruption (#330), null-org/config paths, and sandbox filesystem/package-install restrictions (#340). Doctor can report green while dispatch preflight is unsafe (#112, #332); selftest misses instruction loading, auth, and side-effect validation. Flag drift and stale completion summaries (`UNKNOWN`, #579) make jobs/logs/cost/pr-check/story/decide non-deterministic.

**D. Claim 3 CROSS-DISPATCH (Codex home)**

- **claude: PARTIAL** — basic dispatch likely works; completion/cost/files and privileged side-effects are not proven end-to-end.
- **agy: FAIL** — headless GH-write path is explicitly broken (#426); SOP lacks six required sections (doctor TC-5).
- **codex: FAIL** — approval-policy mismatch (TC-2) and expired `gh` auth (#577) block reliable self-dispatch.
- **grok: PARTIAL** — execution works, but grants are no-op (#338), CWD may relocate (#342), and reporting is inconsistent.
- **local/aider: FAIL** — missing from `synlynk open`; TC-1 says no PTY and TC-3 cannot reach `127.0.0.1:8080`.

**E. Top pain**

1. Headless GH/auth failures (#426, #577).  
2. Sandbox DB/state divergence (#648, #330).  
3. Incorrect preflight/doctor confidence (#112, #332).  
4. Instruction contamination or omission (#347, #344/#351/#345, #411).  
5. Incomplete job/cost/file reporting (#579).

**F. Audit plan**

Run every home harness × every core verb (`status doctor dispatch jobs logs pr cost story decide`) in dry and live modes, then every home × five targets. Assert instruction-file hash, DB location/org, exact argv, auth/network probe, PTY behavior, exit code, files, cost, logs, and GH side-effect evidence.

**G. Brainstorm agenda**

Should support mean vendor-wrapper parity or native harness semantics? Is one canonical headless contract mandatory? Do we fail closed on missing auth/instructions? Should sandbox state be centralized? What side-effects require cryptographic proof? Is `local` a supported product path or experimental? Which doctor checks become blocking gates?

**H. Position**

Completely supported today: **NO** — the biggest gap is trustworthy, harness-specific headless preflight and side-effect verification.

### grok
I'll ground this panel take in your harness identity and live fleet evidence—reading capability baselines, doctor/selftest contracts, and the open-issue cluster before grading HOME / FUNCTION-100 / CROSS-DISPATCH.## Grok panel: full-fleet operability audit

### A. Identity
**Harness: grok** (CLI `grok` 0.2.118). Headless contract in `AGENT_CAPABILITY_BASELINES`: `prompt_flag=--single`, `prompt_via_arg=True`, `requires_pty=False`, dispatch allowlist includes `--always-approve` / `--output-format` / `--model` / `--single`; invalid: `--yes`, `--dangerously-skip-permissions`, `--print`. Network: `cli-chat-proxy.grok.com:443`. Auth: version probe + unauthenticated markers. `can_gh_write=True` (default GH-write target per #426/#438). Interactive session uses tool loop + shell; no PTY requirement for headless.

### B. Claim 1 HOME — **PARTIAL**
Inside this Grok session, `synlynk` is on PATH and verbs run (`doctor`, `status` worked live). Gaps:
- `synlynk open` allowlist is `claude,agy,codex,grok` — no `local`; home entry is asymmetric.
- Instruction reach is unproven (#347): `GROK.md` exists but is **template-contaminated** (TODO domains, GitHub Projects TODOs, incomplete harness SOP vs Claude.md managed block; #344/#351/#345).
- Grants are no-op for Grok (#338) — permission surface is vendor CLI (`--always-approve` / `--allow`), not synlynk-managed.
- CWD auto-relocation (#342) still a live risk when tools/spawn assume repo root.
- Status matrix still rates Grok cycle capability mostly empty / attach 0% — “home” works by shell, not as a first-class attached home.

### C. Claim 2 FUNCTION-100 — **PARTIAL**
Core CLI verbs execute, but not fully under sandbox reality:
- **DB path still fragments**: live tree has many `worktrees/job-*/.synlynk/**/state.db` copies — violates “state never branches”; #648/#650 mitigates sandbox fallback but #330-class corruption remains visible.
- Doctor **false-greens / soft-warns**: TC-5 SOP missing 6 sections on agy/codex instruction files (warning, not fail); local TC-3 hard-fail on `127.0.0.1:8080`; version drift (status: grok 0.2.106 vs CLI 0.2.118; codex 0.144.1 vs 0.146.0).
- `AGENTS.md` **missing** — codex home/instruction TC is broken at source.
- Flag drift is chronic (devlog: grok `--yes` ↔ `--always-approve` thrash).
- Selftest blind spots: no proof that instruction file was loaded; job summary UNKNOWN (#579); harness directive corruption (#411).

### D. Claim 3 CROSS-DISPATCH (Grok home → headless targets)

| Target | Grade | Notes |
|--------|-------|--------|
| **claude** | **PARTIAL** | Best peer; headless `--print` + skip-permissions works in contract; attach/score 0% here; cost capture usually OK when job finishes cleanly |
| **agy** | **PARTIAL→FAIL on side-effects** | Headless OK-ish (`-p`); `can_gh_write=False` (#426); SOP missing; Stitch MCP headless (#573); token/auth surface fragile |
| **codex** | **FAIL / PARTIAL** | Sandbox blocks package install (#340), network egress design; GH auth expired (#577); no AGENTS.md; doctor flag history flaky (#112 TC-2); not reliable for gh/git side-effects |
| **grok** | **PARTIAL** | Self-dispatch possible (`--single` + `--always-approve`); flag thrash + CWD + no grant parity; cost/completion better than local/codex when job exits 0 |
| **local** | **FAIL** | Not in `open` allowlist; doctor TC-3 8080 unreachable; `requires_pty` history FAIL on some machines; not a real fleet member in practice |

Reliable **full** matrix (complete + cost/files + authorized git/gh) is **not** true for every target. GH-write routing intentionally funnels to claude/grok; that is structural partiality, not a green fleet.

### E. Top 5 failure modes (pain-ranked)
1. **Sandbox / worktree DB split** — jobs write wrong or empty state; status/costs lie (#648 family, #330).
2. **Side-effect agents that can’t side-effect** — Agy/Codex GH-write headless (#426, #577); dispatches “succeed” without PR actions.
3. **Instruction / SOP fiction** — missing AGENTS.md, contaminated GROK.md, TC-5 warnings, no load proof (#347, #344, #411).
4. **Vendor flag/version drift** — baselines lag CLI (codex approval flags; grok `--yes` vs `--always-approve`; status version skew).
5. **Completion theater** — UNKNOWN summaries (#579), attach 0%, 182 sentinels — green CLI ≠ green operability.

### F. Empirical audit plan (minimal matrix)
**Rows:** home ∈ {claude, agy, codex, grok} (+ local if claimed).  
**Cols (verbs):** `status`, `doctor --agent X`, `dispatch X --dry`, `dispatch X trivial`, `jobs show`, `logs`, `pr check`, `cost log`, `story list`, `decide` (if present).  
**Cols (targets):** for each home, live dispatch to each fleet member with assertions: exit 0, job row complete, cost >0 or explicit zero, files changed optional, `gh auth status` if `--requires-gh-write`.  
**Tiers:** (1) dry/contract only, (2) live trivial no-network-write, (3) live git-only worktree, (4) live gh-write on can_gh_write agents only.  
Doctor must **fail** on missing instruction file, version mismatch, TC-3 required endpoint, and per-worktree state.db under repo (not only warn).

### G. Brainstorm agenda (sharp)
1. Is “full fleet” a product claim or a marketing ceiling until native harness?
2. Drop `local` from fleet until 8080 + open + TC-1 green, or invest and pin?
3. Single canonical state.db: enforce hard error on nested `.synlynk/state.db`?
4. Instruction truth: regenerate-only managed blocks vs #347 load attestation?
5. GH-write: role-scoped tokens vs “route to Grok/Claude only” forever (#426/#569)?
6. Doctor severity: promote TC-5 / version skew / missing AGENTS.md to FAIL?
7. Selftest: require one live cross-dispatch per PR or weekly only?
8. Wrapper vs native (`docs/strategy/synlynk-as-a-harness.md`): go/no-go — stop chasing parity bugs if native loop is the real fix for sandbox/grants/telemetry.
9. Capability matrix in status: empty ○’s with attach 0% — hide unproven claims?
10. What does “supported” mean: CLI present, doctor green, or weekly green matrix?

### H. Position
**Completely supported today: NO — biggest single gap is reliable shared state + side-effect-capable headless workers under vendor sandboxes, not missing verbs on the happy path.**

**Recommendation:** Treat A/B dual claim as **aspirational**. For brainstorm: freeze new “fleet parity” stories until a **live matrix gate** exists; decide wrapper-vs-native before more baseline patching. Short term: FAIL doctor on missing AGENTS.md / nested state.dbs / local-if-listed-but-dead; keep GH-write on claude/grok only and stop advertising Agy/Codex/local as full workers.

## Synthesis
## Synthesis

All four panelists — despite different harness vantage points — converge on the same shape of answer, which makes this an unusually clean panel to synthesize rather than adjudicate.

**Where they agree completely:**
- **Claim 1 (HOME):** PARTIAL everywhere. `synlynk open`'s allowlist (claude/agy/codex/grok) structurally excludes `local` even though it's a "supported" fleet member — a paper/reality mismatch every panelist independently flagged. Instruction-file reach is unproven (#347) and, per codex/grok, actively broken (`AGENTS.md` missing entirely; `GROK.md` contaminated per #344/#351/#345).
- **Claim 2 (FUNCTION-100):** no panelist gave better than PARTIAL; codex says FAIL outright. The unanimous root cause is **doctor false-greens** — "OK" reflects flag/version presence, not a verified round-trip — compounded by persistent per-worktree `state.db` fragmentation (#330) that #648/#650 mitigated but did not eliminate (grok found live `worktrees/job-*/.synlynk/state.db` copies as of this session).
- **Claim 3 (CROSS-DISPATCH):** identical ranking across all four, regardless of who's "home": **codex is the weakest headless target** (TC-2 `--approval-policy` flag drift + #577 expired gh auth + #340 sandbox install block), **local is not viable** (missing from `open`, TC-1 no PTY, TC-3 unreachable port — it's listed as supported but isn't dispatchable at all), and **agy/grok are both PARTIAL** for the same underlying reason: neither can be trusted for GH-write side-effects (#426 for agy; #338 grants no-op + #342 CWD relocation for grok corrupting file/cost attribution).
- **Position (H):** unanimous **NO** on "completely supported today." The recurring single-worst-gap theme, stated in different words by each panelist, is the same failure mode: **the system reports success (doctor green, job complete) without having verified the underlying claim** — codex calls it "trustworthy headless preflight," agy calls it "false-greens," grok calls it "completion theater" (#579 UNKNOWN summaries), claude calls it "doctor masking real dispatch failure." This is the single point every other listed issue (#330, #426, #340, #577, #342, #347) ultimately traces back to: nothing forces a *live* check.

**Where they diverge (minor):** claude rates the codex path as its worst personal pain point; grok and agy independently surface the wrapper-vs-native strategic question (docs/strategy/synlynk-as-a-harness.md) as something that should gate further patching rather than be deferred indefinitely; codex is the only one to explicitly propose failing closed on missing auth/instructions as a design principle rather than a bug list.

Decision: Full-fleet operability is **not** supported today on any of the three claims, and the panel is unanimous on why — synlynk's doctor/status/completion signals report presence and exit codes, not verified round-trips, so "green" and "complete" are currently unfalsifiable claims. Before any more fleet-parity feature stories are queued, build the minimal live audit matrix all four panelists independently converged on (5 home harnesses × core verbs, dry-vs-live, with hard assertions on instruction-file load, single state.db location, and — for dispatch cells — actual cost/file/git-gh side-effect evidence, not just exit 0), and make doctor FAIL (not warn) on missing `AGENTS.md`, nested `state.db`, and TC-2/TC-3 hard failures. Concurrently, stop advertising `local` as a supported fleet member until it clears `open` allowlist inclusion and TC-1/TC-3, and keep GH-write routed only to claude/grok until #426 is closed rather than treating agy/codex as GH-write-capable in docs. The wrapper-vs-native strategic question is real but is a separate go/no-go — it should be decided only after the live-matrix data exists to inform it, not before. This is the brainstorm agenda: gate-the-matrix first, decide-the-fleet-list second, wrapper-vs-native third.

## Decision
Decision: Full-fleet operability is **not** supported today on any of the three claims, and the panel is unanimous on why — synlynk's doctor/status/completion signals report presence and exit codes, not verified round-trips, so "green" and "complete" are currently unfalsifiable claims. Before any more fleet-parity feature stories are queued, build the minimal live audit matrix all four panelists independently converged on (5 home harnesses × core verbs, dry-vs-live, with hard assertions on instruction-file load, single state.db location, and — for dispatch cells — actual cost/file/git-gh side-effect evidence, not just exit 0), and make doctor FAIL (not warn) on missing `AGENTS.md`, nested `state.db`, and TC-2/TC-3 hard failures. Concurrently, stop advertising `local` as a supported fleet member until it clears `open` allowlist inclusion and TC-1/TC-3, and keep GH-write routed only to claude/grok until #426 is closed rather than treating agy/codex as GH-write-capable in docs. The wrapper-vs-native strategic question is real but is a separate go/no-go — it should be decided only after the live-matrix data exists to inform it, not before. This is the brainstorm agenda: gate-the-matrix first, decide-the-fleet-list second, wrapper-vs-native third.

> Signatures: see 2026-08-02-fleet-operability-deep-survey.json
