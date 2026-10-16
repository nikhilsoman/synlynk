# Managed Execution Nodes and Swarms: Discovery Decision Design

**Status:** Draft for Nikhil's review; not an implementation approval

**Date:** 2026-10-07

**GOVERNS goal:** `goal-256d17d6`

**Tracking issue:** [#2108](https://github.com/nikhilsoman/synlynk/issues/2108)

## Decision to make

Decide whether Synlynk should operate hosted execution nodes or swarms for users, should support customer-operated remote nodes only, should partner for compute, or should keep managed execution out of scope.

The question is whether Synlynk itself should receive customer source code and execute tasks in infrastructure it operates. This is a larger trust commitment than remote access to a user's machine, a team-owned sync server, or a hosted read model.

This spec frames the discovery and decision. It does not authorize implementation, a hosted service, a pricing commitment, or a change to the local-first product promise.

## Context and evidence reviewed

The initial review used the repository's existing decisions and designs, not the 2026-10-07 handoff alone:

- `project-docs/decisions/2026-09-27-round-3-roadmap-and-tokq-articulation.md` keeps Horizon 1 host-local and sets explicit adoption gates. G2 allows optional team sync only when the team runs the replica. G3 is a mid-2027 company decision; even a hosted read model operated by someone other than the customer requires a positive company outcome. G3 also requires measured adoption, at least five design partners, verified success, and support-load evidence.
- `project-docs/decisions/2026-09-20-cloudflare-tunnel-as-a-full-duplex-remote.md` distinguishes direct access to a user's live workspace from a shared relay. A tunnel is opt-in reachability, not a replacement for the relay, a hosted compute service, or an identity system.
- `docs/superpowers/specs/2026-09-02-ephemeral-swarm-cloud-runners-design.md` and issue #1326 explore remote runner and swarm mechanics. They do not establish customer demand for Synlynk-operated compute or settle its trust model.
- The 2026-10-02 Tokq panel explored peer-to-peer compute, while the later 2026-09-27 roadmap decision defers the marketplace question until G3. The earlier speculative opportunity does not override the later adoption gate.
- `docs/reviews/2026-10-05-three-lens-strategic-review.md` recommends promoting the relay and Cloudflare Tunnel work toward a managed service. That recommendation concerns relay/access and does not itself authorize Synlynk-operated execution.

The reviewed material establishes strategic constraints and prior architecture exploration. It does not provide direct customer evidence that users want Synlynk to host their source code or run their jobs.

## User problem to validate

The discovery must establish whether a real user segment needs Synlynk to operate compute, or whether its problem is already addressed by one of these lower-custody options:

1. Run dispatch locally on the user's machine.
2. Coordinate worker nodes that the customer owns and operates.
3. Provide remote access to a customer-owned workspace through an opt-in tunnel.
4. Provide a relay or shared read/control plane while execution remains customer-owned.
5. Partner with an existing execution provider without Synlynk taking custody of source or credentials.

The primary question for user interviews is: **What task is impossible or materially more expensive with customer-owned workers that justifies transferring code execution custody to Synlynk?**

No customer persona, pricing model, adoption assumption, or minimum interview count is fixed by this draft. The brainstorm must use actual user/design-partner evidence to choose an evidence bar.

## Options to compare

### A. Customer-operated nodes

Synlynk coordinates work on nodes selected and controlled by the customer. The customer retains control of infrastructure, credentials, network policy, and data lifecycle. This can support remote work without making Synlynk the compute operator.

### B. Synlynk-operated hosted execution

Synlynk provisions and operates worker infrastructure. Customer source, build/test artifacts, and possibly provider credentials enter a Synlynk-operated execution boundary. This creates a new security, privacy, availability, abuse, support, and billing surface.

### C. Third-party or peer-to-peer compute

Independent operators provide capacity. This introduces operator trust, workload isolation, code confidentiality, artifact integrity, provenance, settlement, dispute, and abuse questions beyond ordinary hosted execution.

### D. No managed compute product

Keep execution host-local or customer-operated. Continue improving local setup, customer-owned remote access, and team coordination without creating an operated compute service.

## Evaluation criteria

The brainstorm should compare each option against:

- **User evidence:** observed unmet need, buyer, frequency, willingness to adopt, and alternatives already available.
- **Trust boundary:** who can read source, secrets, prompts, logs, artifacts, and model-provider responses.
- **Isolation and security:** tenant separation, sandboxing, network egress, credential delivery, supply chain, provenance, teardown, deletion evidence, and incident response.
- **Sovereignty:** offline operation, customer control, self-hosting, air-gap compatibility, and whether the local core remains useful without Synlynk-operated services.
- **Operational burden:** uptime, queueing, capacity, support, abuse response, incident handling, and service ownership.
- **Economics:** infrastructure cost, utilization, variable model spend, metering, billing disputes, and who bears failed or runaway jobs.
- **Strategic gates:** consistency with the G1/G2/G3 adoption conditions and the existing decision to defer hosted services until the company gate.
- **Exit and portability:** moving workspaces, policies, job history, and artifacts away from any hosted or partner service.

## Initial recommendation for discovery

Do not start a Synlynk-operated compute build. First validate the need and compare customer-operated nodes, customer-owned remote access, and a relay/control plane against it. Treat managed execution as deferred until the existing G3 gate is met or Nikhil explicitly reopens that strategic decision with new evidence.

If users demonstrate a strong unmet need before G3, the next step is a separate threat-model and business decision, not an implementation shortcut. Any future spec must explicitly preserve an offline/local path and state who controls source, credentials, network egress, job artifacts, and deletion.

This recommendation is provisional. The brainstorm must be revisited with actual design-partner evidence and may conclude defer, partner, customer-operated nodes, or proceed to a new design.

## Scope of the brainstorm

The brainstorm will:

1. Review the evidence listed above and any newer adoption/design-partner data.
2. Identify user groups and interview questions that distinguish demand for hosted compute from demand for customer-owned remote nodes or a hosted relay.
3. Compare options A–D against the evaluation criteria.
4. Make an explicit proceed/defer/partner recommendation and state the evidence that would reopen it.
5. Record the decision in the issue and GOVERNS story.

The brainstorm will not:

- Design a production multi-tenant compute architecture.
- Select a cloud provider, billing system, or pricing tier.
- Authorize collection or transfer of customer code or credentials.
- Start implementation or alter existing local dispatch behavior.
- Treat #1326, the Cloudflare Tunnel decision, or this handoff as an approved product specification.

## Approval and follow-on gates

- This document is a draft. It becomes an approved spec only after it is committed to its task branch and Nikhil signs off.
- After the brainstorm produces a decision, a plan is written only if Nikhil approves a proceed direction.
- No implementation dispatch may start until both the approved spec and the approved plan are committed.
- Any proceed decision must reconcile explicitly with G3 and the later 2026-09-27 roadmap decision; it must not silently weaken that gate.

## Open questions for the brainstorm

1. Which actual users have asked for Synlynk-operated compute, and what evidence supports the request?
2. Is the problem compute availability, remote access, team coordination, budget control, or something else?
3. Would customer-operated nodes or a partner satisfy the need while keeping source and credentials outside Synlynk custody?
4. What evidence would justify revisiting G3 early, and who has authority to make that exception?
5. If the recommendation is defer, what observable trigger and review date should reopen the question?
