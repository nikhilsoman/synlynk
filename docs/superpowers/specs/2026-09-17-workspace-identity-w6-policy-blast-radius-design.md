# Workspace identity W6 — Policy, blast radius, receipts, connector inject firewall

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): `can_merge` = canonical `kind: qa` only; disjoint self-merge is a runtime grant; product-store policy wins; connector firewall is inject-time (no proxy); receipts are the existing gate chain. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W1, W5, W8  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0 locked who may merge and that GitHub auto-merge stays **off**. W8 locked packs, type id ≠ kind (`director` is `pm`), and `connector` allowlists. Today `.synlynk/policy.json` is **per repo** and `can_merge: ["qa"]` is a string with no product, no kind/type split, and no disjoint predicate.

Without W6, a studio `edit` App with GitHub write can merge, two vdowrx repos can disagree on merger, and a `figma` connector secret can leak into a `qa` worker.

W6 makes the merge table and connector allowlist **enforceable** at **product** scope. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| `can_merge` | Canonical **type** of `kind: qa` only (type id `qa` in all three W8 packs) |
| Disjoint self-merge | Runtime grant, **not** a second policy list |
| Policy home | Product store wins; repo file is git copy / pointer |
| Connector firewall | Inject-time at dispatch; **no** synlynk proxy |
| Receipts | Existing chain (`pr check`, qa-gate, `check-merge`, T5 instruction receipt, non-author review). No `receipts.sqlite` |
| Policy edits | Human (pm may propose). **Workers never write** product `policy.json` |
| GitHub auto-merge | Stays **off** (W0) |

---

## 3. Policy layout

```
~/.synlynk/workspaces/<product>/policy.json    # source of truth
<repo>/.synlynk/policy.json                    # git-visible copy / pointer
```

`synlynk policy check-merge` reads the **product** file (via `identity_slug`). If repo and product files disagree: **product wins**, doctor **warns**.

Policy is not a secret. W4 may sync it to members without handing out PEMs or connector `secret` files.

---

## 4. Merge authority

### 4.1 `can_merge`

Lists the **canonical type id** of `kind: qa`. In `software-product`, `studio`, and `agency` that id is `qa` (labels QA / QC / Proof).

Forbidden in this list: `director`, `production`, `dop`, `edit`, `frontend-qa`, `figma`, `partner`, any `connector` type.

`policy check-merge --role <type-id>` resolves type → kind:

- `--role qa` → may pass (canonical qa).
- `--role director` → **fail** (kind `pm`).
- `--role frontend-qa` → **fail** `can_merge` (specialist). May still pass the **disjoint grant** (§4.3) if that predicate is true.

GitHub merge/`administration` permission is requested only for the canonical `qa` App (today’s dynamic manifest vs `can_merge`). Specialists may have `pull_requests: write` for **review**, not train merge.

### 4.2 Trains (linked / overlapping PRs)

Workers of any `kind: qa` type (canonical or specialist) **review only**.

Merge is a **follow-up** job as canonical product `qa` (or Home as that type) when the graph is green. One merge government per product.

### 4.3 Disjoint self-merge (scoped grant)

A worker may squash-merge **its own** PR as itself iff **all** of:

1. Type’s `kind` is `qa`
2. No file overlap with other open PRs **in this product** (all constituent repos)
3. PR is not on a linked train
4. qa-gate + CI green
5. `synlynk pr check` passes
6. `synlynk policy check-merge --role <that-type>` passes the **grant** (not the `can_merge` list)
7. Non-author review rule satisfied (qa App vs author; #423 comment-checklist only on same-identity collision)

This grant is **not** a `can_merge_disjoint` YAML list. Encoding it as a list invites `kind: connector` by accident.

### 4.4 Reserved human merges

Spec sign-off, irreversible release, new kind, and `can_merge` / reserved-gate **policy edits**: human member. pm may propose; workers do not merge these.

---

## 5. Receipts

No new store. Refuse the act if the evidence is missing (job log, PR checks, instruction receipt).

| Act | Receipt |
|:---|:---|
| Train merge | Canonical `qa` job + green graph + qa-gate+CI + `pr check` + `check-merge --role qa` + non-author review |
| Disjoint self-merge | Same gates + overlap/train predicate **false** |
| Connector dispatch | Allowlist non-empty + known protocol + secret present; instruction pack **includes** the allowlist (T5-family receipt if ignored) |
| Policy edit | Human |

Workers **never** write `~/.synlynk/workspaces/<product>/policy.json`.

---

## 6. Connector blast radius (inject-time)

Allowlists and secrets stay on the **type** (W8 `connectors/<type>/`). Policy states **laws**, not host lists.

At `dispatch` of a `connector` type:

1. Allowlist non-empty or **refuse**.
2. Protocol in the known enum (`api_key`, `bearer_token`, `basic`, `oauth`, `gateway`) or **refuse**.
3. Secret injected only into **that** worker (env or temp file).
4. Instruction pack contains the allowlist.
5. Non-connector types **never** receive connector secrets.

No synlynk-owned HTTP/MITM proxy. Enterprise DLP/proxy may sit in front later without changing type identity.

`gateway` protocol: still type allowlist + inject; no vendor SDK in this spec (W8).

---

## 7. `policy.json` (illustrative, not a schema freeze)

```json
{
  "schema_version": 1,
  "product": "hitchcock",
  "merge_authority": {
    "can_merge": ["qa"],
    "require_non_authoring_review": true,
    "review_fallback": "same_identity_comment_checklist"
  },
  "release_authority": {
    "can_cut_release": ["pm"],
    "requires_human_approval": true
  },
  "connector_authority": {
    "require_allowlist": true,
    "inject_secret_only_to_type": true,
    "unknown_protocol": "fail"
  }
}
```

`can_cut_release: ["pm"]` means **kind** `pm` (studio type id `director`). Implementation resolves kind → canonical type. Host allowlists do **not** belong in this file.

Repo copy may omit secrets-adjacent fields; it must not invent a second `can_merge`.

---

## 8. Doctor / CLI

| Condition | Result |
|:---|:---|
| Product policy missing while repo policy exists | Warn; treat repo as migrate-from until copied |
| Product vs repo `can_merge` differ | Warn; product wins |
| `can_merge` contains a type whose kind is not `qa` | **Fail** |
| `can_merge` contains a non-canonical qa specialist | **Fail** |
| `check-merge --role director` for a train merge | **Fail** |
| Connector dispatch, empty allowlist | **Fail** |
| Worker process writes product `policy.json` | **Fail** / refuse (when implemented) |

---

## 9. Non-goals (W6)

- Outbound proxy / DLP product
- Vendor connector SDKs (W8 `gateway` slot)
- Signed receipt object store
- Moving `state.db` (W2)
- Vizor organigram UI (W8)
- Closing #914
- Implementation of `check-merge` kind resolution (plan after this spec is on `main`)

---

## 10. Success

- hitchcock: `check-merge --role director` cannot merge a train; `--role qa` can.
- `frontend-qa` cannot be added to `can_merge`; it may disjoint-self-merge only when the predicate is true.
- Two vdowrx repos cannot silently disagree: product `policy.json` wins.
- `figma` secret is not in the env of a `qa` worker.
- Empty connector allowlist refuses dispatch.
- GitHub auto-merge remains unused.

---

## 11. Test plan (when implemented; not this PR)

- Unit: kind resolution for `director` vs `qa`; `can_merge` rejects non-qa kinds; disjoint predicate true/false; product policy beats repo; connector inject isolation; empty allowlist refuse.
- No live GitHub merge in unit tests.
