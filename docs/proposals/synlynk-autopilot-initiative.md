# Synlynk Autopilot — Strategic Initiative

**Status:** 🧠 Brainstorm pending  
**Goal:** Put synlynk's own growth, content, and quality assurance on autonomous agents — using synlynk itself as the substrate. Dogfood the platform at the product level.

---

## The Three Agents

### 1. PM Agent — Growth
Owns the growth loop. Monitors metrics, identifies friction points in the funnel, proposes roadmap adjustments, drafts issues, tracks initiative health.

Questions for brainstorm:
- What data sources does it consume? (GitHub stars, install counts, usage telemetry, Tokq signups)
- What decisions can it make autonomously vs. escalate?
- What does "growth" mean at this stage — installs? Contributors? Enterprise pilots?
- How does it interact with the human roadmap decisions?

### 2. Marketing Intern Agent — Blogs + Publishing
Writes and publishes content. Sources from: PRs merged, design sessions, feature launches, community questions. Posts to public platforms.

Questions for brainstorm:
- Which platforms? (dev.to, Hashnode, LinkedIn, X, Hacker News)
- What level of human review before publish?
- How does it draw from existing docs (docs/blog/, specs, proposals)?
- What's the publishing cadence and content mix?
- Does it monitor what content performs and adjust?

### 3. Support Engineer Agent — Regression Scanning
Continuously runs the test suite, monitors for regressions, files issues when something breaks, bisects failures to the offending commit.

Questions for brainstorm:
- Trigger: cron (every N hours) vs. on every push vs. both?
- Scope: unit tests only, E2E suite, or extended integration tests?
- What does the agent do when it finds a regression — file a GitHub issue? Write a sentinel alert? Page Nikhil?
- How does it handle flaky tests vs. real regressions?
- Does it attempt a fix, or only report?

---

## Infrastructure Requirements

This initiative assumes synlynk as the substrate. Key primitives needed before these agents can run autonomously:

| Primitive | Available In |
|---|---|
| `synlynk exec` with budget + health gates | ✅ v0.3.1 |
| Trio Protocol — Architect/Build/Verify pipeline | v0.4.0 |
| Agent identity + dispatch | v0.5.0 |
| Entitlements + sandboxing | v0.6.0 |
| `synlynk dispatch` + daemon | v0.7.0 |
| Human approval bridge (email) | v0.7.0 |
| MCP server (agent→platform integration) | v0.8.0 |

The Support Engineer agent is the earliest viable — it only needs `synlynk exec` + cron + sentinel alerts, available now.  
The Marketing Intern needs MCP server integration (platform APIs) — realistic at v0.8.0.  
The PM Agent needs full dispatch + entitlements + the state.db PM hierarchy — realistic at v0.6.0+.

---

## Open Questions for Brainstorm

1. **Ownership model** — does each agent own a story/epic in state.db, or do they operate outside the PM hierarchy and just report in?
2. **Human-in-the-loop thresholds** — what actions always require approval (publish, file issue, merge PR), what can be auto-dispatched?
3. **Agent personas** — do these agents have distinct identities (Ed25519 keypairs, roles) in the identity system, or are they capability profiles?
4. **Feedback loops** — does the PM Agent direct the Marketing Intern based on what content performs? How do agents collaborate?
5. **Cold start** — what does each agent need to bootstrap on a fresh synlynk install vs. what's seeded centrally?

---

## Brainstorm Session Notes

_(to be filled during the brainstorm session)_
