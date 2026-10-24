# AI engineering tools for an IT services practice

**For:** the CxO team of an IT services firm  
**Date:** 19 October 2026  
**Question:** which client-engagement patterns can keep the firm's existing delivery SOPs if the firm trials Devin and Synlynk separately  
**Panel:** Agy, Codex (`gpt-5.6-luna`), Grok. Claude was invited and could not sit (weekly CLI limit).  
**Record:** `project-docs/decisions/2026-10-19-it-services-cxo-strategic-review-devin-a.md` (`dec-85a5a151`)  
**Status of that record:** the decide tool stamps `approved` when it writes. This brief is the panel's recommendation. It is not an operator sign-off.

## Decision

Trial Devin on legacy modernization, managed application services, and accompanied time-and-materials work, with the firm's peer review, change control, and a usage cap written into the statement of work.

Trial Synlynk on one dedicated product-engineering pod, or on one regulated on-premises pilot that is required to use a local model, with unattended execution turned off.

Do not put either tool into a multi-account factory or an outcome-based contract yet. Synlynk is not ready for one firm's teams to deploy it across many customers. Devin and Synlynk are separate trials. They are not a combined offer.

## How to read the scores

The score is fitness for keeping the firm's current practice, not a rating of model quality. Five means estimation, the staffing pyramid, peer review, change control, status reporting, knowledge transfer, client IP assignment, and reuse of accelerators can stay as they are. One means the tool forces the firm to abandon those SOPs.

The working score is the panel synthesis. The range is the three members. A wide range means the CxO should treat the working score as a split opinion, not a measurement.

Vendor case studies (Nubank, Comarch, Mercedes-Benz, Endava, Cognizant, Infosys, and others) are the vendor's account of the result. The panel was instructed not to treat those multiples as audited.

## What each trial actually is

**Devin** is an autonomous software engineer from Cognition. A session plans, edits, tests, and opens a pull request from Cloud, Desktop, or CLI. Enterprise buyers get SAML or OIDC, SOC 2 Type II (since September 2024), and a contract metered in Agent Compute Units. The machine can sit in Cognition's cloud, in a dedicated VPC, or in the customer's VPC. In the documented dedicated model the reasoning tier can still run in Cognition's cloud while the dev environment sits in the customer network. Public services-firm use already exists, including Cognizant, Infosys, Endava, WPP Enterprise Solutions, and AHEAD. Cognition staffs partner-deployed engineers for global systems integrators. In Japan the published split is the one a services firm needs: accompany the client's own team, or use Devin on the firm's contracted delivery.

**Synlynk** is a host-local control plane in this repository. It sends a task to a harness the firm already runs (Claude, Codex, Grok, Agy, or a local model). The harness works in its own git worktree and can edit, test, and open a pull request. The product also scans a workspace, can classify a directory of repositories, builds a cross-repo graph, requires a different party to review, and records cost against the job. It does not operate a multi-tenant cloud. The personal relay moves events between the operator's own devices. It does not host the engineer or the client's code. A model call still leaves the host unless the local harness is the one selected. A 16 October 2026 architecture review, which the panel was required to use, found that unattended scheduling does not consistently demand approval before work starts, and that a job's recorded status can diverge from GitHub.

## Engagement patterns

| Pattern | Devin | Synlynk | Member range (Devin / Synlynk) | What happens to the SOP |
|---|---:|---:|---|---|
| Time-and-materials staff augmentation | 4 | 3 | 2–5 / 2–4 | Devin can be sold as accompanied capacity beside a named team. Grok scored it 2 because an autonomous seat bypasses the pyramid. Synlynk fits when it follows a named engineer and unattended scheduling stays off. |
| Fixed-price project | 3 | 2 | 2–4 / 2–3 | Neither meter is a person-day. ACU and token spend sit outside the estimate. A cap in the SOW is the control. Synlynk's status gap makes earned-value reporting weaker. |
| Managed application services | 4 | 2 | 3–4 / 2–3 | Devin Oncall and ticket links resemble a run-state queue. Synlynk has no service-desk connector, and a status that can disagree with GitHub is a weak SLA evidence pack. |
| Legacy modernization program | 4 | 3 | 3–5 / 2–4 | This is the Devin trial the whole panel will support, with the firm's review gate kept. Synlynk's repo graph is useful context and has no published program at this scale. Codex was the high outlier on Synlynk (4). |
| Dedicated product-engineering pod | 4 | 4 | 3–5 / 4–4 | The one pattern where all three members score Synlynk at 4 or above. Role charters, a worktree per job, and a non-author review match how a pod already works. |
| Multi-account factory, one playbook | 3 | 2 | 2–4 / 2–2 | Unanimous that Synlynk cannot carry one playbook across accounts. There is no tenant boundary, so an accelerator can meet the next client's IP. Devin's enterprise tenancy is further along and still not a factory SOP. |
| Advisory, then implementation | 4 | 3 | 3–4 / 2–3 | Devin's codebase reading supports a discovery phase that becomes a build. Synlynk's workspace scan supports an audit. The handoff into delivery is a dispatch, not a client workshop pack. |
| Regulated, on the client's premises | 2 | 4 | 2–2 / 3–4 | Devin is unanimous at 2: the reasoning tier is off-host in the dedicated model. The synthesis scores Synlynk 4 by following Agy. Codex and Grok scored 3, because a cloud harness still sends the prompt and the diff out. Use 4 only when the pilot is locked to the local harness. |
| Outcome-based or gainshare | 2 | 2 | 2–3 / 2–3 | Both meters record compute. Neither records the client outcome the contract pays on. Keep this pattern out of the first trials. |

## Where the existing SOP holds

Peer review and change control hold when the firm keeps them in the statement of work. Devin's pull request is the input to the firm's review, not a replacement for it. Synlynk already separates the reviewer from the author. That matches a pod's definition of done, which is why the pod is the Synlynk trial.

Estimation holds only as a capped envelope. Person-day rates do not describe Agent Compute Units or harness tokens. The PMO should price a discovery fee plus a usage ceiling, and stop the pilot when the ceiling is hit.

The staffing pyramid holds on accompanied time-and-materials and on a named pod. It weakens if the tool is staffed as a headcount substitute. Grok's low score on Devin for staff augmentation is that warning. The Japan accompany model, which Cognition already publishes, is the shape that keeps the firm's people in the engagement.

Knowledge transfer holds when the firm leaves the client with the runbook, the review record, and the cost record. Synlynk's ledger is built for that handback on a single host. Devin's session history lives with the vendor unless the contract says otherwise.

Client IP assignment holds in the contract either way. Technically it holds for Synlynk when the selected harness is local, and it needs a written egress rule when the harness is Claude, Codex, Grok, or Agy. For Devin it needs the deployment schedule in the order form, because "in your VPC" does not by itself mean the reasoning tier is in the VPC.

Status reporting holds for Devin through the ticket tools a managed-service desk already uses. It does not yet hold for Synlynk, because the job record and GitHub can disagree. A delivery manager should not paste a Synlynk job status into a client steerco.

## SWOT

### Devin

**Strengths.** The product is an engineer a client can watch: shell, editor, browser, parallel sessions, review, and on-call. Enterprise procurement has a path: SOC 2 Type II, SAML or OIDC, a sales contract, and marketplace routes. Services firms are already on the record, and Cognition is hiring people whose job is to make those firms successful. Ticket and chat assignment matches how a managed-service queue already works.

**Weaknesses.** The usage meter does not match a person-day estimate or a fixed-price baseline. In the dedicated deployment the reasoning tier can remain in Cognition's cloud, so a residency slide that says "your VPC" is incomplete until the order form is read. The autonomous session will ignore the staffing pyramid unless the SOW names the firm's reviewers and forbids unattended merge.

**Opportunities.** One modernization account and one accompanied time-and-materials account are enough to learn the offer. Partner-deployed engineers let the firm build a repeatable playbook on Cognition's time. Managed service is the second commercial pattern, because on-call and ticket links resemble work the firm already staffs.

**Threats.** Client code and prompts meet a vendor-operated brain. Direct sales compete with the partner for the same logo. Unit cost moves with the model and the session length, so an uncapped commitment inside a fixed fee is a margin leak. A published 8x or 12x result that the firm cannot reproduce on its own scope becomes a renewal problem.

### Synlynk

**Strengths.** The firm runs it on a host it controls and chooses the engineer per task, including a local model. Each job is isolated in a worktree. A different party reviews. Cost is recorded against the job. Roles and charters give a pod a place to put the responsibilities it already has. Workspace scan and the cross-repo graph are a real start on "understand this account before anyone codes."

**Weaknesses.** Unattended execution is not a safe default: approval before auto-execute is not consistently enforced. Job status can diverge from GitHub, so the PMO cannot trust the dashboard. Each repository still has its own workspace identity, and the context a job receives comes from that repository's graph, not from the merged map of the account. There is no systems-integrator kit, no service-desk connector, and no published result on a multi-million-line estate. There is no SOC 2 report. For a tool with no cloud tenancy, the sharper gap is the absence of a fail-closed local-only mode.

**Opportunities.** A single product pod can adopt it without throwing away sprint review. A regulated account that already forbids code from leaving the building is the other honest pilot, and only with the local harness. The longer opportunity is the layer the firm's existing teams operate across accounts: policy, evidence, and cost, with whichever coding agent the client already bought.

**Threats.** Turning on the scheduler across clients before approval and tenancy exist can breach change control and mix one client's material into another's context. A cloud harness quietly defeats a residency promise. Clients and partner managers will reject a tool that cannot show an audit pack or a bid sheet in the firm's current formats.

## This quarter

1. Stand up one Devin trial on a modernization slice or an accompanied time-and-materials team. The SOW keeps the firm's peer review and change control, names who may merge, and caps Agent Compute Units.
2. Stand up one Synlynk trial on a dedicated pod, or on a regulated on-premises slice locked to the local harness. Unattended scheduling stays off. Status for the steerco comes from GitHub, not from the job label.
3. Give both trials the same scorecard: cycle time, escaped defects, review compliance, gross margin after the meter, and any client-IP incident. Do not sign a factory rollout or a gainshare from either result.

## Limits of this review

The panel is three harnesses. Claude did not participate. Codex sat on `gpt-5.6-luna` because `gpt-5.6-terra` was at capacity. Members disagreed by two or more points on staff augmentation, fixed price, modernization, the factory, and regulated delivery. Those ranges are in the table so a single synthesized number is not mistaken for consensus. The evidence pack was the public Devin record as of 19 October 2026 and an inspection of this repository, including the 16 October architecture review. No client pilot was run for this brief.
