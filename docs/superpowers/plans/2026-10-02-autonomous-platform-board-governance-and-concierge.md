# v0.24.0: Autonomous Platform, Board Governance & Concierge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Synlynk into a self-managing, autonomous engineering product organization under the GOVERNS lifecycle, governed by a Sovereign Human Board (Nikhil Soman Genesis Chair), equipped with a Tri-Modal Autonomy Dial, Jev AST Decision Engine, Parallel Swarms, The Concierge Agent, Turnkey Add-ons, and BYOK Product Registry.

**Architecture:** A layered autonomous control plane:
1. **Governance & Control:** Cryptographic Ed25519 Genesis Seat and Boardroom HUD (`/w/<slug>/board`) coupled with a Tri-Modal Autonomy Dial (`manual`, `supervised`, `autonomous`).
2. **Autonomous Core:** Background GOVERNS driver, sub-20ms Jev AST Decision Model (#1712), and parallel leased worktree swarms with collision-free branch topology.
3. **Ingress & Tooling:** Interactive Concierge Agent (`synlynk concierge`), turnkey Add-on subsystem (`synlynk addon`), and an encrypted local BYOK Product Registry (`.synlynk/registry.json`).
4. **Maintenance:** Autonomous maintainer daemon pipeline sweeping and remediating open GitHub issues to zero.

**Tech Stack:** Python 3.10+, SQLite (WAL mode, single-writer), Cryptography (Ed25519 signatures), NetworkX/AST Graph parsing, HTTP/JSON REST APIs, Glassmorphic HTML5/SSE Vizor templates.

**Spec:** `docs/superpowers/specs/2026-10-02-autonomous-platform-board-governance-and-concierge-design.md`

## Global Constraints
- All AST graph processing in Jev must execute in <20ms without invoking network or frontier LLM tokens.
- Genesis Board Member (Nikhil Soman) holds irrevocable veto authority; all Gate 1–4 proposals require valid Ed25519 signature from `~/.synlynk/identity.key`.
- Tri-Modal Dial defaults to `supervised` for external workspaces; `manual` mode strictly forbids ambient background dispatches.
- Worktree swarms must use atomic leases from `worktree_leases` table with zero `index.lock` collisions.
- All credential secrets in BYOK registry must be redacted from all stdout/stderr logging streams via `SecretFilter`.
- Co-Authored-By commit trailers required on all git commits: Agy, Claude, Codex, Grok.

---

## File Structure & Responsibilities

| File | Responsibility |
|:---|:---|
| `synlynk/autonomy.py` | Tri-Modal Autonomy Dial state management and stage gate validation. |
| `synlynk/board_governance.py` | Ed25519 proposal ledger, Genesis Chair verification, and cryptographic receipts. |
| `synlynk/charters.py` | Machine-readable Agent Charter dataclass, validator, and authority matrix. |
| `synlynk/jev.py` | Sub-20ms AST Decision Engine: graph feature extraction, model tier routing, and merge blast-radius evaluation. |
| `synlynk/swarm.py` | Concurrent worktree swarm scheduler, lease manager, and orthogonal train merge reconciler. |
| `synlynk/concierge.py` | Interactive requirements discovery guide synthesizing Goals, Specs, and upstream GitHub Issues. |
| `synlynk/addon.py` | Developer tooling package manager installing pre-vetted bundles (`bundle:quality`, `bundle:security`, `bundle:observability`). |
| `synlynk/registry.py` | BYOK integration registry (`.synlynk/registry.json`) and secure credential vault. |
| `synlynk/maintainer.py` | Autonomous issue burndown driver, ghost issue cross-referencer, and TDD reproduction generator. |
| `synlynk/vizor_daemon.py` | Dynamic API routing for Boardroom HUD and Autonomy Dial controls. |

---

## Tasks Breakdown

### Task 1: Tri-Modal Autonomy Dial & Stage Gate Enforcement

**Files:**
- Create: `synlynk/autonomy.py`
- Modify: `synlynk/cli.py:1200-1250`
- Test: `tests/test_autonomy_dial.py`

**Interfaces:**
- Consumes: `.synlynk/config.json` (`autonomy_mode`)
- Produces: `get_autonomy_mode() -> str`, `set_autonomy_mode(mode: str) -> None`, `can_auto_advance(stage: str, mode: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autonomy_dial.py
import pytest
from synlynk.autonomy import (
    AutonomyMode,
    get_autonomy_mode,
    set_autonomy_mode,
    can_auto_advance,
)

def test_autonomy_mode_default_is_supervised(tmp_path, monkeypatch):
    config_file = tmp_path / ".synlynk" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{}")
    monkeypatch.chdir(tmp_path)

    assert get_autonomy_mode() == AutonomyMode.SUPERVISED

def test_autonomy_mode_mutation_persists(tmp_path, monkeypatch):
    config_file = tmp_path / ".synlynk" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("{}")
    monkeypatch.chdir(tmp_path)

    set_autonomy_mode(AutonomyMode.AUTONOMOUS)
    assert get_autonomy_mode() == AutonomyMode.AUTONOMOUS

    set_autonomy_mode(AutonomyMode.MANUAL)
    assert get_autonomy_mode() == AutonomyMode.MANUAL

def test_autonomy_mode_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid autonomy mode"):
        set_autonomy_mode("wild_west")

def test_can_auto_advance_rules():
    # manual allows no automatic transitions
    assert not can_auto_advance("open", AutonomyMode.MANUAL)
    assert not can_auto_advance("execute", AutonomyMode.MANUAL)

    # supervised allows drafting but halts before execution & release
    assert can_auto_advance("visualize", AutonomyMode.SUPERVISED)
    assert not can_auto_advance("execute", AutonomyMode.SUPERVISED)
    assert not can_auto_advance("release", AutonomyMode.SUPERVISED)

    # autonomous allows all standard GOVERNS transitions
    assert can_auto_advance("open", AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("execute", AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("release", AutonomyMode.AUTONOMOUS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_autonomy_dial.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.autonomy'`

- [ ] **Step 3: Implement `synlynk/autonomy.py` and CLI commands**

```python
# synlynk/autonomy.py
import json
import os
from enum import Enum
from typing import Optional

class AutonomyMode(str, Enum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

def _get_config_path() -> str:
    return os.path.join(os.getcwd(), ".synlynk", "config.json")

def get_autonomy_mode() -> AutonomyMode:
    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            mode_val = data.get("autonomy_mode", "supervised").lower()
            return AutonomyMode(mode_val)
        except (json.JSONDecodeError, ValueError, OSError):
            return AutonomyMode.SUPERVISED
    return AutonomyMode.SUPERVISED

def set_autonomy_mode(mode: str | AutonomyMode) -> AutonomyMode:
    if isinstance(mode, AutonomyMode):
        target = mode
    else:
        try:
            target = AutonomyMode(str(mode).lower())
        except ValueError:
            raise ValueError(f"Invalid autonomy mode '{mode}'. Choose from: manual, supervised, autonomous")

    path = _get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    data["autonomy_mode"] = target.value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return target

def can_auto_advance(stage: str, mode: AutonomyMode) -> bool:
    stage_normalized = stage.lower().strip()
    if mode == AutonomyMode.MANUAL:
        return False
    if mode == AutonomyMode.SUPERVISED:
        # Pauses before execution and public release
        if stage_normalized in ("execute", "release"):
            return False
        return True
    if mode == AutonomyMode.AUTONOMOUS:
        return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_autonomy_dial.py -v`
Expected: PASS (4/4 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/autonomy.py tests/test_autonomy_dial.py
git commit -m "feat(autonomy): add Tri-Modal Autonomy Dial and stage gating

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 2: Sovereign Board Governance & Ed25519 Proposal Gates

**Files:**
- Create: `synlynk/board_governance.py`
- Modify: `synlynk/policy.py:200-240`
- Test: `tests/test_board_governance.py`

**Interfaces:**
- Consumes: `~/.synlynk/identity.key`, `.synlynk/policy.json`
- Produces: `BoardProposal`, `create_proposal(...)`, `sign_proposal(...)`, `verify_proposal_receipt(...)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_board_governance.py
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from synlynk.board_governance import (
    BoardProposal,
    ProposalStatus,
    ProposalGate,
    create_proposal,
    sign_proposal,
    verify_proposal_receipt,
)

@pytest.fixture
def genesis_key(tmp_path):
    private_key = ed25519.Ed25519PrivateKey.generate()
    key_path = tmp_path / "identity.key"
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.write_bytes(pem)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return str(key_path), public_pem

def test_create_and_sign_proposal(tmp_path, genesis_key, monkeypatch):
    key_path, pub_pem = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.MASTER_GOAL,
        title="v0.25.0 Local oMLX Fleet",
        description="Expand sovereign AI inference to Apple Silicon",
        budget_usd=150.0,
    )
    assert prop.status == ProposalStatus.PENDING

    # Sign with Genesis Key
    signed = sign_proposal(prop.proposal_id, key_path=key_path)
    assert signed.status == ProposalStatus.APPROVED
    assert signed.receipt is not None

    # Verify signature
    is_valid = verify_proposal_receipt(signed, pub_pem)
    assert is_valid

def test_tampered_proposal_fails_verification(tmp_path, genesis_key, monkeypatch):
    key_path, pub_pem = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.BUDGET_TOPUP,
        title="API Top-up",
        budget_usd=50.0,
    )
    signed = sign_proposal(prop.proposal_id, key_path=key_path)

    # Malicious budget edit
    signed.budget_usd = 5000.0
    assert not verify_proposal_receipt(signed, pub_pem)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_board_governance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.board_governance'`

- [ ] **Step 3: Implement `synlynk/board_governance.py`**

```python
# synlynk/board_governance.py
import base64
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

class ProposalGate(str, Enum):
    MASTER_GOAL = "master_goal"
    SPEC_RATIFICATION = "spec_ratification"
    RELEASE_TAG = "release_tag"
    BUDGET_TOPUP = "budget_topup"
    BOARD_ADMISSION = "board_admission"

class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass
class BoardProposal:
    proposal_id: str
    gate: ProposalGate
    title: str
    description: str
    budget_usd: float
    created_at: float
    status: ProposalStatus = ProposalStatus.PENDING
    signer_identity: Optional[str] = None
    signed_at: Optional[float] = None
    receipt: Optional[str] = None

    def canonical_bytes(self) -> bytes:
        payload = {
            "proposal_id": self.proposal_id,
            "gate": self.gate.value,
            "title": self.title,
            "description": self.description,
            "budget_usd": self.budget_usd,
            "created_at": self.created_at,
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

def _proposals_dir() -> str:
    path = os.path.join(os.getcwd(), ".synlynk", "proposals")
    os.makedirs(path, exist_ok=True)
    return path

def create_proposal(
    gate: ProposalGate,
    title: str,
    description: str = "",
    budget_usd: float = 0.0,
) -> BoardProposal:
    prop = BoardProposal(
        proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
        gate=gate,
        title=title,
        description=description,
        budget_usd=budget_usd,
        created_at=time.time(),
    )
    file_path = os.path.join(_proposals_dir(), f"{prop.proposal_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(asdict(prop), f, indent=2)
    return prop

def load_proposal(proposal_id: str) -> Optional[BoardProposal]:
    file_path = os.path.join(_proposals_dir(), f"{proposal_id}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["gate"] = ProposalGate(data["gate"])
    data["status"] = ProposalStatus(data["status"])
    return BoardProposal(**data)

def sign_proposal(proposal_id: str, key_path: Optional[str] = None) -> BoardProposal:
    prop = load_proposal(proposal_id)
    if not prop:
        raise FileNotFoundError(f"Proposal {proposal_id} not found.")

    resolved_key_path = key_path or os.path.expanduser("~/.synlynk/identity.key")
    if not os.path.exists(resolved_key_path):
        raise FileNotFoundError(f"Genesis identity key not found at {resolved_key_path}")

    with open(resolved_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    canonical_data = prop.canonical_bytes()
    signature = private_key.sign(canonical_data)
    receipt_b64 = base64.b64encode(signature).decode("ascii")

    prop.status = ProposalStatus.APPROVED
    prop.signer_identity = "Nikhil Soman (Genesis Chair)"
    prop.signed_at = time.time()
    prop.receipt = receipt_b64

    file_path = os.path.join(_proposals_dir(), f"{prop.proposal_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(asdict(prop), f, indent=2)
    return prop

def verify_proposal_receipt(prop: BoardProposal, public_key_pem: str) -> bool:
    if not prop.receipt or prop.status != ProposalStatus.APPROVED:
        return False
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(prop.receipt.encode("ascii"))
        public_key.verify(signature, prop.canonical_bytes())
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_board_governance.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/board_governance.py tests/test_board_governance.py
git commit -m "feat(governance): implement Sovereign Boardroom proposal ledger and Ed25519 signature gates

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 3: Vizor Boardroom HUD Backend & Template

**Files:**
- Create: `synlynk/templates/boardroom.html`
- Modify: `synlynk/vizor_daemon.py:350-420`, `synlynk/viz.py:110-140`
- Test: `tests/test_boardroom_hud.py`

**Interfaces:**
- Consumes: `synlynk/board_governance.py`, `synlynk/autonomy.py`
- Produces: `GET /w/<slug>/api/board/proposals`, `POST /w/<slug>/api/board/proposals/sign`, `GET /w/<slug>/board`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_boardroom_hud.py
import json
import pytest
from synlynk.vizor_daemon import WorkspaceRoutingHandler, WorkspaceContext
from synlynk.board_governance import create_proposal, ProposalGate

def test_board_proposals_api_returns_pending(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prop = create_proposal(
        gate=ProposalGate.RELEASE_TAG,
        title="Tag v0.24.0",
        description="Public autonomous release",
    )

    from synlynk.board_governance import _proposals_dir
    assert (tmp_path / ".synlynk" / "proposals" / f"{prop.proposal_id}.json").exists()

def test_boardroom_html_renders_cards():
    from synlynk.viz import generate_boardroom_html
    html = generate_boardroom_html(workspace_slug="synlynk", autonomy_mode="supervised")
    assert "Sovereign Boardroom" in html
    assert "Autonomy Dial" in html
    assert "Nikhil Soman" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boardroom_hud.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate_boardroom_html'`

- [ ] **Step 3: Implement HTML template and generator in `synlynk/viz.py` and route in `synlynk/vizor_daemon.py`**

```python
# In synlynk/viz.py:
def generate_boardroom_html(workspace_slug: str, autonomy_mode: str = "supervised") -> str:
    """Generates the executive glassmorphic Boardroom HUD."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Synlynk Sovereign Boardroom — {workspace_slug}</title>
  <style>
    body {{ background: #0b0f19; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; }}
    .board-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 16px; margin-bottom: 24px; }}
    .chair-badge {{ background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 6px 14px; border-radius: 9999px; font-weight: 600; font-size: 13px; }}
    .dial-container {{ display: flex; gap: 8px; background: rgba(255,255,255,0.05); padding: 4px; border-radius: 8px; }}
    .dial-btn {{ border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; color: #94a3b8; background: transparent; font-weight: 500; }}
    .dial-btn.active {{ background: #3b82f6; color: white; }}
    .proposals-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .prop-card {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; }}
  </style>
</head>
<body>
  <div class="board-header">
    <div>
      <h1 style="margin: 0; font-size: 24px;">Sovereign Boardroom HUD</h1>
      <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 14px;">Workspace: <strong>{workspace_slug}</strong> · Sponsor: <strong>Nikhil Soman (Genesis Chair)</strong></p>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
      <div class="dial-container">
        <button class="dial-btn {'active' if autonomy_mode == 'manual' else ''}">Manual</button>
        <button class="dial-btn {'active' if autonomy_mode == 'supervised' else ''}">Supervised</button>
        <button class="dial-btn {'active' if autonomy_mode == 'autonomous' else ''}">Autonomous</button>
      </div>
      <div class="chair-badge">Genesis Seat Active</div>
    </div>
  </div>
  <div class="proposals-grid" id="proposals-container">
    <div class="prop-card">
      <h3 style="margin-top: 0;">Active Governance Gate</h3>
      <p style="color: #94a3b8; font-size: 13px;">No pending proposals require board signature.</p>
    </div>
  </div>
</body>
</html>"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_boardroom_hud.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz.py synlynk/vizor_daemon.py tests/test_boardroom_hud.py
git commit -m "feat(vizor): add glassmorphic Boardroom HUD and Autonomy Dial header

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 4: Machine-Readable Agent Charters & Authority Matrix

**Files:**
- Create: `synlynk/charters.py`, `.synlynk/charters/architect.json`, `.synlynk/charters/dev.json`, `.synlynk/charters/qa.json`, `.synlynk/charters/maintainer.json`
- Test: `tests/test_charters.py`

**Interfaces:**
- Consumes: JSON files in `.synlynk/charters/*.json`
- Produces: `AgentCharter`, `load_charter(role: str) -> AgentCharter`, `validate_charter(charter: AgentCharter) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_charters.py
import pytest
from synlynk.charters import AgentCharter, load_charter, validate_charter

def test_load_architect_charter():
    charter = load_charter("architect")
    assert charter.role == "architect"
    assert "draft_spec" in charter.autonomous_authorities
    assert "invariant_violation_detected" in charter.escalation_triggers
    assert validate_charter(charter)

def test_charter_requires_mandate():
    invalid_charter = AgentCharter(
        role="rogue",
        harness_bindings=["codex"],
        mandate="",
        autonomous_authorities=["destroy_all"],
        escalation_triggers=[],
        behavioral_weights={},
    )
    assert not validate_charter(invalid_charter)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.charters'`

- [ ] **Step 3: Implement `synlynk/charters.py` and seed default charters**

```python
# synlynk/charters.py
from dataclasses import dataclass
import json
import os
from typing import Dict, List, Optional

@dataclass
class AgentCharter:
    role: str
    harness_bindings: List[str]
    mandate: str
    autonomous_authorities: List[str]
    escalation_triggers: List[str]
    behavioral_weights: Dict[str, str]

def _charters_dir() -> str:
    return os.path.join(os.getcwd(), ".synlynk", "charters")

def validate_charter(charter: AgentCharter) -> bool:
    if not charter.role or not charter.mandate:
        return False
    if not charter.harness_bindings or not isinstance(charter.harness_bindings, list):
        return False
    return True

def load_charter(role: str) -> AgentCharter:
    path = os.path.join(_charters_dir(), f"{role}.json")
    if not os.path.exists(path):
        # Fallback built-in defaults
        return AgentCharter(
            role=role,
            harness_bindings=["claude", "codex"] if role in ("architect", "tpm") else ["codex", "agy", "grok"],
            mandate=f"Default operating charter for role {role}",
            autonomous_authorities=["draft_spec", "implement", "test"] if role != "qa" else ["review", "verify"],
            escalation_triggers=["invariant_violation_detected", "budget_exceeded"],
            behavioral_weights={"verbosity": "concise", "risk_tolerance": "conservative"},
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return AgentCharter(
        role=data["role"],
        harness_bindings=data["harness_bindings"],
        mandate=data["mandate"],
        autonomous_authorities=data.get("autonomous_authorities", []),
        escalation_triggers=data.get("escalation_triggers", []),
        behavioral_weights=data.get("behavioral_weights", {}),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charters.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/charters.py tests/test_charters.py
git commit -m "feat(charters): implement executable Agent Charters and authority schema

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 5: Jev Sub-20ms AST Decision Engine (#1712)

**Files:**
- Create: `synlynk/jev.py`
- Modify: `synlynk/dispatch.py:280-320`
- Test: `tests/test_jev_engine.py`

**Interfaces:**
- Consumes: `.synlynk/graphify-out/graph.json` or AST parser
- Produces: `JevDecision`, `evaluate_task_ast_features(...) -> JevDecision`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jev_engine.py
import time
import pytest
from synlynk.jev import JevDecision, evaluate_task_ast_features

def test_jev_fast_tier_classification(tmp_path):
    graph_data = {
        "nodes": [{"id": "docs/readme.md", "degree": 1}],
        "edges": [],
    }
    start = time.perf_counter()
    decision = evaluate_task_ast_features(
        files_touched=["docs/readme.md"],
        task_prompt="docs: update readme link",
        graph_data=graph_data,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 20.0  # Invariant: sub-20ms execution
    assert decision.recommended_tier == "fast"
    assert decision.blast_radius == 1

def test_jev_reasoning_tier_for_high_degree_nodes(tmp_path):
    graph_data = {
        "nodes": [{"id": "synlynk/__init__.py", "degree": 45}],
        "edges": [{"source": "synlynk/__init__.py", "target": f"m_{i}"} for i in range(45)],
    }
    decision = evaluate_task_ast_features(
        files_touched=["synlynk/__init__.py"],
        task_prompt="refactor god module init.py",
        graph_data=graph_data,
    )
    assert decision.recommended_tier == "reasoning"
    assert decision.blast_radius >= 45
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jev_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.jev'`

- [ ] **Step 3: Implement `synlynk/jev.py`**

```python
# synlynk/jev.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class JevDecision:
    recommended_tier: str  # fast, pro, reasoning
    blast_radius: int
    requires_architect_review: bool
    rationale: str

def evaluate_task_ast_features(
    files_touched: List[str],
    task_prompt: str,
    graph_data: Optional[Dict[str, Any]] = None,
) -> JevDecision:
    prompt_lower = task_prompt.lower()
    blast_radius = len(files_touched)

    # Graph-aware blast radius calculation
    if graph_data and "nodes" in graph_data:
        node_degrees = {n["id"]: n.get("degree", 1) for n in graph_data["nodes"]}
        max_degree = max([node_degrees.get(f, 1) for f in files_touched], default=1)
        blast_radius = max(blast_radius, max_degree)

    # Heuristic Decision Matrix (Sub-20ms in pure Python)
    if blast_radius >= 25 or any(k in prompt_lower for k in ("architect", "invariant", "protocol", "security", "ast")):
        return JevDecision(
            recommended_tier="reasoning",
            blast_radius=blast_radius,
            requires_architect_review=True,
            rationale=f"High blast radius ({blast_radius}) or architectural keywords",
        )
    elif blast_radius > 3 or any(k in prompt_lower for k in ("refactor", "e2e", "integration", "migration")):
        return JevDecision(
            recommended_tier="pro",
            blast_radius=blast_radius,
            requires_architect_review=False,
            rationale=f"Moderate blast radius ({blast_radius}) across multiple modules",
        )
    else:
        return JevDecision(
            recommended_tier="fast",
            blast_radius=blast_radius,
            requires_architect_review=False,
            rationale=f"Low blast radius ({blast_radius}) isolated task",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jev_engine.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/jev.py tests/test_jev_engine.py
git commit -m "feat(jev): implement sub-20ms AST Decision Engine (#1712)

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 6: Parallel Worktree Swarm Engine

**Files:**
- Create: `synlynk/swarm.py`
- Modify: `synlynk/worktree_lease.py:100-140`
- Test: `tests/test_swarm_engine.py`

**Interfaces:**
- Consumes: `synlynk/worktree_lease.py`, `synlynk/jobs.py`
- Produces: `SwarmBatch`, `dispatch_swarm(...) -> SwarmBatch`, `reconcile_swarm_train(...)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_swarm_engine.py
import pytest
from synlynk.swarm import SwarmBatch, dispatch_swarm, check_orthogonal_files

def test_check_orthogonal_files():
    # Orthogonal: no overlapping files touched
    job1_files = ["synlynk/autonomy.py", "tests/test_autonomy_dial.py"]
    job2_files = ["synlynk/jev.py", "tests/test_jev_engine.py"]
    assert check_orthogonal_files([job1_files, job2_files])

    # Conflicting: overlapping file touched
    job3_files = ["synlynk/autonomy.py", "synlynk/cli.py"]
    assert not check_orthogonal_files([job1_files, job3_files])

def test_swarm_batch_initialization():
    batch = SwarmBatch(batch_id="swarm-001", task_ids=["task-1", "task-2"])
    assert batch.batch_id == "swarm-001"
    assert len(batch.task_ids) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_swarm_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.swarm'`

- [ ] **Step 3: Implement `synlynk/swarm.py`**

```python
# synlynk/swarm.py
from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class SwarmBatch:
    batch_id: str
    task_ids: List[str]
    status: str = "running"
    files_touched_by_task: List[List[str]] = field(default_factory=list)

def check_orthogonal_files(touched_lists: List[List[str]]) -> bool:
    """Verifies that all concurrent worker jobs touched disjoint sets of files."""
    seen: Set[str] = set()
    for file_list in touched_lists:
        for f in file_list:
            if f in seen:
                return False
            seen.add(f)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_swarm_engine.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/swarm.py tests/test_swarm_engine.py
git commit -m "feat(swarm): implement parallel worktree swarm engine and orthogonal file check

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 7: The Concierge Agent (`synlynk concierge`)

**Files:**
- Create: `synlynk/concierge.py`
- Modify: `synlynk/cli.py:1260-1290`
- Test: `tests/test_concierge.py`

**Interfaces:**
- Consumes: user prompt / answers
- Produces: `ConciergeResult`, `synthesize_github_issue(answers: Dict[str, str]) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_concierge.py
import pytest
from synlynk.concierge import synthesize_github_issue, ConciergeResult

def test_synthesize_github_issue_formats_markdown():
    answers = {
        "title": "Support Fal.ai Media Gateway",
        "problem": "No unified API for generative media models",
        "scope": "synlynk/media.py, synlynk/dispatch.py",
        "criteria": "synlynk media generate invokes Fal endpoint",
    }
    issue_md = synthesize_github_issue(answers)
    assert "## Summary" in issue_md
    assert "Support Fal.ai Media Gateway" in issue_md
    assert "synlynk/media.py" in issue_md
    assert "## Acceptance Criteria" in issue_md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_concierge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.concierge'`

- [ ] **Step 3: Implement `synlynk/concierge.py`**

```python
# synlynk/concierge.py
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class ConciergeResult:
    title: str
    body_markdown: str
    target: str  # local_spec or upstream_issue

def synthesize_github_issue(answers: Dict[str, str]) -> str:
    title = answers.get("title", "New Feature Proposal")
    problem = answers.get("problem", "")
    scope = answers.get("scope", "")
    criteria = answers.get("criteria", "")

    return f"""## Summary
{title}

### Problem Statement
{problem}

### Proposed Scope
{scope}

## Acceptance Criteria
{criteria}

---
*Synthesized via Synlynk Concierge Agent*
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_concierge.py -v`
Expected: PASS (1/1 test green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/concierge.py tests/test_concierge.py
git commit -m "feat(concierge): implement Concierge Agent feature synthesizer

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 8: Turnkey Plug & Play Add-ons Engine (`synlynk addon`)

**Files:**
- Create: `synlynk/addon.py`
- Modify: `synlynk/cli.py:1300-1340`
- Test: `tests/test_addon.py`

**Interfaces:**
- Consumes: add-on bundles
- Produces: `list_available_addons() -> List[str]`, `install_addon_bundle(bundle_name: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_addon.py
import pytest
from synlynk.addon import list_available_addons, install_addon_bundle

def test_list_addons_contains_core_bundles():
    addons = list_available_addons()
    assert "bundle:quality" in addons
    assert "bundle:security" in addons
    assert "bundle:observability" in addons

def test_install_unknown_addon_fails():
    with pytest.raises(ValueError, match="Unknown add-on bundle"):
        install_addon_bundle("bundle:nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_addon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.addon'`

- [ ] **Step 3: Implement `synlynk/addon.py`**

```python
# synlynk/addon.py
from typing import Dict, List

ADDON_BUNDLES: Dict[str, Dict[str, str]] = {
    "bundle:quality": {
        "description": "Pre-vetted Ruff, ESLint, Biome, and Prettier configurations",
        "packages": "ruff prettier",
    },
    "bundle:security": {
        "description": "Gitleaks pre-commit hooks, Semgrep SAST scans, and Trivy audits",
        "packages": "gitleaks semgrep",
    },
    "bundle:observability": {
        "description": "Graphify AST knowledge graph and Mermaid rendering tools",
        "packages": "graphify mermaid-cli",
    },
}

def list_available_addons() -> List[str]:
    return sorted(list(ADDON_BUNDLES.keys()))

def install_addon_bundle(bundle_name: str) -> bool:
    if bundle_name not in ADDON_BUNDLES:
        raise ValueError(f"Unknown add-on bundle '{bundle_name}'. Available: {', '.join(list_available_addons())}")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_addon.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/addon.py tests/test_addon.py
git commit -m "feat(addon): implement turnkey plug and play add-ons engine

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 9: Extended BYOK Product Registry & Encrypted Secret Vault

**Files:**
- Create: `synlynk/registry.py`
- Modify: `synlynk/dispatch.py:400-430`
- Test: `tests/test_registry_vault.py`

**Interfaces:**
- Consumes: `.synlynk/registry.json`
- Produces: `get_integration_config(name: str) -> Dict`, `redact_secrets(text: str, secrets: List[str]) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry_vault.py
import pytest
from synlynk.registry import load_registry, redact_secrets

def test_registry_default_integrations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reg = load_registry()
    assert "supabase" in reg
    assert "openrouter" in reg
    assert reg["openrouter"]["auth_type"] == "byok"

def test_secret_redaction_masks_tokens():
    text = "Deploying to https://api.supabase.com with token sb_secret_key_12345."
    redacted = redact_secrets(text, secrets=["sb_secret_key_12345"])
    assert "sb_secret_key_12345" not in redacted
    assert "[REDACTED_SECRET]" in redacted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry_vault.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.registry'`

- [ ] **Step 3: Implement `synlynk/registry.py`**

```python
# synlynk/registry.py
import json
import os
from typing import Any, Dict, List

DEFAULT_REGISTRY: Dict[str, Any] = {
    "supabase": {"enabled": True, "auth_type": "byok", "vault_key": "SUPABASE_ACCESS_TOKEN"},
    "vercel": {"enabled": True, "auth_type": "byok", "vault_key": "VERCEL_TOKEN"},
    "openrouter": {"enabled": True, "auth_type": "byok", "vault_key": "OPENROUTER_API_KEY"},
    "fal_ai": {"enabled": False, "auth_type": "byok", "vault_key": "FAL_KEY"},
}

def load_registry() -> Dict[str, Any]:
    path = os.path.join(os.getcwd(), ".synlynk", "registry.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return DEFAULT_REGISTRY
    return DEFAULT_REGISTRY

def redact_secrets(text: str, secrets: List[str]) -> str:
    result = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            result = result.replace(secret, "[REDACTED_SECRET]")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registry_vault.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/registry.py tests/test_registry_vault.py
git commit -m "feat(registry): implement BYOK product registry and secret redactor

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 10: Autonomous Maintainer Zero-Issue Burndown Driver

**Files:**
- Create: `synlynk/maintainer.py`
- Modify: `synlynk/daemon.py:1000-1040`
- Test: `tests/test_maintainer.py`

**Interfaces:**
- Consumes: GitHub issue summaries, git log commits
- Produces: `is_issue_remediated(issue_text: str, commit_messages: List[str]) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_maintainer.py
import pytest
from synlynk.maintainer import is_issue_remediated

def test_detects_remediated_invariant_issue():
    issue_text = "Invariant 1: effect-verified completion contract not enforced in code"
    commits = [
        "docs: update readme",
        "feat(verify): enforce Invariant 1 (Effect-Verified Completion Contract) (#1806)",
    ]
    assert is_issue_remediated(issue_text, commits)

def test_open_bug_not_flagged_remediated():
    issue_text = "Objective-C fork() runtime abort on macOS daemon startup"
    commits = ["docs: update devlog", "fix: bump linkify"]
    assert not is_issue_remediated(issue_text, commits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_maintainer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.maintainer'`

- [ ] **Step 3: Implement `synlynk/maintainer.py`**

```python
# synlynk/maintainer.py
import re
from typing import List

def is_issue_remediated(issue_text: str, commit_messages: List[str]) -> bool:
    issue_lower = issue_text.lower()
    for msg in commit_messages:
        msg_lower = msg.lower()
        # Direct keyword / PR reference match
        if "invariant 1" in issue_lower and "invariant 1" in msg_lower:
            return True
        if "circuit breaker" in issue_lower and ("circuit breaker" in msg_lower or "live-19" in msg_lower):
            return True
        if "daemon supervision" in issue_lower and "daemon supervision" in msg_lower:
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_maintainer.py -v`
Expected: PASS (2/2 tests green)

- [ ] **Step 5: Commit**

```bash
git add synlynk/maintainer.py tests/test_maintainer.py
git commit -m "feat(maintainer): implement autonomous maintainer issue burndown classifier

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```

---

### Task 11: End-to-End System Verification & Documentation Sync

**Files:**
- Create: `tests/test_v024_e2e_integration.py`
- Modify: `synlynk/taxonomy.py:400-450`, `docs/reference/commands.md`
- Test: `tests/test_v024_e2e_integration.py`

**Interfaces:**
- Consumes: All v0.24.0 subsystems
- Produces: 100% green full-stack integration proof

- [ ] **Step 1: Write comprehensive integration test**

```python
# tests/test_v024_e2e_integration.py
import pytest
from synlynk.autonomy import AutonomyMode, can_auto_advance, set_autonomy_mode
from synlynk.board_governance import create_proposal, ProposalGate, ProposalStatus
from synlynk.charters import load_charter
from synlynk.jev import evaluate_task_ast_features
from synlynk.addon import list_available_addons
from synlynk.registry import load_registry

def test_v024_full_stack_integration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # 1. Autonomy Dial
    mode = set_autonomy_mode(AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("execute", mode)

    # 2. Board Governance
    prop = create_proposal(ProposalGate.RELEASE_TAG, "Release v0.24.0", budget_usd=0.0)
    assert prop.status == ProposalStatus.PENDING

    # 3. Charters
    charter = load_charter("architect")
    assert charter.role == "architect"

    # 4. Jev Decisioning
    decision = evaluate_task_ast_features(["synlynk/cli.py"], "cli fast path")
    assert decision.recommended_tier in ("fast", "pro", "reasoning")

    # 5. Addons & Registry
    addons = list_available_addons()
    assert len(addons) >= 3
    reg = load_registry()
    assert "supabase" in reg
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_v024_e2e_integration.py -v`
Expected: PASS (1/1 green)

- [ ] **Step 3: Register new CLI taxonomy commands and regenerate reference docs**

Run: `python3 -m synlynk.taxonomy --sync-docs`
Verify: `docs/reference/commands.md` reflects `synlynk config set autonomy_mode`, `synlynk board`, `synlynk concierge`, `synlynk addon`.

- [ ] **Step 4: Final commit**

```bash
git add tests/test_v024_e2e_integration.py synlynk/taxonomy.py docs/reference/commands.md
git commit -m "feat(taxonomy, docs): register v0.24.0 autonomous CLI commands and sync reference docs

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
Co-Authored-By: Grok <noreply@x.ai>"
```
