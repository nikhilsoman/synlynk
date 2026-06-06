# Bootstrapping RxCC with the Synlynk Polyglot Agent Protocol

**Date:** 2026-06-01
**Author:** Gemini (Data & Frontend Domain)
**Status:** Proposed

## Context and Timing

Based on the current state of **RxCC.me**, this is a **high-leverage inflection point** to bootstrap with the **Synlynk Polyglot Agent Protocol**.

The project has transitioned from "Foundations" to "Active Maintenance & Scaling." We have a stable multi-agent environment (Claude, Gemini, Codex) and are facing the limitations of sequential, turn-based CLI interactions. Bootstrapping now…specifically to bridge the gap toward the **Antigravity CLI** (`agy`) release on June 18, 2026…will turn the agentic workforce into a true force multiplier.

### Why now? (lifecycle context)

1. **Domain Divergence:** The project now has distinct "Intelligence" vs "UI" tracks. Claude is managing the `ClinicalNote` extraction logic (DI-7), while Gemini is handling the Arctic Precision UI (us-ui3). Synlynk would allow these two to collaborate asynchronously on a shared "Verification Queue" without human bottlenecking.
2. **Operational Complexity:** We've reached a state where infrastructure drift (ENGOPS-2) and CI/CD hardening (ENGOPS-1) are becoming the "taxes" on development speed. A polyglot protocol allows specialized "EngOps" agents to run background observability tasks while product agents focus on features.
3. **Antigravity Readiness:** Moving to Synlynk now ensures that when we transition to `agy`, the "Agent Graph" is already structured for the multi-agent orchestration that Antigravity provides.

---

## Essential Behavioral Modifiers for Synlynk
.₡ To make this transition a force multiplier, the Synlynk implementation should include these specific modifiers to agent behaviors:

### 1. The "Spec-First" Synchronizer (Modifier: `PROTOCOL_LOCK`)
* **Behavior:** Agents must not start implementation on `domain:frontend` (Gemini) or `domain:backend` (Claude) until a shared `spec.md` exists in `project-docs/`.
* **Force Multiplier:** Prevents the "hallucination mismatch" where the backend agent assumes a different FHIR structure than the frontend agent expects.
* **Actionable Rule:** `IF task touches cross-domain boundaries THEN REQUIRE SYNLYNK_SPEC_VERIFICATION`.

### 2. The "Cross-Domain" Evaluator (Modifier: `DOMAIN_BRIDGE`)
* **Behavior:** When Claude (Backend) finishes a route, it should automatically trigger a "Shadow Review" from Gemini (Frontend) to evaluate the API's usability for the Next.js client.
* **Force Multiplier:** Eliminates the "Integration Tax"—the 2-3 turns usually wasted fixing CORS, hydration mismatches, or missing Zod schemas.

### 3. "YOLO-Guard" Sandboxing (Modifier: `SAFE_EXECUTION_CONTEXT`)
* **Behavior:** As we move toward Antigravity's "YOLO Mode," Synlynk should enforce a "Pre-Commit Validation" behavior where agents *must* run the local Vitest suite before asking for a merge.
* **Force Multiplier:** Moves the "Validation" phase from the human's brain to the agent's background process. The human only sees the "Green" report.

### 4. The "Cost-Aware" Researcher (Modifier: `TOKEN_BUDGETING`)
* **Behavior:** Agents should be modified to use **Flash models** (Gemini 1.5 Flash / Claude Haiku) for high-volume research (e.g., scanning 51k LOINC codes) and only "promote" the final reasoning to **Pro/Sonnet models**.
* **Force Multiplier:** Dramatically reduces the `rxcc_costs.md` run rate, allowing for more aggressive parallelization within the same budget.

### 5. "Antigravity-Ready" Identity (Modifier: `UNIFIED_ATTRIBUTION`)
* **Behavior:** Standardize the `Co-Authored-By` and `git config` patterns across all agents to use the `agy` 0naming convention immediately.
* **Force Multiplier:** Ensures a seamless git history transition when the "Agent Harness" switches in mid-June.

## Recommended Next Steps

Update `GEMINI.md` and `CLAUDE.md` today with a **"Synlynk Initialization"** block that defines these modifiers. This prepares the ground for the Antigravity CLI and ensures agents start "talking" to each other via documentation before they start talking to each other via the `agy` orchestrator.
