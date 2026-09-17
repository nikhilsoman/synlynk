# Workspace identity W8 — Industry packs, onboarding organigram, connectors

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): three shipped packs; Vizor organigram onboard; expansion never frozen; `connector` kind catalog-only; product-store connector creds; `gateway` protocol slot with no vendor default. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W1, W5  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W5 says how a type is stored and born (`type create` then `identity init`). It still assumed every product’s canonical set is the **synlynk software eight**, and it never mentioned Vizor.

That is false for hitchcock (synthetic **studio**) vs rxcc/vdowrx (**software-product**), and it leaves no room for a marketing/sales **agency**. Today’s CLI wizard seeds eight charters in &lt;5s; Vizor `/onboarding/roles` 1-click mints a **hardcoded** role list. Both must survive; the hardcoded list must not.

W8 is packs + discovery + organigram + post-onboard expansion + outbound connectors. **GitHub App minting stays in onboarding.** No code in this file. **#914 stays OPEN.**

Approving this spec is the reserved human sign-off for the new **kinds** it ships (`edit`, `color`, `script`, `sound`, `account`, `creative`, `media`, `research`, `connector`). Further kinds still need architect charter + a later reserved sign-off.

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Packs this epic | `software-product`, `studio`, `agency` — YAML in the synlynk package, extensible by adding a file |
| Spine | Every pack includes kinds `pm`, `tpm`, `architect`, `qa` (`qa` is the only `can_merge`) |
| Type id vs kind vs label | Type id = App + `--role`; kind = law; label = organigram sticker, editable, no remint |
| Hitchcock pack | `studio` (production org; gen-AI is how types run, not extra kinds) |
| Onboard | CLI probe, then **Vizor organigram** (LLM propose → revise → confirm mint) |
| Headless | `--pack <id> --yes` skips LLM, mints pack defaults |
| Expansion | Never frozen after onboard |
| Home + reach | Chosen at every add/onboard confirm (W1 install surface) |
| Outbound kind | `connector` — catalog-only, not in pack default lists |
| Connector secrets | Product store, parallel to PEMs (W1 A now / C at Teams) |
| Aggregators | Protocol `gateway` slot; **no** vendor default; no decide panel in this PR |

---

## 3. Kind vs type id vs label

| Layer | Stable? | Example (`studio`) |
|:---|:---|:---|
| **Kind** | Yes — policy, review laws, `can_merge` | `pm` |
| **Type id** | Frozen at mint | `director` → `synlynk-hitchcock-director[bot]`, `--role director` |
| **Label** | Editable on organigram | “Director” → “Showrunner” without remint |

`--kind pm` may alias to the product’s canonical type of that kind. Renaming a **type id** after mint is a migrate, not an onboard click.

---

## 4. Packs (shipped in this epic)

Files: `synlynk/packs/<id>.yaml` (illustrative path). Adding a fourth pack is a new file + Vizor label, not an identity-stack change.

**Spine type ids differ by pack; kinds do not.**

### 4.1 `software-product`

Dogfood: synlynk, rxcc, vdowrx, playblazer, …

| Kind | Type id | Default label |
|:---|:---|:---|
| `pm` | `pm` | PM |
| `tpm` | `tpm` | TPM |
| `architect` | `architect` | Architect |
| `qa` | `qa` | QA |
| `dev` | `dev` | Dev |
| `designer` | `designer` | Designer |
| `marketing` | `marketing` | Marketing |
| `synlynk-bot` | `synlynk-bot` | synlynk-bot |
| `infra` | `infra` | Infra |

`infra` only if already treated as canonical in this repo; omit from mint if the pack file marks it optional.

### 4.2 `studio` (hitchcock)

Synthetic studio: organigram is a production company.

| Kind | Type id | Default label |
|:---|:---|:---|
| `pm` | `director` | Director |
| `tpm` | `production` | Production |
| `architect` | `dop` | DoP |
| `qa` | `qa` | QC |
| `edit` | `edit` | Edit |
| `color` | `color` | Color |
| `script` | `script` | Script |
| `sound` | `sound` | Sound |
| `marketing` | `marketing` | Marketing |

Pipeline stages (ingest / generate / deliver) are context packs and tools, not kinds.

### 4.3 `agency`

Digital marketing/sales knowledge-worker org. No current dogfood repo required.

| Kind | Type id | Default label |
|:---|:---|:---|
| `pm` | `partner` | Partner |
| `tpm` | `traffic` | Traffic |
| `architect` | `strategy` | Strategy |
| `qa` | `qa` | Proof |
| `account` | `account` | Account |
| `creative` | `creative` | Creative |
| `media` | `media` | Media |
| `research` | `research` | Research |

No extra `marketing` kind (would duplicate `creative`).

Default is **one canonical type per pack kind** (type id as above). Extra specialists later via `type create` (W5). Organigram may **deselect** a pack type so it is not minted.

---

## 5. Onboarding

1. CLI wizard still probes harnesses, `identity_slug`, repos (fast, local). It does **not** silently seed eight software charters when the product is not `software-product`.
2. Opens Vizor: intent/workflow text → LLM proposes **pack + organigram** (humans + types, spine vs pack kinds, labels).
3. A few explain/revise rounds: change pack, relabel, drop a type, add a type under an **approved** kind, set home + reach.
4. Confirm → W5 pack seed / `type create` **then** `identity init --type` for every **selected** type. `/onboarding/roles` becomes “mint this organigram,” not “mint these six names.”
5. Organigram remains a standing Vizor view (kind, type id, label, App minted/missing, home, reach). Architect Map stays **repos**.

LLM may only propose kinds **in the catalog**. Confirming the picture is not a new-kind constitution.

**Headless / CI:** `synlynk init --wizard --pack software-product --yes` (hitchcock: `--pack studio`). Skips LLM; mints pack defaults.

**Solo:** organigram is the operator + types. Teammates are W4.

**Minting stays in onboarding.** Two-step is internal. The human leaves onboard with GitHub Apps for the agreed set.

---

## 6. Expansion (never frozen)

Onboarding is the first organigram, not the last. PM or human admin may later add types: charter, skill/tool delta, durability (standing vs dispatch-only), work scope, GitHub **home repo** and **reach** (that repo / explicit list / all product repos).

Spine types still *default* to all product repos so trains can merge; the human may narrow. Specialists and connectors default to one home repo (W0/W1).

**New kinds** remain gated. Expanding the **set of types** is not gated beyond PM/admin. Different products diverge on purpose.

Each add uses the same Vizor sheet as onboard confirm (home + reach + labels + durability). Then W5 two-step + mint if GitHub writes are required.

---

## 7. `connector` kind

Catalog-only. Not in the three pack default lists. Add from the organigram or a tool stub.

Job: talk to **one** outside system (Figma, Stitch, Blender, Stripe, …) with an **allowlist**. Not “anyone who uses web search” — pm/qa still research under normal policy.

| | Other kinds | `connector` |
|:---|:---|:---|
| Egress | Default harness tools | Allowlisted MCP/API/hosts only; deny the rest |
| `can_merge` | Per W0 (`qa` only) | Never, including via skill delta |
| Default durability | Per pack | Dispatch-triggered unless admin sets durable |
| Allowlist | — | **Required.** Empty allowlist → fail closed |

Types: `figma`, `stitch`, `blender`, … each `kind: connector`, own App, charter, home, reach, allowlist, credentials.

W6 owns the firewall **engine** (blast radius, receipts). W8 names the kind, allowlist field, and fail-closed empty list.

### 7.1 Credentials (product store)

```
~/.synlynk/workspaces/<product>/
  github_apps/<type>.{json,pem}
  connectors/<type>/
    credentials.json          # protocol, metadata, expiry — avoid embedding secrets
    secret                    # chmod 600, or OS keychain handle
```

- Vizor write-only secret fields; never echo back in full.
- Dispatch as **that type only** gets injection (env or temp file). Other types do not see it.
- Workers do not persist secrets. Swarm: job-scoped handoff, not the long-lived key (same as W1 token handoff).
- **Protocols this epic:** `api_key`, `bearer_token`, `basic`, `oauth`, `gateway`. Unknown protocol id → fail closed until implemented.
- `passkey` and further enterprise protocols: named extensions, no redesign.
- Teams/W4: members do not copy connector secrets; daemon injects (approach C analogue).

### 7.2 `gateway` protocol (no vendor default)

Aggregators (Zapier MCP, Arcade, Composio, n8n) are **not** the identity layer.

`gateway` payload (illustrative): `{ "protocol": "gateway", "provider": "composio"|"arcade"|"n8n"|"zapier"|<open>, "account_handle": "..." }`. Allowlist still lives on the **type**.

A Figma type may be `direct` **or** `gateway`. A product may also have one long-tail gateway connector.

**This epic does not implement any vendor SDK** and does **not** set a default `provider`. Run `synlynk decide --panel` on default provider in the **implementation** plan for connectors, not in this docs PR.

### 7.3 Tool → type stub

A tool/add-on manifest **may** declare `provisions_type: { kind: connector, type_id: figma, label: Figma }` (illustrative). Vizor shows the same add-type sheet. **No silent mint.** Implementation of the installer can be empty besides accepting the field.

---

## 8. Relation to W5

W5 store, two-step CLI, kind-inherit skill deltas, memory path — unchanged.

**Amended:** “canonical eight” are **canonical for this product, from its pack**. Empty-store `identity init --type director` with `--pack studio` (or product already on `studio`) seeds that pack then mints. `identity init --type frontend-qa` still fails without `type create`. `identity init --type figma` fails unless `connector` type exists.

Solo software dogfood: `--pack software-product` (default when scan looks like a software repo) restores today’s eight.

---

## 9. Doctor (extends W1/W5)

| Condition | Result |
|:---|:---|
| Selected canonical type, `gh_write` required, no App | **Fail** |
| `connector` type, empty allowlist | **Fail** |
| `connector` type, unknown protocol | **Fail** |
| `connector` type, no secret when protocol requires one | **Fail** if that type is dispatched outbound; **warn** if never dispatched |
| Pack id unknown on `--pack` | **Fail** |
| Organigram type id rename after mint without migrate | **Fail** / refuse |

---

## 10. Non-goals (W8)

- Implementing wizard, Vizor organigram, LLM rounds, or `synlynk type` in this docs PR
- Vendor SDKs (Arcade/Composio/Zapier/n8n)
- Firewall engine, swarm write receipts — **W6**
- Member sync of charters/creds — **W4**
- Closing #914
- Decide panel on default gateway provider (implementation plan)

---

## 11. Success

- hitchcock onboard with `--pack studio` (or LLM→studio) mints `director` / `production` / `dop` / `qa` / … not `pm` as the GitHub actor; reviews can show `synlynk-hitchcock-director[bot]`.
- synlynk/rxcc onboard still mints `pm`/`qa`/… ; no fake `edit` type.
- Relabeling Director → Showrunner does not remint.
- After onboard, PM adds `figma` (`kind: connector`) with home repo, reach, allowlist, `oauth` or `gateway` creds; `qa` workers cannot read that secret.
- `--pack software-product --yes` in CI mints without Vizor.
- No Zapier/Arcade account is required to complete onboard.

---

## 12. Test plan (when implemented; not this PR)

- Unit: pack YAML load; spine present; type id ≠ kind for studio/agency; deselect skips mint; empty connector allowlist fails; unknown protocol fails; `--pack` unknown id fails.
- No live GitHub App or vendor OAuth in unit tests.
- Live (later): one studio pack on hitchcock **or** a throwaway slug; delete Apps if not kept.
