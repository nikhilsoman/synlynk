# Wave 1 — Product store for GitHub Apps and types

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store GitHub App PEMs and type registry on the **product** path `~/.synlynk/workspaces/<identity_slug>/`, fail-closed on a second App for the same `(product, type)`, and make doctor/dispatch/worktrees use **absolute** product paths.

**Architecture:** Add `synlynk/product_store.py` as the single path resolver (`identity_slug` from `.synlynk/config.json`, else repo basename slug). Point `team._role_app_dir`, `dispatch._resolve_github_apps_dir`, and doctor at that resolver. Keep a **read fallback** to repo `.synlynk/github_apps/` so unmigrated dogfood does not go dark; **writes** always go to the product store. Seed `types.yaml` from `synlynk/packs/software-product.yaml` on first init of a canonical type.

**Tech Stack:** Python 3.10+ stdlib, pytest, existing GitHub App manifest flow in `synlynk/team.py`.

**Specs:** W1, W5 §4.4 empty-store canonical seed, W7 doctor fail row for missing product App material.

**Out of this wave:** relay, members, Vizor organigram, Linear, `state.db` move, studio pack runtime, connector secrets.

**Constraints:** Never commit `main`. Worktree `feat/codex/914-wave1-product-store`. TDD. No live GitHub App create in unit tests. Co-Authored-By: Codex. Route GitHub writes (PR open) to Codex `--requires-gh-write`.

---

### Task 1: Product path resolver

**Files:**
- Create: `synlynk/product_store.py`
- Test: `tests/test_product_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_product_store.py
import json
from pathlib import Path

from synlynk.product_store import (
    github_apps_dir,
    identity_slug_from_config,
    product_root,
    types_yaml_path,
)


def test_identity_slug_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    syn = tmp_path / ".synlynk"
    syn.mkdir()
    (syn / "config.json").write_text(json.dumps({"identity_slug": "vdowrx"}))
    assert identity_slug_from_config(tmp_path) == "vdowrx"


def test_identity_slug_falls_back_to_dirname(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    assert identity_slug_from_config(tmp_path) == tmp_path.name


def test_product_paths_use_home_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = product_root("vdowrx")
    assert root == Path(tmp_path / "home" / ".synlynk" / "workspaces" / "vdowrx")
    assert github_apps_dir("vdowrx") == root / "github_apps"
    assert types_yaml_path("vdowrx") == root / "types.yaml"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_product_store.py -v
```

Expected: FAIL `ModuleNotFoundError: synlynk.product_store`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/product_store.py
"""Product-scoped paths (W1/W5). Keyed by identity_slug, not git worktree cwd."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def identity_slug_from_config(repo_path: PathLike = ".") -> str:
    repo = Path(repo_path).resolve()
    cfg_path = repo / ".synlynk" / "config.json"
    slug = None
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        raw = data.get("identity_slug")
        if isinstance(raw, str) and raw.strip():
            slug = raw.strip()
    if not slug:
        slug = repo.name
    return _slugify(slug)


def product_root(slug: str) -> Path:
    return Path(os.path.expanduser("~")) / ".synlynk" / "workspaces" / slug


def github_apps_dir(slug: str) -> Path:
    return product_root(slug) / "github_apps"


def types_yaml_path(slug: str) -> Path:
    return product_root(slug) / "types.yaml"


def types_dir(slug: str) -> Path:
    return product_root(slug) / "types"


def ensure_product_dirs(slug: str) -> Path:
    root = product_root(slug)
    github_apps_dir(slug).mkdir(parents=True, exist_ok=True)
    types_dir(slug).mkdir(parents=True, exist_ok=True)
    return root
```

- [ ] **Step 4: Run tests and make sure they pass**

```bash
python3 -m pytest tests/test_product_store.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/product_store.py tests/test_product_store.py
git commit -m "feat: product store path resolver for identity_slug

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 2: Resolve App dir — product first, repo fallback

**Files:**
- Modify: `synlynk/product_store.py` (add `resolve_github_apps_dir`)
- Modify: `synlynk/dispatch.py` (`_resolve_github_apps_dir`)
- Modify: `synlynk/team.py` (`_role_app_dir`)
- Test: `tests/test_product_store.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_product_store.py
from synlynk.product_store import resolve_github_apps_dir


def test_resolve_prefers_product_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    product_apps = github_apps_dir("vdowrx")
    product_apps.mkdir(parents=True)
    (product_apps / "qa.json").write_text("{}")
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text("{}")
    assert resolve_github_apps_dir(tmp_path) == product_apps


def test_resolve_falls_back_to_repo_apps(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text("{}")
    assert resolve_github_apps_dir(tmp_path) == repo_apps
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_product_store.py::test_resolve_prefers_product_store -v
```

Expected: FAIL `ImportError` or `AttributeError: resolve_github_apps_dir`

- [ ] **Step 3: Write minimal implementation**

Add to `synlynk/product_store.py`:

```python
def resolve_github_apps_dir(repo_path: PathLike = ".") -> Path:
    """Prefer product store if it has any App json; else repo .synlynk/github_apps."""
    slug = identity_slug_from_config(repo_path)
    product_apps = github_apps_dir(slug)
    if any(product_apps.glob("*.json")):
        return product_apps
    repo_apps = Path(repo_path).resolve() / ".synlynk" / "github_apps"
    if repo_apps.is_dir():
        return repo_apps
    return product_apps
```

Change `synlynk/team.py` `_role_app_dir`:

```python
def _role_app_dir() -> Path:
    from synlynk.product_store import resolve_github_apps_dir
    return resolve_github_apps_dir(".")
```

Change `synlynk/dispatch.py` `_resolve_github_apps_dir` to:

```python
def _resolve_github_apps_dir() -> str:
    from synlynk.product_store import resolve_github_apps_dir
    return str(resolve_github_apps_dir("."))
```

Keep worktree behavior by resolving `identity_slug` from repo `config.json` (copied or inherited). If worktree has no config, walk to git common dir **only to read config.json**, never to require PEMs under the worktree.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_product_store.py tests/test_identity_list.py tests/test_identity_init_role_token_seed.py -v
```

Expected: PASS, or update fixtures that assume cwd `.synlynk/github_apps` **writes** — those tests should set `HOME` and `identity_slug`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/product_store.py synlynk/team.py synlynk/dispatch.py tests/test_product_store.py
git commit -m "feat: resolve GitHub App dir from product store

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 3: Writes go to product store; second App fail-closed

**Files:**
- Modify: `synlynk/team.py` (`cmd_identity_init_role`, `_role_app_dir` for writes)
- Test: `tests/test_product_store.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from synlynk.product_store import github_apps_dir, write_apps_dir_for_init
from synlynk.team import IdentityAlreadyProvisioned, cmd_identity_init_role


def test_write_apps_dir_is_always_product(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    d = write_apps_dir_for_init(".")
    assert d == github_apps_dir("vdowrx")
    assert d.is_dir()


def test_second_init_raises_when_product_app_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    apps = github_apps_dir("vdowrx")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({
        "app_id": 1,
        "installation_id": 2,
        "app_slug": "synlynk-vdowrx-qa",
        "private_key_path": str(apps / "qa.pem"),
    }))
    (apps / "qa.pem").write_text("dummy")
    with pytest.raises(IdentityAlreadyProvisioned):
        cmd_identity_init_role("qa")
```

Do **not** call the live GitHub manifest in this test. `cmd_identity_init_role` must raise **before** opening a browser if product material exists (including when cwd is a **different clone** with the same `identity_slug`).

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_product_store.py::test_second_init_raises_when_product_app_exists -v
```

Expected: FAIL (function still writes under repo or returns print-and-return)

- [ ] **Step 3: Write minimal implementation**

In `synlynk/product_store.py`:

```python
def write_apps_dir_for_init(repo_path: PathLike = ".") -> Path:
    slug = identity_slug_from_config(repo_path)
    ensure_product_dirs(slug)
    return github_apps_dir(slug)
```

In `synlynk/team.py`:

```python
class IdentityAlreadyProvisioned(RuntimeError):
    """W1: never mint a second App for (product, type)."""


def cmd_identity_init_role(role: str, project=None) -> None:
    from synlynk.product_store import write_apps_dir_for_init
    app_dir = write_apps_dir_for_init(".")
    json_path = app_dir / f"{_role_slug(role)}.json"
    pem_path = app_dir / f"{_role_slug(role)}.pem"
    if json_path.exists():
        raise IdentityAlreadyProvisioned(
            f"type exists; add this repo to the installation instead ({json_path})"
        )
    # existing manifest flow, but app_dir/json_path/pem_path as above
```

Preserve the **resume install confirmation** path only when json exists **without** `installation_id` (partial create). That is not a second App.

CLI: catch `IdentityAlreadyProvisioned`, print the message, `sys.exit(1)`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_product_store.py tests/test_identity_init_role_token_seed.py -v
```

Expected: PASS. Update seed tests to use `HOME` + product path.

- [ ] **Step 5: Commit**

```bash
git commit -m "fix: identity init writes product store and refuses second App

Co-Authored-By: Codex <noreply@openai.com>"
```

---

### Task 4: Doctor fail-closed on product App material

**Files:**
- Modify: `synlynk/doctor.py` (identity json/pem checks ~208–252)
- Test: `tests/test_doctor_product_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor_product_store.py
import json
import os
from synlynk.doctor import _hc_identity_file_perms, _hc_identity_roles
from synlynk.product_store import github_apps_dir


def test_doctor_ok_when_pem_only_in_product_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "synlynk"})
    )
    apps = github_apps_dir("synlynk")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"installation_id": 1}))
    (apps / "qa.pem").write_text("k")
    os.chmod(apps / "qa.json", 0o600)
    os.chmod(apps / "qa.pem", 0o600)
    monkeypatch.setattr(
        "synlynk.identity_roles.load_declared_roles", lambda: ["qa"]
    )
    perms = _hc_identity_file_perms()
    roles = _hc_identity_roles()
    assert perms.status == "ok"
    assert roles.status == "ok"
```

Point `_hc_identity_roles` and `_hc_identity_file_perms` (`synlynk/doctor.py` ~201–253) at `resolve_github_apps_dir(".")`.

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_doctor_product_store.py -v
```

- [ ] **Step 3: Implement** — replace hardcoded `.synlynk/github_apps` in `doctor.py` with `str(resolve_github_apps_dir("."))`. Missing product material for durable `qa`/`pm`/`tpm` when `gh_write` is required → **fail** (existing #1630 spirit).

- [ ] **Step 4: Run**

```bash
python3 -m pytest tests/test_doctor_product_store.py tests/test_synlynk.py -k hc_identity -v
```

- [ ] **Step 5: Commit** `fix: doctor reads GitHub App material from product store`

---

### Task 5: One-shot migrate copy (no dual-App merge)

**Files:**
- Modify: `synlynk/product_store.py` (`migrate_repo_apps_if_needed`)
- Test: `tests/test_product_store.py`

- [ ] **Step 1: Failing test**

```python
def test_migrate_copies_repo_apps_when_product_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text("{}")
    (repo_apps / "qa.pem").write_text("k")
    from synlynk.product_store import migrate_repo_apps_if_needed, github_apps_dir
    migrate_repo_apps_if_needed(".")
    assert (github_apps_dir("vdowrx") / "qa.pem").read_text() == "k"


def test_migrate_does_not_overwrite_product(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    from synlynk.product_store import github_apps_dir, migrate_repo_apps_if_needed
    dest = github_apps_dir("vdowrx")
    dest.mkdir(parents=True)
    (dest / "qa.json").write_text('{"app_id": 9}')
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text('{"app_id": 1}')
    migrate_repo_apps_if_needed(".")
    assert json.loads((dest / "qa.json").read_text())["app_id"] == 9
```

- [ ] **Step 2: pytest fails on missing `migrate_repo_apps_if_needed`**
- [ ] **Step 3: Implement copytree of `*.json`/`*.pem` only if destination file missing.** Call from `cmd_identity_init_role` and doctor (once). **Do not** delete the repo copy in this wave (W1 §7 step 4).
- [ ] **Step 4: pytest pass**
- [ ] **Step 5: Commit** `feat: copy repo github_apps into product store if empty`

---

### Task 6: `software-product` pack + types.yaml seed

**Files:**
- Create: `synlynk/packs/software-product.yaml`
- Create: `synlynk/types_registry.py`
- Test: `tests/test_types_registry.py`
- Modify: `synlynk/cli.py` (subcommand `type create`)

Pack file:

```yaml
id: software-product
spine_kinds: [pm, tpm, architect, qa]
types:
  pm: {kind: pm, canonical: true, label: PM}
  tpm: {kind: tpm, canonical: true, label: TPM}
  architect: {kind: architect, canonical: true, label: Architect}
  qa: {kind: qa, canonical: true, label: QA}
  dev: {kind: dev, canonical: true, label: Dev}
  designer: {kind: designer, canonical: true, label: Designer}
  marketing: {kind: marketing, canonical: true, label: Marketing}
  synlynk-bot: {kind: synlynk-bot, canonical: true, label: synlynk-bot}
```

- [ ] **Step 1: Tests**

```python
# tests/test_types_registry.py
import json
from pathlib import Path

from synlynk.types_registry import (
    seed_canonical_types,
    type_create,
    load_types,
    TypeExists,
    UnknownKind,
)


def test_seed_software_product(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "synlynk"})
    )
    seed_canonical_types("synlynk", pack_id="software-product")
    types = load_types("synlynk")
    assert types["qa"]["kind"] == "qa"
    assert types["qa"]["canonical"] is True
    charter = tmp_path / "home" / ".synlynk" / "workspaces" / "synlynk" / "types" / "qa" / "charter.md"
    assert charter.is_file()


def test_type_create_frontend_qa(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    seed_canonical_types("vdowrx", pack_id="software-product")
    type_create("vdowrx", type_id="frontend-qa", kind="qa")
    types = load_types("vdowrx")
    assert types["frontend-qa"]["kind"] == "qa"
    assert types["frontend-qa"]["canonical"] is False


def test_type_create_rejects_duplicate_and_unknown_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    seed_canonical_types("vdowrx", pack_id="software-product")
    import pytest
    with pytest.raises(TypeExists):
        type_create("vdowrx", type_id="qa", kind="qa")
    with pytest.raises(UnknownKind):
        type_create("vdowrx", type_id="colorist", kind="not-a-kind")
```

Approved kinds for Wave 1 = keys in the software-product pack plus `infra` if present in `charter_schema.KNOWN_ROLES`. Do not load studio kinds yet.

- [ ] **Step 2: pytest fails**
- [ ] **Step 3: Implement YAML load via `yaml` **only if already a dependency**; otherwise parse a **minimal** subset with `json` by shipping `software-product.json` **or** use stdlib — grep `PyYAML` in `pyproject.toml`. If no YAML lib, ship `synlynk/packs/software-product.json` and still name the spec file `.yaml` in a later wave. Prefer json in Wave 1 if yaml is not a dependency (YAGNI).
- [ ] **Step 4: pytest pass**
- [ ] **Step 5: Commit** `feat: software-product type registry seed and type create`

CLI wiring: `synlynk type create <id> --kind <kind>` → `type_create`; no GitHub calls. `sys.exit(1)` on `TypeExists` / `UnknownKind`.

---

### Task 7: `identity init --type` requires type row (canonical seed exception)

**Files:**
- Modify: `synlynk/team.py` `cmd_identity_init_role`
- Modify: `synlynk/cli.py` accept `--type` as alias of `--role`
- Test: `tests/test_product_store.py`

- [ ] **Step 1: Tests**

```python
def test_init_unknown_specialist_fails_without_type_create(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"})
    )
    from synlynk.team import UnknownType, cmd_identity_init_role
    import pytest
    with pytest.raises(UnknownType):
        cmd_identity_init_role("frontend-qa")


def test_init_canonical_seeds_types_then_would_write_apps_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"identity_slug": "synlynk"})
    )
    from synlynk.types_registry import load_types
    from synlynk.team import ensure_type_for_identity_init
    ensure_type_for_identity_init("qa")
    assert load_types("synlynk")["qa"]["canonical"] is True
```

- [ ] **Step 2: pytest fail**
- [ ] **Step 3:** `ensure_type_for_identity_init(type_id)`: if no `types.yaml`, `seed_canonical_types` then continue **only if** `type_id` is canonical in that pack; else `UnknownType`. If `types.yaml` exists and id missing → `UnknownType` (no implicit frontend-qa).
- [ ] **Step 4: pytest pass**
- [ ] **Step 5: Commit** `feat: identity init seeds canonical types and refuses unknown specialists`

---

### Task 8: Regression + blog line

**Files:**
- Modify: `docs/blog/203-prTBD-914-w0-vocabulary.md` only if this wave is the same PR; **Wave 1 code PR gets its own blog post** `docs/blog/204-prTBD-914-wave1-product-store.md` per blog protocol.
- Run: full `python3 -m pytest tests/test_product_store.py tests/test_types_registry.py tests/test_doctor_product_store.py tests/test_identity_list.py tests/test_identity_init_role_token_seed.py tests/test_gh_role.py -v` plus a broader `pytest tests/test_dispatch.py tests/test_doctor.py -q` if those files exist.

- [ ] **Step 1:** Author `docs/blog/204-prTBD-914-wave1-product-store.md` from `docs/blog/README.md` template (goal going in, shift, what shipped, new goalpost).
- [ ] **Step 2:** `python3 -m pytest` on the files above; 0 fails.
- [ ] **Step 3:** Comment on GitHub issue #914: Wave 1 PR link; #914 remains OPEN.
- [ ] **Step 4:** Open PR with Summary + Test plan. Do not merge; qa App reviews.
- [ ] **Step 5:** Commit blog with the code branch.

---

## Self-review (Wave 1 vs specs)

| Spec requirement | Task |
|:---|:---|
| W1 product PEM path | 1–3, 5 |
| W1 fail-closed second App | 3 |
| W1 worktree absolute PEM | 2 (product store, not worktree relative) |
| W1 doctor product material | 4 |
| W1 no state.db move | not in this wave |
| W5 types.yaml + type create | 6 |
| W5 empty store + canonical seed | 7 |
| W5 specialist never implied | 7 |
| W8 packs | software-product data only (6) |
| W4/W9/Linear/Board | excluded |

No `TBD` implementation steps. Live GitHub App create remains the existing `_build_app_manifest_url` path after fail-closed checks; unit tests never hit the network.
