<!-- generated - source of truth is state.db -->
---
decision_id: dec-53a2730a
topic: "Synlynk V2 Architecture: Vizor Generalization, Living GOVERNS Substrate, Autonomous Graphify, and 10-Step Flight Academy.
Key proposals:
1. URL Namespacing: /w/<slug>/... with relative api/... paths; explicit (repo_path, db_path) in all handlers to eliminate daemon CWD coupling and prepare for Team/Enterprise.
2. Living GOVERNS: Dynamic goal resolution against target workspace's own goals table; auto-stage advancement (done -> sustain); fuzzy/issue# roadmap phase matching in Gantt.
3. Repo-Truth Views: Purge hardcoded synlynk fallbacks from Product, Infra, Logical, World; auto-discover local mocks (.superpowers/brainstorm/), TS/JS routes, and real infra manifests.
4. Autonomous Graphify: Daemon background AST extraction on workspace poll; native glassmorphic HUD instead of 404 iframe.
5. 10-Step Flight Academy: Dual-surface onboarding (TUI + Vizor /onboarding) from orientation to live Step-10 Golden Path execution.
Please provide your review, critique, and recommended sub-project sequencing."
date: 2026-09-30
panel: [claude, codex, grok]
status: approved
---

## Topic
Synlynk V2 Architecture: Vizor Generalization, Living GOVERNS Substrate, Autonomous Graphify, and 10-Step Flight Academy.
Key proposals:
1. URL Namespacing: /w/<slug>/... with relative api/... paths; explicit (repo_path, db_path) in all handlers to eliminate daemon CWD coupling and prepare for Team/Enterprise.
2. Living GOVERNS: Dynamic goal resolution against target workspace's own goals table; auto-stage advancement (done -> sustain); fuzzy/issue# roadmap phase matching in Gantt.
3. Repo-Truth Views: Purge hardcoded synlynk fallbacks from Product, Infra, Logical, World; auto-discover local mocks (.superpowers/brainstorm/), TS/JS routes, and real infra manifests.
4. Autonomous Graphify: Daemon background AST extraction on workspace poll; native glassmorphic HUD instead of 404 iframe.
5. 10-Step Flight Academy: Dual-surface onboarding (TUI + Vizor /onboarding) from orientation to live Step-10 Golden Path execution.
Please provide your review, critique, and recommended sub-project sequencing.

## Panel Inputs

### claude
[model=sonnet; version=2.1.284 (Claude Code)]

## Review

**Overall:** The five proposals are really five independent sub-projects, not one architecture. Under the brainstorm-first policy each needs its own spec. Bundling them into one "V2" spec would hide the dependency order.

**1. URL namespacing plus explicit (repo_path, db_path): the foundation, do it first.**
- It fixes the daemon CWD-coupling class of bugs (#1228, #1881) at the root.
- Risks:
  - Slug collisions and slug stability when a repo is renamed or moved.
  - Old bookmarked routes need a redirect shim.
  - The trust boundary is unstated: `db_path` arriving from a request is a path-traversal hole. Handlers should resolve a slug through a server-side registry and never accept raw paths.

**2. Living GOVERNS: good, but it depends on #1.**
- Resolving goals against the target workspace's own goals table only works once the handler knows which workspace it is serving.
- Auto-advancing `done → sustain` is a state mutation triggered by reads. Make it an explicit, audited transition rather than a side effect of rendering.
- Fuzzy phase matching in the Gantt is a correctness risk. Prefer exact issue# matching, and show a visible "unmatched" state instead of guessing.

**3. Repo-truth views: sequence right after #1.**
- Purging hardcoded synlynk fallbacks is mostly deletion plus empty states, so it is cheap and de-risks Team/Enterprise.
- Auto-discovery of TS/JS routes and infra manifests is open-ended. Cap it to a defined set of detectors, and ship each one with a fixture repo.

**4. Autonomous graphify: highest operational risk, so defer and gate it.**
- Background AST extraction on every poll collides with known pain: the 7.1GB state shard growth (#1831) and the nested-writer deadlock class (LIVE-17).
- Require it to be opt-in, hash-gated (re-extract only on changed files), throttled, and written outside the hot state.db path.
- The native HUD replacing the 404 iframe can ship earlier and independently as a small win.

**5. Flight Academy: last.**
- It depends on stable surfaces from #1 to #3, and ten steps plus dual surfaces is a large scope.
- Ship the TUI path first, since it has the fewest dependencies. Add Vizor `/onboarding` afterward, driven by the same step definitions so the two surfaces can't drift.
- Per the agent-design principles, it must be opt-in and have measurable ROI, for example time to first successful dispatch.

## Recommended sequence

1. Namespacing and explicit paths, with a registry lookup and redirect shim.
2. Repo-truth purge, alongside the native graph HUD shell.
3. Living GOVERNS.
4. Autonomous graphify, opt-in and throttled.
5. Flight Academy: TUI first, then Vizor.

## Position

I recommend proceeding, but as five separately specced sub-projects in the order above, with #1 as a hard prerequisite for the rest. Two changes to the proposals: resolve workspaces by slug through a server-side registry (never accept a raw `db_path`), and make graphify opt-in and throttled until the state.db growth and write-contention issues are closed. Don't start #4 or #5 until #1 to #3 are merged and verified against a second, non-synlynk workspace. That verification is the real test of whether the generalization worked.

### codex
[model=default; version=codex-cli 0.155.1]

The proposals are directionally strong, but they should be treated as a dependency graph rather than five parallel initiatives.

URL namespacing and explicit `(repo_path, db_path)` propagation are foundational. They remove hidden daemon-CWD assumptions, enable multi-workspace correctness, and provide the contract that every later feature depends on. This work should include request-context validation, path traversal protection, migration compatibility, and tests proving two workspaces can be served concurrently.

Living GOVERNS is the next priority because it establishes the system’s source-of-truth model. Dynamic goal resolution should be strict by default: fuzzy matching may suggest candidates, but must not silently mutate roadmap state. Auto-advancing `done -> sustain` needs an auditable event trail, idempotency, and explicit handling for reopened or abandoned goals. Gantt matching should expose confidence and ambiguity rather than conceal it.

Repo-Truth Views should follow the context model. Removing hardcoded fallbacks is valuable, but auto-discovery across mocks, routes, and infrastructure manifests risks inconsistent semantics and accidental exposure of irrelevant files. Define an allowlisted discovery protocol, precedence rules, schema normalization, and a “truth unavailable” state instead of fabricating data.

Autonomous Graphify should come after repository truth and workspace polling are reliable. AST extraction is resource-intensive and language/toolchain-sensitive; it needs incremental hashing, cancellation, bounded concurrency, observability, and graceful degradation. The HUD should be a deliberate product surface, not merely a replacement for an iframe error.

The Flight Academy should be last—or developed as a thin consumer-driven vertical slice once the contracts stabilize. Its Step 10 should execute a safe, idempotent Golden Path in a disposable or explicitly selected workspace, with checkpoints and recovery. TUI and Vizor must share the same underlying workflow engine to avoid divergent onboarding behavior.

My recommendation is: **(1) URL/context contract, (2) GOVERNS resolution and lifecycle, (3) Repo-Truth discovery, (4) Graphify pipeline and HUD, (5) Flight Academy hardening and rollout.** I support the overall architecture, contingent on explicit trust boundaries, auditability, and a staged vertical slice proving one workspace end-to-end before broad generalization.

### grok
[model=default; version=grok 1.0.41 (4220f3b224a6) [stable]]

I'll ground the panel review in the current Vizor, GOVERNS, and onboarding design so the sequencing recommendation matches how the repo actually works.Approve the direction. Do not ship it as one V2 program. The five proposals have different blast radii, and two of them write state or load the daemon. Those wait until a workspace can be addressed and rendered without synlynk's own repo as the implicit subject.

**1. URL namespacing is the keystone.** `workspace_render_context` in `synlynk/vizor_daemon.py` still `chdir`s into `repo_path` because viz generation and the cache writer are cwd-coupled. Team and Enterprise cannot exist on that. Put `/w/<slug>/...` in front, keep relative `api/...` under that prefix, and thread an explicit `(repo_path, db_path)` from the workspace registry into every handler. Resolve paths on the server from the slug. Never accept a client-supplied filesystem path. This is the only change the others can safely build on.

**2. Living GOVERNS should be read-only first.** Resolving goals from the target workspace's own goals table is the right model: GOVERNS is the lifecycle and attention layer, and SQLite already owns goal meaning. Auto-advancing `done` to `sustain`, and fuzzy or issue-number phase matching that writes the Gantt, will mis-file work. The August strategy notes already separate issue close, story done, and goal complete. Fuzzy match may annotate. It must not mutate stage or phase without a confidence floor and a human confirm.

**3. Repo-truth views are next, still read-only.** Hardcoded synlynk fallbacks in Product, Infra, Logical, and World make every other workspace look like this repo. Purge them only after the slug context exists, or discovery runs against the wrong tree. Local mocks, TS and JS routes, and infra manifests are useful, but the scanner has to ignore `node_modules`, vendored trees, and fixtures. A wrong manifest on the Infra view is worse than an empty one.

**4. Autonomous graphify is last among the machinery.** A native glass HUD that replaces the 404 iframe is a small UX fix and can land early. Daemon-side AST extraction on every workspace poll is not. Poll-time parsing will stall the daemon, and a green poll is not evidence the graph is true. Keep extraction opt-in, bounded, and off the request path. The September graphify spike and the SCIP research already point at a job, not a poll hook.

**5. The flight academy teaches whatever the product actually is.** Dual-surface onboarding (TUI plus Vizor `/onboarding`) is the right adoption shape, but Steps 8–10, the live Golden Path, will rehearse synlynk fallbacks if they ship before namespacing and repo-truth. Orientation through a first truthful view can start earlier. Live execution waits.

**Sequence:** (1) slug routing and explicit `(repo_path, db_path)`, (2) purge hardcoded fallbacks with read-only discovery, (3) GOVERNS goal resolution with no auto-advance, (4) academy Steps 1–7 on that surface plus the native HUD shell, (5) gated stage advancement, (6) bounded graphify, (7) academy Steps 8–10.

**Position:** V2 is "Vizor tells the truth about a workspace that is not synlynk." Ship identity and read-only truth before any autonomous write. Hold auto-stage and poll-time graphify until a second repo renders correctly without a daemon `chdir`.

## Synthesis
The three reviewers agree on direction and order. The main disagreement is when the write-heavy pieces (stage advancement, graphify) and the live Golden Path should land.

**Where the panel agrees**
- **Five specs, not one:** these are five independent sub-projects, and the brainstorm-first policy means each needs its own spec.
- **Namespacing first:** slug routing is the keystone, and the server resolves the slug to `(repo_path, db_path)` through a registry. A client-supplied `db_path` is a path-traversal hole.
- **Read-only before writes:** the repo-truth purge and goal resolution come first. Views should show "truth unavailable" instead of guessing or falling back to synlynk's own data.
- **No fuzzy writes:** fuzzy phase matching may only annotate. It must never change the roadmap or a goal's stage.
- **Auditable advancement:** `done → sustain` must be an explicit, audited, idempotent transition. It must not be a side effect of a page render.
- **Graphify is opt-in:** it needs hash gating, throttling and bounded concurrency, and it runs off the request path and off the hot `state.db` (#1831, LIVE-17). The native HUD replacing the 404 iframe can ship early and independently.
- **One Academy engine:** the TUI and Vizor `/onboarding` share one step-definition engine so they can't drift.

**Where they differ**
- **Order of GOVERNS and repo-truth:** Codex puts GOVERNS second and Repo-Truth third. Claude and Grok put Repo-Truth second and GOVERNS third. I side with Claude and Grok: the purge is mostly deletion, it cuts the Team/Enterprise risk cheaply, and GOVERNS is more useful once views stop defaulting to synlynk data.
- **When the Academy starts:** Grok splits it, with Steps 1–7 after GOVERNS and Steps 8–10 after graphify. I adopt that split, because Step 10 (the live Golden Path) would otherwise rehearse synlynk fallbacks.
- **Gate on stage advancement:** only Grok sequences it as its own gated step. I adopt that, since it is the first autonomous write.

**Sequence**
1. Slug routing and the explicit `(repo_path, db_path)` contract, with a registry lookup, a redirect shim for old routes, and a test that two workspaces are served concurrently.
2. Repo-truth purge with allowlisted, fixture-tested discovery, plus the native graph HUD shell.
3. Living GOVERNS goal resolution, read-only, with exact issue# matching.
4. Academy Steps 1–7, TUI first and then Vizor.
5. Gated, audited stage advancement with human confirm.
6. Opt-in, throttled graphify.
7. Academy Steps 8–10.

The gate: steps 1–3 must render correctly on a second, non-synlynk workspace before steps 5–7 start.

I tried to append this to `project-docs/devlogs/nikhilsoman.md` as your checkpoint protocol requires. The shell write needed approval and didn't go through, so it isn't in the devlog yet. Say the word and I'll write it another way.

Decision: Approve the V2 direction as five separately specced sub-projects in this order: slug routing with a server-side registry, repo-truth purge with the native HUD shell, read-only GOVERNS resolution, Academy Steps 1–7, gated and audited stage advancement, opt-in throttled graphify, then Academy Steps 8–10. No autonomous write or daemon-load feature starts until the first three are verified on a second, non-synlynk workspace, and no client request ever supplies a filesystem path.

## Decision
Decision: Approve the V2 direction as five separately specced sub-projects in this order: slug routing with a server-side registry, repo-truth purge with the native HUD shell, read-only GOVERNS resolution, Academy Steps 1–7, gated and audited stage advancement, opt-in throttled graphify, then Academy Steps 8–10. No autonomous write or daemon-load feature starts until the first three are verified on a second, non-synlynk workspace, and no client request ever supplies a filesystem path.

> Signatures: see 2026-09-30-synlynk-v2-architecture-vizor-generaliza.json
