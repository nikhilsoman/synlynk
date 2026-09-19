# Design Spec: Vizor World View & Autonomous Opportunity Radar

- **Governing Goal:** [`goal-f0489be9`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md) (Establish Vizor World View as an inside-out projection of external integrations and autonomous opportunity radar)
- **Tracking Story:** [`story-2161a277`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (Exploration: Vizor World View Inside-Out Projection & Opportunity Radar Architecture)
- **Assigned Agents:** `pm` (Claude) + `architect` (Claude / Codex / Agy)
- **Status:** Approved Spec
- **Date:** 2026-09-19

---

## 1. Executive Summary & Vision

Modern software products do not exist in isolation. They are deeply embedded in an intricate web of external dependencies: payment processors, LLM APIs, identity providers, inbound webhooks, regulatory mandates, notification gateways, and data clearinghouses.

Currently, Vizor provides three essential "inside-the-fence" perspectives:
1. **Product View (UX / Journeys):** How users navigate screens, routes, and application flows.
2. **Logical View (Code / AST):** How modules, packages, and functions connect via Graphify call graphs.
3. **Infra View (Runtime / Compute):** How local daemons, background workers, worktrees, and ports operate.

The **World View** introduces a 4th fundamental perspective: an **inside-out projection** of the product relative to the external ecosystem. It begins with grounded, undeniable code truth (what the software directly touches today) and expands outward into an **autonomous opportunity radar** maintained collaboratively by the PM and Architect agents.

```
                            THE 4 VIZOR PERSPECTIVES
  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐
  │         1. PRODUCT VIEW         │   │         2. LOGICAL VIEW         │
  │    (UX / Journeys / Screens)    │   │    (AST / Modules / Symbols)    │
  └────────────────┬────────────────┘   └────────────────┬────────────────┘
                   │                                     │
                   ▼                                     ▼
         ┌─────────────────────────────────────────────────────┐
         │                  THE PRODUCT CORE                   │
         │                (Codebase & Runtime)                 │
         └─────────────────────────────────────────────────────┘
                   ▲                                     ▲
                   │                                     │
  ┌────────────────┴────────────────┐   ┌────────────────┴────────────────┐
  │          3. INFRA VIEW          │   │      4. WORLD VIEW (NEW)        │
  │  (Daemons / Worktrees / Ports)  │   │  (Inside-Out Ecosystem Radar)   │
  └─────────────────────────────────┘   └─────────────────────────────────┘
```

---

## 2. Core Architectural Policies & Principles

### A. The Universal Workspace Boundary Law
- **Strict Boundary Isolation:** Any service, API, or SDK outside the current workspace's repository boundary is formally classified as **External**.
- **Cross-Team Internal Services:** Even if a service or SDK belongs to the same enterprise or a sibling team (e.g. `@corp/auth-sdk`, internal billing microservice), it is treated as an external dependency from this product's architectural viewpoint.
- **Classification Taxonomy:**
  - `external_third_party`: Public vendor APIs (Stripe, OpenAI, Twilio, AWS S3, Auth0).
  - `external_team_internal`: Sibling team APIs/SDKs within the broader organization.

### B. Blast-Radius Criticality Scoring (User-Facing Reach)
Dependencies are stack-ranked and visually prioritized by their structural criticality:
$$\text{Criticality Score}(S) = \frac{\text{Count of User-Facing Routes / Journeys Traversing Service } S}{\text{Total User-Facing Routes}}$$
- **High Criticality ($>0.5$):** Core dependencies (e.g. Primary Auth IdP, Main Payment Gateway). Rendered with prominent node weight and highlighted connection lines.
- **Low Criticality ($<0.1$):** Peripheral dependencies (e.g. Asynchronous background logging, optional enrichment feeds). Rendered lightly.

---

## 3. Dual Visual Projection Engine

The World View provides two switchable rendering layouts in Vizor (`localhost:8585`), powered by the exact same underlying projection data in `workspace_view_nodes`:

```
    MODE A: CONCENTRIC RADAR (DEFAULT)                    MODE B: DIRECTED SEQUENCE FLOW (TOGGLE)
  ┌──────────────────────────────────────────┐          ┌──────────────────────────────────────────┐
  │              RING 3 (OPPORTUNITIES)      │          │  INBOUND        PRODUCT        OUTBOUND  │
  │        ┌────────────────────────┐        │          │ CHANNELS          CORE        PROVIDERS  │
  │        │    RING 2 (STANDBY)    │        │          │                                          │
  │        │   ┌────────────────┐   │        │          │ [GitHub App] ──> ┌──────┐ ──> [Stripe]   │
  │        │   │ RING 1 (TRUTH) │   │        │          │                  │ main │                │
  │        │   │   [ PRODUCT ]  │   │        │          │ [Slack Webhook]─>└──────┘ ──> [OpenAI]   │
  │        │   │     (Center)   │   │        │          │                                          │
  │        │   └────────────────┘   │        │          │                   ───────────────>       │
  │        └────────────────────────┘        │          │                   OPPORTUNITY HORIZON    │
  └──────────────────────────────────────────┘          └──────────────────────────────────────────┘
```

1. **Mode A: Concentric Radar Layout (Default):**
   - Epicenter: The Product Workspace $(0,0)$.
   - 360° Quadrants: North = Payments & FinTech, East = AI & LLM APIs, South = Auth & IdP, West = Inbound Webhooks & Channels.
   - Ring 1 (Inner): Live Code Truth (green nodes directly wired to source files).
   - Ring 2 (Middle): Configured / Standby SDKs and declared environment variables.
   - Ring 3 (Outer): Strategic Opportunities (pulsing violet blips from PM/Architect sweeps).
2. **Mode B: Directed Inside-Out Sequence Flow (Toggle):**
   - Horizontal pipeline visualizing how data flows through Inbound Channels $\to$ Routing Layers $\to$ Core Logic $\to$ Outbound External Services.
   - Thickness of connection links directly reflects the Graphify **User-Facing Criticality Score**.

---

## 4. Multi-Language Code-Truth Extractor

The extractor (`extract_world_nodes()` in `synlynk/viz_views.py`) deterministically scans Python, TypeScript/JavaScript, and Go:

| Category | Extraction Heuristic | Target Examples |
| :--- | :--- | :--- |
| **Outbound APIs & SDKs** | AST Import Matching + Regex Base URLs | `stripe`, `openai`, `anthropic`, `boto3`, `@sendgrid/mail`, `github.com/stripe/stripe-go` |
| **Inbound Webhook Channels** | Route Decorator & Listener AST | `@app.post("*/webhook*")`, `router.post("/events")`, `express.post("/hooks/*")` |
| **Identity & Auth Providers** | OAuth Handlers & JWT Parsers | GitHub OAuth, Google Sign-In, Auth0, Firebase Auth, Okta |
| **Data Enrichment & CDNs** | Config Endpoints & Feeds | GeoIP, TaxJar, Sentry, PostHog, Cloudflare S3 |
| **Compliance Boundaries** | Consent Controllers & Opt-Outs | Cookie consent toggles, GDPR data export endpoints |

---

## 5. Storage Schema Extension (`synlynk/viz_views.py`)

```sql
-- Projection table: workspace_view_nodes where view = 'world'
{
  "category": "payment_gateway",
  "boundary_type": "external_third_party", -- "external_third_party" | "external_team_internal"
  "tier": 1,                               -- 1: Code Truth, 2: Standby, 3: Opportunity
  "status": "active",                      -- "active", "standby", "proposed"
  "provider_name": "Stripe",
  "endpoint": "api.stripe.com",
  "sdk": "stripe-python",
  "source_file": "synlynk/billing.py",
  "criticality_score": 0.85,
  "user_path_reach": ["/checkout", "/subscription/upgrade", "/api/v1/pay"],
  "resilience": {
    "circuit_breaker": false,
    "fallback_provider": null,
    "spof_risk": "high"
  },
  "opportunity": {
    "proposed_by": "pm",
    "rationale": "Add Apple Pay / Google Pay button to reduce cart drop-off by 18%",
    "linked_story": null
  }
}
```

---

## 6. Verification & Acceptance Criteria

- [ ] **AC-1:** `extract_world_nodes()` extracts outbound APIs, webhooks, and IdPs with $<10\text{ms}$ scan time.
- [ ] **AC-2:** Vizor renders the Concentric Radar layout with active node drawer and 1-click `synlynk story create`.
- [ ] **AC-3:** Vizor renders the Directed Sequence Flow toggle layout with thickness scaled to criticality.
- [ ] **AC-4:** Graphify AST user-facing path reach calculates accurate criticality scores across multi-route apps.
