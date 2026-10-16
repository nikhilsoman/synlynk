# Decide panels: recommendation reassessment

Date: 2026-10-16. Code baseline: `19132dfabd1ecca9de7a9f06b1a8691262d90d1b`.
Companion: [architecture review](2026-10-16-frontier-lab-architecture-review.md).

This reassessment follows the architecture and code investigation. Historical panel claims are evidence of what was recommended, not evidence that an outcome occurred. In particular, `cmd_decision_record()` hardcodes `approved`; its status does not independently establish human sign-off, implementation, or validation. None of the judgments here rewrites historical decisions or grants new implementation authority.

Status meanings: **Implemented** = relevant implementation inspected; **Partial** = meaningful implementation with remaining gaps; **Regressed** = current code invalidates a former premise; **Unverified** = insufficient independently checked evidence; **Superseded** = newer explicit decision replaces the guidance; **Reject** = recommendation/claim should not guide current work; **Retain** = valid direction still requiring work. Implemented never automatically means production-proven.

## A. September 27 architecture panel: each recommendation

Source: `project-docs/decisions/2026-09-27-round-1-deep-architectural-review.json`.

| Recommendation | Present status | Validity and required next action |
|---|---|---|
| Verify effects rather than trusting exit 0 | Partial | `verify_effects` and `job_truth` exist, but permissive legacy cases and shadow rollout remain. Retain; F03/R02/R08 |
| Require verification before successful mutation | Partial / ambiguous design | Prose and diagram disagree about omitted checks. Reproduction yields verified success with `tests_passed=None`. Specify applicable checks explicitly |
| Enforce input and cumulative budgets in flight | Partial | Watchdog is real; reported usage is not always timely and termination is PID-scoped. Retain with bounded overshoot, F06 |
| Choose scoped context and reduce instruction tax | Partial | Context pack exists; five root files total 79,787 bytes. Measure per-dispatch injected tokens, not just file size |
| Probe capabilities before routing, deny unknown | Partial | Probe/permission code exists; unknown-action authorization exceptions need negative tests. Do not equate a writable canary with full execution capability |
| One canonical state ledger | Partial | Resolver, registry and explicit modes are substantial progress. JSON reconciliation and tracked projections remain at baseline |
| One writer/leased worktree lifecycle | Partial | Leases/WAL helpers exist; brief concurrency tests pass. WAL is not an application-level ownership proof; test restart, stale epochs and shared Git refs |
| Role + Harness default vocabulary | Partial | CLI rename and glossary exist; user journeys still expose extensive governance machinery |
| Compress GOVERNS default to 3-5 stages | Partial / UX unverified | Retain progressive disclosure. Ten onboarding stages are not proof of a simple first run |
| Opt-in GitHub App identity for simple local use | Retain with scope | Basic local tasks should not require App setup; remote write safety still requires explicit suitable credentials |
| About eight preview verbs; hide advanced dependencies | Partial | Taxonomy and fast paths exist; choose a small task-oriented default and measure discovery, not a magic verb count |
| Degrade Vizor/daemon without network or graphs | Partial | Offline-first design is sensible; observed status crash shows recovery observation still coupled to mutation |
| Fix architecture/instruction accuracy | Partial | Some old claims corrected, others stale in policy and version labels. Generate facts with a verified SHA |
| Replace brittle first-line receipt reliance | Partial | Structured events and corroboration exist; sentinel still has many receipt warnings. Require causal effect evidence, not arbitrary output formatting |
| Measure tokens per verified acceptance criterion | Retain | Stronger than tokens per file, provided acceptance is independently checked and total retry/review cost is included |
| Hold preview until invariants demonstrated end to end | Retain | October 2 clearance cannot override present counterexamples. Revalidate at the release SHA |

## B. September 27 business/roadmap panels and October 2 re-reviews

Sources: September 27 rounds 2/3; October 2 rounds 1/2/3, broader issues, add-ons and Tokq panels.

| Recommendation or assertion | Present status | Detailed assessment |
|---|---|---|
| Position as local-first neutral control plane | Implemented in README | Clear and suitable. Package metadata still says coordination OS; align secondary surfaces |
| Position outcome history as differentiation | Retain, unproven advantage | Useful only with clean causal attribution, independent quality and consented reuse; a SQLite file is not a data moat |
| Host-local means code never enters agent clouds | Reject | Cloud harnesses and gateway calls contradict this universal claim. Distinguish local storage, local execution and local inference |
| All five invariants passed on October 2 | Reject as current clearance | F01-F10 demonstrate present gaps. Historical outcome must be re-evidenced, not assumed false or true solely from prose |
| WAL eliminates database locking/stale worktrees | Reject absolute | WAL permits concurrent readers and serializes writes; workload, lock lifetimes and crash recovery still matter |
| Breakers eliminate runaway spend | Reject absolute | Telemetry delay, evaluator failures and descendant processes remain. State measured bound and detection coverage |
| Four first-win field trials passed in 4-14 minutes | Unverified | Record has timings but this audit did not reproduce trials or trace every raw receipt. Require commit/environment/task and independent acceptance evidence |
| All tests green and status 0.62 s | Unverified historically; not current proof | Current selected tests: 123 passed/5 xfailed. Current sandbox status crashes. Neither result reconstructs October 2 conditions |
| Instruction tax ~6,500 tokens | Unverified | Current source bytes are measured; exact injected/tokenized prompt was not. Do not substitute bytes/4 for a validated token budget |
| Commercially cleared / defensible moat | Reject as established fact | No audited demand, retention, pricing experiment or causal routing advantage in this review |
| Personal free, Teams/Enterprise paid tiers | Retain as hypotheses | Pricing needs willingness-to-pay and support-cost data; no recommendation of the historical price points |
| Horizon 1 then Teams then Enterprise | Retain | Sequence by reliability/adoption gates, not the now-passed October 1 date |
| Stars/forks as horizon gates | Revise | Useful community signals; accepted outcomes, active external teams and retention matter more |
| Autonomous dispatch streak with zero human code intervention | Revise | Can reward unreviewed busywork. Measure accepted value and intervention burden while preserving human approval |
| Defer proprietary memory marketplace | Retain | Focus and trust arguments remain valid; signed portable packs do not require a market |
| AST context is always exact/fresh and large windows obsolete curated memory | Reject absolute | Extraction, unsupported languages, generated code and invalidation can fail; curated constraints can remain valuable |
| Tokq permanently retired | Conflicted | Same-day expansion record revives it. Record explicit supersession or a human decision before any roadmap action |
| Tokens/stablecoins/slashing prove real engineering work | Reject for current portfolio | Diff+tests is not sufficient economic or semantic proof. No need demonstrated for settlement; keep outside committed roadmap |
| Add-ons / product registry / BYOK drivers | Partial | `addon.py`, registry and role infrastructure exist; a secure lifecycle and useful third-party driver outcomes remain separate proofs |
| Concierge requirements-to-proposal flow | Unverified complete journey | Discovery assistance can be valuable, but must not auto-authorize work or upstream messages. Establish task-level consent and acceptance |
| Local model integration first | Partial | Local adapter exists; receipt conformance xfails remain. No measured 20% accepted-work contribution established |
| OpenRouter/Fal/LiteLLM expansion | Partial / OpenRouter regression | OpenRouter transport exists; dispatch registration absent. Do not infer support for other providers from the gateway name |
| Muse promotion | Partial | MuseAdapter exists and is included in conformance. Empirical task-specific production parity unverified |
| Tri-modal autonomy dial | Regressed semantics | Supervised scheduler requests execution. Fix F01 before unattended promotion |
| Boardroom HUD and executable charters | Partial | Charters/policy/display infrastructure exists; display and instruction injection do not prove enforced authority |
| Jev sub-20ms AST decision system | Defer | No measured critical-path bottleneck requiring it shown. Fix deterministic orchestration first |
| Parallel worktree swarms | Partial / gated | Existing scheduler/worktrees provide a base; isolation, economics and merge conflict behavior need tests |
| Zero outstanding GitHub issues | Reject as objective | Issue count is not value; it encourages premature closure and unnecessary execution |
| Mobile/data domain packs | Defer breadth | Pilot one useful domain with measurable acceptance improvement |
| OSS contributor docs and website refresh | Retain | Version, install and success-claim consistency are immediate needs |
| Permission skipping opt-in | Improved | `skip_permissions=False` default inspected. Verify every backend and configuration override, not just signature defaults |
| Minimal init and retention controls | Partial | Onboarding engine exists; minimal fresh-machine experience and bounded artifact retention need independent receipts |
| Routing-proof report + five-way benchmark | Partial | Report shipped but has cross-attribution defect; benchmark outcome evidence not established |
| 10-20 design partners / one paid conversion | Unverified | Retain externally tested demand as a gate; choose realistic initial cohort of 5-10 teams |
| Recruit partners before broad launch | Retain | Reduces maintenance surprise and tests first-win claims |
| Competitive matrix / authorship framing | Revise | Use dated primary sources; do not claim uniqueness or quality from agent authorship itself |
| OpenClaw skill / OpenRouter partnership | Hypotheses | An integration is not a partnership. Pursue only if it reaches actual users and preserves authority/data boundaries |
| Avoid inference billing; privacy-safe outcome schema | Retain | Keep financial scope narrow and export only consented, redacted evidence |
| Documentary/benchmark content before tutorials | Conditional | Accurate incident evidence is useful; content order should follow audience need, not substitute for product readiness |

## C. October 5 review, ratified/triaged October 6: every priority and opportunity

Sources: `docs/reviews/2026-10-05-three-lens-strategic-review.md` and October 6 panel record.

| Ref | Recommendation | Status and assessment |
|---|---|---|
| P0-1 | Consolidate state and ship capability report or remove claim | Partial: canonical resolution/report exist; stale policy says otherwise. Fix attribution before claiming useful empirical selection |
| P0-2 | Complete adapter strangler | Partial: registry is now consulted and legacy class removed from registry; execution still has multiple abstractions. OpenRouter exposes migration regression |
| P0-3 | Host-auth fallback audit log | Implemented source path inspected; live persistence/failure behavior not exercised. Close stale documentation, retain audit-before-effect verification |
| P1-1 | Config schema validation | Implemented basic checker and doctor tests passed; nested security overrides lack strict validation. Continue depth, not another parallel schema system |
| P1-2 | Config decomposition | Implemented split/write/load machinery in `__init__.py`; autonomy still has its own CWD-relative config reader. Unify typed access |
| P1-3 | GOVERNS hard-fail | Partial: gate code exists, current policy is observe. "Shipped" and "enforced here" must be distinct |
| P1-4 | 20-50 SQLite writers | Implemented and passed short tests; extend to sustained multiprocess/recovery. Cannot be deferred indefinitely while selling fleet safety |
| P1-5 | Adapter conformance | Implemented with five xfails. This is progress, not full parity |
| P2-1 | VS Code thin client | Unverified shipping/adoption. Valid after stable API and actual pilot demand; do not build many clients at once |
| P2-2 | External evaluation harness | Partial infrastructure; no independent external benchmark run here. Use realistic held-out tasks and contamination controls |
| P2-3 | Hosted relay managed service | Personal NATS hub exists; managed tenancy, support and economics unverified. Distinguish personal relay from hosted execution |
| Opp-1 | Prove routing thesis | Retain, highest product-evidence priority after safety. Paired prospective evaluation needed; descriptive dogfood medians insufficient |
| Opp-2 | Distribution surface + GitHub App | Retain one surface. Existing role Apps serve identity, not proof of a distributed customer product |
| Opp-3 | Finish strangler and harden adapters | Retain, R07. Must preserve every supported target during cutover |
| Opp-4 | Governance, audit and RBAC | Partial: local role/merge policy exists. Prior assertion "no RBAC" was too broad; enterprise identity and tamper resistance remain unproven |
| Opp-5 | Standalone ledger product | Explore via read-only export first. Product and data rights require demand validation; avoid a second product now |
| Opp-6 | One-click sovereign local + case study | Partial local implementation; genuine zero-egress profile and third-party case study unverified |
| Opp-7 | Demo and pricing | Retain demo, experiment with pricing after demand. Demo must use attributable results, not fabricated pass flags |
| Panel addendum | Fail-closed local preflight | Improved helper returns False on failure; caller behavior and explicit-local no-fallback integration must be demonstrated |
| Panel addendum | Correct routing marketing | README now states minimum samples/interim defaults. Retain; policy generator status still stale and report semantics weaker than wording |
| Panel addendum | Park all RBAC/soak work indefinitely | Reject blanket deferral | Security and reliability appropriate to advertised workflows are prerequisites; advanced enterprise features can wait |
| Panel addendum | Reject M&A valuation and VC verdict | Retain rejection of unsupported numbers | User explicitly requests portfolio fit now; provide conditional engineering diligence without an invented valuation |
| Earlier review claim | stdlib means no supply-chain risk / install never breaks | Reject | Python, Git, provider CLIs, CI actions, images, packages and optional NATS remain dependencies |
| Earlier review claim | `sandbox.py`/`fencing.py` enforce filesystem safety | Reject | Inspected files scaffold a demo and render cost UI; use actual harness/container boundaries in the threat model |

## D. October 3 completion-oracle panel: conditions individually

| Required condition | Present assessment |
|---|---|
| Causal actor/target/SHA/time attribution | Partial: contract builders and evidence fields exist; legacy verifier remains broader. Prove all public completion paths |
| Multiple absence reads after deadline | Partial design/engine support; live eventual-consistency behavior not tested here. Retain bounded retry and verifying status |
| Weak receipts cannot override strong evidence | Direction valid; structured telemetry can override exit code in legacy verifier. Audit precedence against immutable effect contract |
| Explicit no-op contract only | Partial: canonical engine exists; unknown legacy class succeeds. Close permissive fallback |
| Closed status enum and aliases | Implemented in `job_truth.py`; propagation to all projections still incomplete |
| Late evidence and decision revisions | Implemented structures/projections; atomic causal propagation and races need integration proof |
| Bounded verifying age | Metrics and promotion limits exist; no live deadline/recovery receipt audited |
| Verified completion never downgraded | Revise absolute: new evidence of a mistaken/compromised verification must permit an explicit correction with history. Cancellation after a real landed effect should not erase that effect |
| Immutable conjunctive contracts | Builders exist; verify lifecycle enforcement, no post-launch weakening and exact predicates |
| Evidence idempotency + cost transaction | Partial engine; report join still breaks downstream attribution. Prove duplicate callbacks/retries and one accepted accounting interpretation |
| No network under DB claim; fencing tokens | Retain; inspect all active reconcilers during R08/R11, not just pure oracle tests |
| Shadow promotion with numeric gate | Implemented gate/default shadow; no successful production promotion established. Minimum 100 is a gate, not statistical proof of rare-error safety |
| Executable writer inventory | Manifest exists, but checks source text for an adapter name. Strengthen with behavioral tests and restricted mutation API |
| Historical fixture replay with independent GitHub truth | Unverified live replay; existing test suite is not an independent API replay receipt |
| GitHub-review pilot before broadening | Retain until evidence supports generalization |
| Agy and non-JSON coverage explicitly bounded | Retain per-harness coverage reporting; do not hide unsupported paths in aggregate success |
| Versioned status contract and rollback | Projection schema exists; integration migration/rollback demonstration remains necessary |
| Bounded evidence retention | Retain; retention must preserve audit/appeal needs without unbounded database growth |

## E. October 10-16 sequencing and implementation panels

| Recommendation | Status / validity today |
|---|---|
| Foundation before measurement before claims before swarms | Retain. Code exists for foundations, but reproduced defects mean the gate is not simply issue closure |
| End-of-week-1 consolidation/status checkpoint | Historical date gate; replace with evidence checkpoint at current SHA. Do not rerequest already-shipped consolidation |
| Week-2 local/routing sample go/no-go | Retain evidence gate; disclose integrated/unmeasured if needed. Sample count alone does not repair attribution |
| Ship narrower preview if seven pillars cannot be proven | Retain. Best near-term release strategy |
| Provider/BYOK before interface and swarm expansion | Retain stable auth/execution contract; repair OpenRouter registry integration first |
| One thin interface before many | Retain; adoption chooses the first client |
| Personal hosted relay design only, no October implementation | Departed from sequence: hub code is now present. Gate violation cannot be established without full chronology, but foundation proof still must precede its promotion |
| Oracle destination, provisional nonterminal stopgap | Retain. Avoid a new competing terminal writer; close unknown contracts and independently adjudicate shadow disagreements |
| Replay disputed cases before oracle promotion | Unverified run; still required. No current production gate receipt reviewed |
| Keep receipt, cost and status bugs on distinct tracks | Retain distinct root causes, with one coordinated end-to-end acceptance journey |
| OpenRouter baseline bridge sound while registry unused | Regressed premise: registry now required. Bridge needs adapter integration or explicit alternate contract |
| Defer GenericAPIAdapter as dead code | Superseded by live registry dependence. Reevaluate now rather than indefinitely preserving deferral |
| Add dispatch integration test for OpenRouter | Still necessary; direct gateway tests did not prevent present mismatch |
| Durable PM/TPM/QA/maintainer; other roles on call | Retain mandate split; test lifecycle ownership and resource bounds |
| TPM owns raw-issue intake, architect gates execution plans | Partial machinery present. An issue is untrusted input and not approval; enforce separately |
| Harness selection out of charters | Retain. Role mandate and tool capability are different dimensions |
| Never let quota sit idle | Revise: use only approved, useful work with positive expected value; preserve safe idleness |
| Generated status exports beside canonical DB, not Git | Accepted and valid. At baseline files still tracked; #2328 user comment confirms decision, later comment reports PR #2338 implementation. Merge not verified |
| No nightly generated-doc commit | Retain. On-change/on-demand export with revision stamps and atomic replacement |
| PR hard-fails on former generated paths; stop autocommits | Pending at baseline; verify #2338 before duplicating work |

## F. Catalog of all decision records

The following catalog accounts for every current JSON panel record, including narrower historical decisions outside the major strategic reviews. Each entry gives an independent present-day disposition. The source decision text remains in its original file; the catalog does not imply every historical feature received a live end-to-end test.

| # | Date / record topic | Status, evidence, validity and next action |
|---|---|---|
| 1 | 2026-07-18: before intensive multi-agent dogfooding | Historical blockers unverified individually. Retain evidence-based dogfood admission; do not infer closure of #330/#332/#338/#340/#342/#343/#344 from later release approvals. Current failures require a fresh matrix |
| 2 | 2026-07-23: wire user lifecycle triggers | Partial. Trigger registry and soft checkpoint suggestions are in AI_INSTRUCTIONS. Retain opt-in suggestions and avoid conversational goal spam; acceptance telemetry was not established |
| 3 | 2026-07-25: per-role GitHub Apps | Partial implementation. `team.py`, `gh_role.py`, `gh_shim.py` contain identity/token/audit machinery. Retain scoped credentials; key permissions, redaction, direct-write bypasses and additional security review need live verification |
| 4 | 2026-07-30: harness self-review | Partial / historical flags superseded. Adapter-specific permission translation exists, but conformance signatures drift. Native capability probes should determine current flags, not July descriptions |
| 5 | 2026-08-02: fleet-operability survey | Partial. `selftest.py` and dry CI matrix exist; no live all-harness/all-verb result audited. Codex exclusion and Claude/Grok-only GH writes are superseded by October policy. Retain verified effect matrix |
| 6 | 2026-08-09: retire Grok-default GH writes | Superseded in routing details. Current measured fallback order starts Codex; keep scoped capability eligibility. Do not retain the historical blanket Codex network exclusion |
| 7 | 2026-08-09: SFIA taxonomy | Retain narrow vocabulary use. `discipline` and related dimensions exist; report mappings are incomplete and should not become access control. No evidence SFIA alone supplies authorization or marketplace portability |
| 8 | 2026-08-09: TPM derives from GOVERNS | Partial. Scheduler/backlog and event systems exist alongside independent status reconciliation. Retain one authority and derived scheduling; validate typed linkage, consumer cursors and correction semantics |
| 9 | 2026-08-09: live holdback calibration | Unverified complete implementation. Sweep/watch/report modules exist; stratified holdback/canary policy not found in inspected capability/dispatch paths. Retain bounded randomized evaluation, approval and rollback; repair F04 first |
| 10 | 2026-08-09: five-phase role architecture | Partial. Roles, charters and model primitives exist. Retain separation of role mandate, access and routing; human approval must be independently recorded. Tokq prerequisite framing is superseded/conflicted |
| 11 | 2026-08-14 round 1: canonical docs location | Superseded for generated todo/roadmap/costs by #2328; authored memory/devlogs remain in repo. Preserve inventory/quarantine safety during migration |
| 12 | 2026-08-14 round 2: lifecycle manifest / upgrade / audit | Partial. Lifecycle/audit mechanisms and extensive archives exist; active strategy still drifts. Retain explicit supersession and idempotent migration, verify against #2328 |
| 13 | 2026-08-14 round 3: documentation categories and release communication | Partial / process drift. October 16 repeats release-oriented blog policy while marketing-pr-sync still generates per-PR posts. Implement the accepted workflow policy together with instruction changes |
| 14 | 2026-08-14 round 4: manifest-driven CRUD | Partial / broad enforcement unverified. Retain category-specific ownership and archive semantics; audit-docs alone cannot make concurrent generated Git documents safe |
| 15 | 2026-08-14 round 5: generated artifacts and sentinel authority | Partial / placement superseded. Root instruction generation exists; sentinel projection remains large. Adopt canonical sidecars for the three named state exports; prove DB incident lifecycle rather than relying on append-only prose |
| 16 | 2026-08-14 round 6: identity registry and revisioned writes | Partial. Product/agent/state registries exist; cross-member identity-fork recovery not exercised here. Retain stable identities and revision-aware writes; signatures/relay are distinct later proofs |
| 17 | 2026-08-14 round 7: workspace agent artifact plane | Partial. Charter schema/injection/storage infrastructure exists. Retain curated records and human-gated mutability; policy protection must extend beyond prompts |
| 18 | 2026-08-16: rename agent commands to harness | Implemented taxonomy/instruction distinction. Valid terminology correction; still measure whether users understand role, harness and provider |
| 19 | 2026-08-19 round 1: host-side deterministic GH broker | Unverified full requested protocol. Role/shim implementation is not proof of a request-ID broker with per-action allowlists. Retain non-LLM authority and deterministic mediation; inspect bypasses before claiming universality |
| 20 | 2026-08-19 round 2: home/headless broker coverage | Unverified universal enforcement. Current interactive sessions and dispatched jobs have different authority surfaces. Keep explicit scope and host-side waits; no model polling or credential-bearing workaround |
| 21 | 2026-08-27: charter authority surfacing | Partial. Shared charter injection and dynamic role concepts exist. Static routing instructions still conflict with policy/runtime. Retain reassignable human-authority pointer only with authenticated approval |
| 22 | 2026-08-29: book editorial review | Unverified editorial completion. This audit did not assess the full manuscript for glossary, endnotes or chapter consolidation. Recommendations remain editorially plausible but provide no product-release evidence |
| 23 | 2026-09-02: first-class model/family | Partial. `models.py`, model-catalog migration and dispatch resolution exist. Retain requested/resolved provenance; hardcoded tier defaults and disconnected cost attribution require reconciliation |
| 24 | 2026-09-13: FTUE and first win | Partial. Unified onboarding and tests pass; 5-minute PR-created-and-checked promise not independently reproduced. Retain dirty-repo isolation, offline deterministic scan, explicit approval and scope limits |
| 25 | 2026-09-14: add-ons / skills / graphify lifecycle | Partial. Add-on/pack/scan facilities exist. Secure grants, compatibility versions, deprecation and invalidation remain separate obligations; no marketplace launch implied |
| 26 | 2026-09-14: reusable spike harness, defer mesh/research | Partial. `spike.py` exists; result quality/ROI unverified. Retain experimental harness and demand gate for broad research; avoid claiming graph freshness from existence |
| 27 | 2026-09-18: canonical DB and idempotent hardening | Substantially implemented, not fully operationally verified. Resolver/registry/repair/inventory exist and fail closed in observed environment. Retain recovery modes; make status readable when writes denied |
| 28 | 2026-09-19: sequence five initiatives behind recovery | Retain but sequence drift evident. Relay and autonomy now exist while core defects persist. Reassert evidence gates; do not interpret presence as proof that recovery prerequisites passed |
| 29 | 2026-09-20: model catalog and tiers | Partial. Catalog discovery shipped, but `_DEFAULT_MODELS_BY_TIER` remains in dispatch and uses fast/pro/reasoning terminology. Distinguish deliberate fallback from forbidden authoritative code mappings; audit requested/resolved values |
| 30 | 2026-09-20: acceptance and multi-node soak | Partial. Testbed plus 20/50-thread WAL tests exist and selected tests passed. VM/nightly/pre-release and long-running multi-node receipts unverified. Retain provider-neutral, isolated acceptance |
| 31 | 2026-09-20: Cloudflare tunnel | Unverified complete security path. Personal NATS hub is not evidence of Cloudflare JWT admission/member mapping. Retain opt-in read-first exposure and separate tunnel versus state-sync responsibilities |
| 32 | 2026-09-20: keep compliance/swarm in monorepo | Retain modular-monolith preference. Optional `nats-py` now means the broader zero-runtime-dependency claim needs qualification; it does not itself prove the swarm extraction trigger fired. Reassess extraction on actual dependency/release boundaries |
| 33 | 2026-09-27 round 1: deep architecture | Partial; recommendations individually reassessed in A. Preserve invariants, resolve weak definitions and test actual boundaries |
| 34 | 2026-09-27 round 2: strategic business | Partially valid thesis; differentiation, commercial and sovereignty claims need qualification. See B and portfolio section |
| 35 | 2026-09-27 round 3: roadmap and Tokq | Retain phased progression and marketplace deferral; revise vanity gates and absolute freshness/locality claims. Later Tokq records conflict |
| 36 | 2026-09-30: Vizor V2 architecture | Partial. `viz/` decomposition, routing and onboarding surfaces exist. Second-workspace validation and all server-resolved path constraints were not audited end to end. Retain no client-supplied filesystem authority |
| 37 | 2026-10-01: topology discovery | Partial. Shared onboarding/topology implementation and tests exist. Retain evidence-scored read-only discovery and explicit confirmation; noninteractive behavior must never persist inferred topology silently |
| 38 | 2026-10-01: unified onboarding | Implemented foundation; selected integration tests pass. Resume/idempotence and external first-win gates remain operational evidence requirements, not satisfied by stage names |
| 39 | 2026-10-01: resilient packaging ladder | Partial / complete matrix unverified. Install-manifest and testbed installer exist; supported Python floor already drifts in README. Retain atomic upgrade/rollback and explicit bootstrap/PATH consent |
| 40 | 2026-10-02: add-ons/registry/concierge | Partial; see B. Approval of broad v0.24 scope is not evidence of each shipped, safe user journey |
| 41 | 2026-10-02: broader strategic concerns | Partial. README positioning improved; proof report exists but defective. Partner, benchmark and external demand outcomes unverified; retain honest launch gates |
| 42 | 2026-10-02 round 1: architectural re-review | Current clearance rejected. Concrete present failures contradict unconditional five-invariant pass; historical claims need attached receipts |
| 43 | 2026-10-02 round 2: business re-review | Current clearance unsupported. Local-storage/inference confusion and unverified field/market data invalidate using it as diligence approval |
| 44 | 2026-10-02 round 3: authoritative roadmap/release | Superseded in schedule by October 10; unconditional readiness and zero-defect numbers unverified. Preserve old record but mark its applicability expired |
| 45 | 2026-10-02: Tokq/DAO/autonomous expansion | Reject settlement as current priority; mixed valid foundations and speculative scope. Autonomy safety and verified economics take precedence; reconcile contradictory retirement decision |
| 46 | 2026-10-03: job-truth design review | Partial, detailed in D. Strongest architectural direction in decision history; complete authoritative integration instead of adding status heuristics |
| 47 | 2026-10-04: containerized dispatch | Implemented core flags inspected, selected tests passed. Retain caveats: bridge network has outbound/LAN reach; Git common dir writable; no production escape test performed |
| 48 | 2026-10-06: three-lens review triage | Partial, detailed in C. Several previously unbuilt items now exist. Reject indefinite deferral of necessary safety/reliability; avoid duplicate tickets for shipped foundations |
| 49 | 2026-10-10 R2: preview reprioritization | Valid dependencies, partial adherence. Provider bridge currently incompatible with registry; personal hub code exists despite earlier design-only sequencing. Revalidate foundation gate |
| 50 | 2026-10-10: revised dev-preview roadmap | Retain conditional, narrower preview. Calendar and minimum samples must not override truthful claims; current quality of samples is the blocker |
| 51 | 2026-10-10: job-status false negatives | Partial. Provisional status and pure oracle direction are sound; production promotion proof unavailable. Retain independent case replay and avoid competing terminal writers |
| 52 | 2026-10-11: GenericAPIAdapter/OpenRouter bridge | Regressed architectural premise. Registry now consulted; OpenRouter missing. Prior merge approval does not certify present integration |
| 53 | 2026-10-13: finalize roles/charters | Partial. Role mandate split sound; continuous work should optimize value, not quota consumption. Supervised execution defect blocks autonomous-readiness claim |
| 54 | 2026-10-16: generated todo/roadmap/costs location | Accepted by explicit user issue comment, implementation reported in PR #2338, not verified merged. Retain canonical sidecars and no feature-worktree commits; do not edit original uncommitted decision artifacts |

## G. What should change in the decide process itself

Every recommendation needs a stable ID, source evidence at a commit, status, owner, acceptance criterion and supersession link. A panel may recommend; a human or explicitly delegated authority may approve; deterministic verification and independent review establish implementation status. These are distinct events.

Require panelists to label inspected, inferred and unverified claims. Attach command outputs and environment metadata to numerical claims. Use heterogeneous reviewers for useful perspective, but do not count four correlated model opinions as four independent experiments. Synthesis must preserve dissent and missing evidence. A release clearance should expire after relevant changes and should never follow merely from storing a decision record.

The practical next step is R01-R06 in the companion review: repair authority, completion and attribution, reconcile the provider seam, and make the active plan reflect verified reality. More panel rounds on unchanged evidence will not resolve those defects.
