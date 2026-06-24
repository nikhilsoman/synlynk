# Hybrid Human:Agent Workgroup Observatory (RxCC)

As-of analysis date: May 28, 2026

## Abstract
RxCC is operating a high-discipline, GitHub-native human:agent workflow with explicit routing, heavy documentation, and strong operational memory. The system is already mature enough to serve as a Synlynk product observatory, but it has clear stress points: instruction drift, single-reviewer bottlenecks, and deployment-safety gaps.

## Evidence Base
I analyzed repo artifacts and process controls, including:

- Agent instructions and routing: `CLAUDE.md`, `GEMINI.md`, `.github/workflows/domain-route.yml`
- Board and lifecycle automation: `.github/workflows/issue-autotrack.yml`, `.github/workflows/pr-status.yml`, `.github/workflows/agent-label.yml`, `.github/workflows/issue-label.yml`
- Documentation/memory system: `docs/proposals/DOCUMENTATION_FRAMEWORK.md`, `devlog.md`, `rxcc_memory.md`, `rxcc_costs.md`, `todo.md`
- Governance and deployment posture: `.github/CODEOWNERS`, `.github/workflows/deploy-api.yml`, `.github/workflows/infra-preview.yml`, `docs/proposals/2026-05-28-canary-deployment-strategy.md`
- Team self-assessment artifacts: `docs/synlynk-agent-workers-assessment.md`, `docs/synlynk-agent-perf.md`, `docs/synlynk-agent-workers-git-managed.md`

Quantitative snapshot from GitHub PR metadata (queried on May 28, 2026):

- 70 merged PRs
- 1 GitHub author identity (`nikhilsoman`) with agent attribution via labels/branch conventions
- Agent-labeled merged PRs: Gemini 15, Claude 3, Codex 1, Human 37, unlabeled 14
- Branch-prefix compliance for labeled agent PRs: 0 mismatches
- Mean merge latency (hours): Human 2.0, Gemini 5.2, Claude 5.9, Codex 61.4 (Codex n=1)

## Inferred SOP (Observed)
1. GitHub is the control plane for issues, routing, PR state, and attribution.
2. Domain-to-agent routing is explicit (`frontend/data` -> Gemini, `testing` -> Codex, backend/infra/design/mobile -> Claude) via docs + automation.
3. All work is mediated through one human account, with agent identity represented by labels/comments/branch prefixes.
4. Memory is multi-layered: tactical log (`devlog`), strategic memory (`rxcc_memory`), cost ledger (`rxcc_costs`), manual dependency ledger (`todo`).
5. Human remains merge/deploy authority, but with partial automation and uneven hard gates.

## Deep Review

### 1) Repo and docs organization
Strengths:

- Clear monorepo segmentation (`apps/`, `packages/`, `infra/`, `docs/`).
- Strong PM-operational artifact coverage, including policy docs and incident proposals.
- Archived roadmap with migration to Issues/Programme Board is explicitly documented.

Weaknesses:

- Instruction drift exists: `CLAUDE.md` still mandates active roadmap updates while roadmap is archived.
- Documentation volume is high; cognitive retrieval cost will grow without indexing/compaction.

### 2) Agent memory management
Strengths:

- Well-defined roles for each memory artifact.
- `rxcc_memory.md` format is decision-centric (`What happened` / `Key decisions` / `Outcome`) and useful for continuity.
- Cost visibility exists and is tied to session IDs.

Weaknesses:

- Heavy manual updates create consistency risk; this already surfaced in review loops.
- Cost metrics are often estimated, reducing decision confidence for fine-grained optimization.

### 3) Agent instructions and governance
Strengths:

- High specificity for workflow and domain boundaries.
- Lifecycle automations are substantial and coherent (issue intake, routing, board sync, PR status).

Weaknesses:

- No dedicated repo-local Codex instruction file equivalent to CLAUDE/GEMINI (observed gap).
- Some controls are advisory on current plan; CODEOWNERS enforcement is explicitly noted as limited under Free.

### 4) Human and agent behavior
Human behavior:

- Operates as orchestrator/reviewer/releaser.
- Uses explicit embargo and risk gating during sensitive windows (captured in memory history).
- Maintains strong meta-governance (SOP audits, automation gap fixes).

Agent behavior:

- Gemini shows high throughput for frontend execution with moderate review-correction overhead.
- Codex is currently under-sampled (1 merged PR), but aligned to testing domain routing.
- Claude is dominant in infra/ops/spec and governance authoring.

Systemic behavior:

- Single-account authorship + synthetic attribution is practical, but reduces independence of quality signals (same identity can author/review/merge).

### 5) Competencies and contribution profile

- Gemini: strongest observed in UI delivery cadence and bounded frontend tasks.
- Claude: strongest in architecture, infra, incident response, and process design.
- Codex: positioned as testing specialist; current evidence is too small for robust performance inference.

## Extrapolated Outcomes

### Likely positive outcomes
1. High short-cycle execution velocity on scoped issues due to routing + automation.
2. Strong institutional memory continuity due to explicit logging and decision capture.
3. Good reproducibility for incident/postmortem narratives and cross-session handoffs.

### Likely adverse outcomes (if unchanged)
1. Control-plane fragility under single reviewer load: throughput and quality gates bottleneck on one person.
2. Policy drift recurrence: multiple instruction sources will diverge without automated consistency checks.
3. Deployment regressions: current deploy-on-merge model still relies on procedural discipline; prior drift incident confirms this risk class.
4. Attribution ambiguity: label-based agent identity is useful operationally but weak for audit-grade provenance.
5. Security hygiene risk: local agent permission config includes high-sensitivity command allowances and embedded credential patterns in-repo.

Reasoning basis:

- Repeated heuristics in this repo indicate failures occur at handoff boundaries (config drift, scope drift, doc drift), not pure coding inability.
- Current trend shows strong fix-after-review loops, so quality is review-coupled rather than fully pre-validated.

## Codex CLI Position in this Hybrid Environment
Codex should be positioned as the verification and guardrail operator, not general owner of infra or ambiguous architecture decisions.

Primary role:

1. Test architecture implementation (integration/e2e/regression harnesses).
2. PR comment closure loop executor (check comments, patch, respond, wait).
3. Deterministic policy conformance checks (workflow scope filters, migration notes, test-plan completeness).
4. Safety net for cross-agent regressions via targeted audits.

## Specific measures to improve certainty

1. Create `CODEX.md` with explicit scope:
   - Own `domain:testing` and QA automation.
   - Mandatory PR-comment sweep and resolution protocol.
   - Hard no-infra-deploy-changes boundary without explicit escalation.

2. Add machine-enforced SOP checks:
   - CI job that fails if PR template sections are blank (`Closes #`, test plan, migration notes).
   - CI check for workflow triggers requiring `paths` filters on expensive jobs.
   - CI drift check for instruction contradictions (archived docs still referenced as active).

3. Strengthen deployment gating:
   - Promote current proposal into implementation path: `docs/proposals/2026-05-28-canary-deployment-strategy.md`.
   - Require human approval gate for deploy workflows (GitHub Environments when plan permits).
   - Keep `infra-preview` mandatory and blocking.

4. Improve provenance architecture:
   - Preserve label-based attribution, but add signed, structured PR metadata (agent name, model, run ID, task packet ID) in PR body.
   - Track review actor distinct from author actor in Synlynk metrics to avoid self-review inflation.

5. Standardize communication channels:
   - Issue thread: scope/acceptance/priority.
   - PR thread: implementation + review closure.
   - `rxcc_memory.md`: only major decisions and incident outcomes.
   - `devlog.md`: session narrative only, no duplication of decision rationale already in memory.

6. Introduce task packets:
   - Each agent task starts with: objective, non-goals, acceptance tests, touched paths, risk tier, rollback notes.
   - Codex validates packet completeness before starting.

## Implications for Synlynk Product Decisions
RxCC is a strong observatory for Synlynk because it exhibits real hybrid patterns: routing automation, label-based provenance, memory-heavy workflows, and live deploy risk. Synlynk should productize:

1. SOP compliance diffing across instruction files and artifacts.
2. Review-loop analytics separating authoring velocity from review-dependent quality.
3. Incident-to-policy feedback automation (RCA creates enforceable controls).
4. Agent capability routing engine using empirical repo-local performance, not static defaults.
5. Deterministic handoff protocols that make multi-agent collaboration auditable and less reviewer-dependent.
