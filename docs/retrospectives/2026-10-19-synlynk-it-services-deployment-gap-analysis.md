# Gap analysis: Synlynk for an IT services deployment

**Date:** 19 October 2026  
**Audience:** Synlynk roadmap, for a firm whose existing teams serve many customers  
**Source:** decide panel `dec-85a5a151` (Agy, Codex on `gpt-5.6-luna`, Grok). Claude did not sit.  
**Companion:** `docs/retrospectives/2026-10-19-it-services-cxo-devin-synlynk.md`  
**Panel decision:** Synlynk may be trialled on one supervised product pod, or on one regulated on-premises pilot locked to a local model. It is not ready for that firm's teams to run it across many customers.

The tool record is stamped `approved` by `synlynk decide`. That stamp is not an operator sign-off.

## The deployment the score is about

An IT services firm does not run one repository. A practice uses the same estimation method, review gate, change control, status pack, and accelerator library across accounts. People move between accounts. Client IP must not move with them.

Synlynk today is a host-local control plane that can act as a remote engineer: `synlynk dispatch` runs a headless harness in a leased worktree, and that harness can edit, test, and open a pull request. `synlynk scan` classifies a directory as a single repo, a monorepo, or a multi-repo workspace. Topology discovery can merge git roots into one polyrepo workspace. `synlynk mesh` infers cross-repo calls. The context pack on a job is scored from that job's own graph (`synlynk/pack.py`). `synlynk/agent_store.py` still gives each repo its own workspace id, with an explicit note that cross-repo sharing is not implemented. The personal relay (`docs/personal-hosted-relay.md`) forwards events between the operator's devices. It does not execute jobs and does not merge workspace databases.

That shape can serve one team on one account. It does not yet serve a practice.

## What the panel agrees must exist first

All three members named the same three blockers, in different words:

1. An approval that is bound to the task before any unattended run.
2. A job status that matches GitHub, so a delivery manager can report it.
3. A boundary between customers strong enough that a playbook cannot carry one client's material into the next account.

SOC 2, a service-desk connector, and a bid export were each named by at least two members. They matter at different moments. The sequence below follows the deployment, not the order the members happened to list them.

## Gap register

### 1. Unattended execution can start without a task-bound approval

**Practice SOP at risk:** change control, the staffing pyramid.  
**Evidence:** `can_auto_advance` exists in `synlynk/autonomy.py` and is not called from the scheduler path. The 16 October 2026 architecture review (finding F01) showed `cmd_schedule(execute=True)` can enqueue work in supervised mode. The panel was given that finding and every member treated it as a blocker.  
**Needed:** an approval receipt bound to the task, the repository, the base SHA, the requested capabilities, the policy revision, and the budget. Supervised mode must refuse to start work from the CLI, the daemon, a retry, a handoff, or the relay when that receipt is missing.  
**Done when:** a test proves a supervised workspace cannot dispatch through any of those paths, and the pod trial runs with this gate on.  
**Sequence:** before any client pilot that is allowed to leave a person unattended. The recommended pilot keeps the scheduler off until this exists.

### 2. The record a manager reads can disagree with GitHub

**Practice SOP at risk:** status reporting, earned value, SLA evidence.  
**Evidence:** job-status false negatives are an open product defect. The panel treated "the label said failed while GitHub succeeded," and the reverse, as disqualifying for managed services.  
**Needed:** one terminal state per job, written only after the claimed effect is read back from GitHub (or from the test command the task declared). The steerco export is that state, not the process exit code.  
**Done when:** a delivery manager can paste the export into a weekly pack and it matches the pull request, the merge, and the cost row.  
**Sequence:** in parallel with gap 1. A pod can survive by reading GitHub directly. A managed-service desk cannot.

### 3. One repo is a workspace, and the account is not

**Practice SOP at risk:** knowledge transfer, accelerator reuse, client IP.  
**Evidence:** multi-repo onboarding builds a map. The job's working memory is still one repository's graph. Agent identity is not shared across repos. The mesh output is a separate artifact the job does not consume.  
**Needed:** an account object above the repos. The context pack for a task may draw from the account graph under an explicit allowlist. A person's grant on account A is not a grant on account B. An accelerator is a template with the client's source stripped, not a copy of the last engagement's `.synlynk` directory.  
**Done when:** two customer fixtures on one operator host cannot see each other's graphs, charters, cost rows, or relay subjects, and a job on account A can be shown the sibling repos it was allowed to read.  
**Sequence:** this is the gate from "one pod" to "this firm's teams, many customers." Do not start a second paying account on a shared home directory before it lands.

### 4. Residency is a harness choice, not a mode

**Practice SOP at risk:** client IP assignment, regulated delivery.  
**Evidence:** the host stores the control plane. The prompt and the diff go to the harness vendor unless the local harness is selected. The panel split the regulated-delivery score (Agy 4, Codex 3, Grok 3). The synthesis used 4 and then qualified the trial as local-model only. That qualification is the requirement.  
**Needed:** a per-account egress policy. `local-only` fails closed if the dispatch would call Claude, Codex, Grok, or Agy. `named-vendors` lists the endpoints the client's security review has accepted. The policy is on the account, not on the operator's shell.  
**Done when:** a dispatch that violates the account policy does not start, including from the scheduler.  
**Sequence:** required for the regulated pilot. Optional for a pod whose client has already accepted a named cloud harness. A SOC 2 report for Synlynk itself does not answer this, because Synlynk is not the party that receives the code in the cloud-harness case. Pursue a report when Synlynk operates a hosted control plane. Until then, ship the fail-closed mode and an audit export of which endpoint saw which job.

### 5. The firm's commercial artifacts have no export

**Practice SOP at risk:** estimation, the staffing pyramid, status reporting.  
**Evidence:** cost is recorded per job. There is no bid sheet a pursuit team can attach to a proposal, and no mapping from a story to a role, a review gate, and a capped meter. There is no Jira or ServiceNow connection. Grok asked for the bid export. Agy and the synthesis asked for ITSM connectors. Codex asked for SLA, monitoring, and cost governance.  
**Needed, in this order:**

1. A story export: role, harness policy, review gate, usage cap, actual cost, pull-request URL, terminal state.
2. A proposal view of the same export with the actuals blank, so estimation uses the firm's units plus a cap.
3. A connector that opens and updates the ticket system the account already uses.

**Done when:** a pursuit lead can price a pod from the export, and a service manager can reconcile a month of tickets to jobs without reading the CLI.  
**Sequence:** the story export is useful on the first pod. The connector is what makes managed services discussable. Do not block the pod trial on ServiceNow.

### 6. The remote engineer is a process on someone's laptop

**Practice SOP at risk:** knowledge transfer when people roll off, and any promise of a shared practice.  
**Evidence:** the relay is a self-hosted NATS bridge with workspace-scoped credentials, no per-device least privilege, and no reconciliation of two workspace databases. `relay hub connect` stores settings and does not provision a managed service. Container execution for an untrusted harness is not the path dispatch uses.  
**Needed:** a practice runner the firm's operations team can install per account, with a named operator, a backup of that account's ledger, and a revocation step when a consultant rolls off. The runner is still in the account's boundary from gap 3. It is not a Cognition-style multi-tenant brain.  
**Done when:** removing a person revokes their device credential and their dispatch right, and the account's jobs remain reviewable by the next person on the account.  
**Sequence:** after gap 3. Building a hosted engineer before tenancy exists would copy the risk the panel refused.

### 7. There is no proof at the scale a pursuit team will be asked about

**Practice SOP at risk:** the sales stage that precedes every pattern above.  
**Evidence:** Devin's public record includes multi-million-line modernizations and named services firms. Synlynk's record is this repository's own dispatched pull requests. The panel scored modernization and the factory partly on that absence.  
**Needed:** one measured pod pilot with the scorecard in the CxO brief (cycle time, escaped defects, review compliance, margin after the meter, IP incidents), written so a pursuit team can show it. Vendor-style multiples are not the goal.  
**Done when:** the pilot report exists and its failures stay in the denominator.  
**Sequence:** this is the trial the panel authorized. It is not a substitute for gaps 1 and 4.

## What to leave out of the next tranche

- A combined go-to-market with Devin. The panel compared them as separate trials.
- A hosted relay positioned as a cloud engineer. The current relay is an event bus, and the architecture review said a relay must not become the canonical writer by default.
- SOC 2 as the first milestone. It does not fix approval, job truth, tenancy, or egress. Start it when a hosted control plane is actually being sold.
- Outcome-based contracting features. Both products record compute. Neither records the business outcome. Building a gainshare meter now would invent a commercial claim the panel rejected.

## Roadmap sequence

| Order | Gap | Unlocks |
|---|---|---|
| Now, before the client pod | 1. Task-bound approval | A supervised pilot that cannot run away |
| Now, in parallel | 2. Job status matches GitHub | A weekly pack the pod lead will sign |
| With the regulated variant only | 4. Account egress policy, local-only fails closed | The on-premises trial |
| Before a second customer on the same host | 3. Account tenancy and a stripped accelerator | The practice deployment |
| During the first pod, not before it | 5. Story export, then the bid view | Pursuit and PMO |
| After tenancy | 6. Per-account runner, revocation on roll-off | Teams that change accounts |
| After the pod has numbers | 7. Pilot report with failures included | The next pursuit |
| When managed services is in scope | 5. Ticket connector, SLA view | A pattern the panel scored 2 |
| When Synlynk itself is hosted for customers | SOC 2 and the audit report | Procurement that requires a vendor cloud |

## Acceptance for "ready for this firm's teams"

The panel's bar for multi-customer deployment is met when all of the following are true on one operator host:

- Two customer fixtures cannot read each other's context, cost, or credentials.
- A dispatch that violates the account's egress policy does not start.
- Supervised mode cannot start work without a task-bound approval.
- The status export matches GitHub.
- A consultant removed from an account cannot dispatch or read that account the next day.
- The story export can be attached to a status report without interpretation.

Until then, the authorized use is one supervised pod, or one local-model on-premises pilot, with unattended scheduling off.
