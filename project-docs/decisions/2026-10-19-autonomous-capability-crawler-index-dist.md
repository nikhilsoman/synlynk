<!-- generated - source of truth is state.db -->
---
decision_id: dec-1ea791ac
topic: "Autonomous Capability Crawler & Index Distribution: Dedicated Budget, AWS Spot Docker Swarm Driver, and Signed AV-Style Definition Packs"
date: 2026-10-19
panel: [codex, grok, agy]
status: approved
---

## Topic
Autonomous Capability Crawler & Index Distribution: Dedicated Budget, AWS Spot Docker Swarm Driver, and Signed AV-Style Definition Packs

## Panel Inputs

### codex
AWS Spot Docker with a dedicated, hard-capped budget is a strong offload architecture: isolate crawler execution, enforce spend limits, and keep developer machines focused on local iteration. Design for interruption, checkpointing, and queue-based retries. Signed AV-style definition packs are appropriate for client updates when content is frequent, independently versioned, and safety-sensitive. Distribute immutable, signed manifests and packs through CDN, with rollback and signature verification built into clients. Capability Crawler is a good inaugural Synlynk Swarm workload: it is parallelizable, bounded, observable, and tolerant of retry-based execution. Phase it as an adapter over the current crawler first; validate pack signing locally, then run a small capped Spot pilot before making Swarm the default. Decision: Proceed with a phased Swarm pilot, not a roadmap-blocking rewrite.

### grok
Yes on isolation and a separate spend cap. Spot Docker is one SwarmRunnerDriver beside Fly, Kubernetes, and Local, behind the existing watchdog and auto-destruct contract. A dedicated crawl ledger is mandatory so calibration cents never mix with interactive burn. Signed AV-style packs are right for the repo registry, SFIA map, and ranker weights. Clients pull versioned, signed packs from a CDN or endpoint and refuse unsigned or stale sets. The crawler should be Swarms first workload: batch, striped, quota-heavy, and disposable. Phase 1 stays on goal-aa48c456: schema, synlynk capability crawl on local worker, and a committed registry. Phase 2 moves that same job onto a cloud driver with its own budget. CDN packs follow once the registry schema stops moving. Decision: Isolate crawl spend now; treat Spot and signed packs as incremental drivers without derailing immediate v0.24 sprint gates.

### agy
The Antivirus-style definition pack model (synlynk capability update fetching signed capability-pack.json.gz from synlynk.com / CDN) is the optimal distribution mechanism: it provides instant, zero-friction capability updates to end-users without requiring local crawler execution, database synchronization, or user token consumption. Operating the crawler as a SwarmRunnerDriver on AWS Spot instances provides cheap, preemption-tolerant execution with an isolated budget ledger. Incremental phasing preserves velocity: (1) Historical backfill & SFIA schema expansion (current sprint); (2) Signed definition pack distribution; (3) Swarm Spot cloud crawler deployment.

## Synthesis
The Decide Panel unanimously adopts the expanded operational architecture for the Capability Crawler and public index distribution, structured into four architectural commitments:

1. Dedicated Budget & Quota Isolation: Crawler spend and token ingestion are decoupled entirely from user development environments and personal subscription accounts. A dedicated ledger namespace (crawler_budget_usd) and separate API billing keys ensure background calibration never triggers user-facing quota exhaustion.

2. Cloud Offload & AWS Spot Docker Swarm Driver: The crawler is offloaded from local developer machines and packaged as a standalone Docker container. It is integrated as an official SwarmRunnerDriver (DockerSpotRunnerDriver) under synlynk/runners/manager.py, utilizing AWS EC2 Spot instances with graceful SIGTERM checkpointing on preemption notices.

3. Antivirus-Style Signed Definition Pack Distribution: Rather than requiring client-side database replication, Synlynk distributes the public capability and cost matrix as an immutable, cryptographically signed definition pack (capability-pack-YYYY-MM-DD.json.gz) via synlynk.com/update and CDN edge mirrors. Clients verify the Ed25519 release signature and ingest updates atomically via synlynk capability update.

4. Swarm Inaugural Workload & Phased Implementation: The Capability Crawler is designated as the flagship production workload for Synlynk Swarm execution mode, validating ephemeral fanned-out workers on orthogonal tasks. To protect the strategic roadmap, execution is strictly phased:
   - Phase 2A (Current Sprint): Historical state.db organic backfill (synlynk capability backfill) and open SFIA taxonomy expansion.
   - Phase 2B: Signed AV-style definition pack generator and client update CLI (synlynk capability update).
   - Phase 3: Swarm Docker Spot runner driver and cloud deployment for continuous cyclic public repo calibration.

## Decision
Decision: Approve the expanded Capability Crawler architecture: isolated cloud budget, AWS Spot Docker SwarmRunnerDriver, and signed AV-style definition pack distribution via CDN. Formally adopt the 3-phase incremental roadmap linked to goal-aa48c456.

> Signatures: see 2026-10-19-autonomous-capability-crawler-index-dist.json
