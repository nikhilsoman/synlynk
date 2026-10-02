"""Sovereign Board governance: Ed25519-signed proposal ledger and Genesis Chair verification.

Signing uses the OpenSSH `ssh-keygen -Y sign`/`-Y verify` SSHSIG workflow (same
pattern as synlynk/team.py's capability-rating signatures) rather than a
third-party crypto library, keeping synlynk's dependency footprint at zero.
"""
import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional

SSH_SIGN_NAMESPACE = "synlynk-board"
GENESIS_PRINCIPAL = "genesis-chair"
GENESIS_IDENTITY = "Nikhil Soman (Genesis Chair)"


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
        """Bytes that are actually signed/verified — excludes status/receipt fields."""
        payload = {
            "proposal_id": self.proposal_id,
            "gate": self.gate.value if isinstance(self.gate, ProposalGate) else self.gate,
            "title": self.title,
            "description": self.description,
            "budget_usd": self.budget_usd,
            "created_at": self.created_at,
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["gate"] = self.gate.value if isinstance(self.gate, ProposalGate) else self.gate
        data["status"] = self.status.value if isinstance(self.status, ProposalStatus) else self.status
        return data


def _proposals_dir() -> str:
    path = os.path.join(os.getcwd(), ".synlynk", "proposals")
    os.makedirs(path, exist_ok=True)
    return path


def _proposal_path(proposal_id: str) -> str:
    return os.path.join(_proposals_dir(), f"{proposal_id}.json")


def _save_proposal(prop: BoardProposal) -> None:
    with open(_proposal_path(prop.proposal_id), "w", encoding="utf-8") as f:
        json.dump(prop.to_dict(), f, indent=2)


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
    _save_proposal(prop)
    return prop


def load_proposal(proposal_id: str) -> Optional[BoardProposal]:
    path = _proposal_path(proposal_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["gate"] = ProposalGate(data["gate"])
    data["status"] = ProposalStatus(data["status"])
    return BoardProposal(**data)


def sign_proposal(proposal_id: str, key_path: Optional[str] = None) -> BoardProposal:
    """Sign a pending proposal with the Genesis Chair's Ed25519 identity key."""
    prop = load_proposal(proposal_id)
    if prop is None:
        raise FileNotFoundError(f"Proposal {proposal_id} not found.")

    resolved_key_path = key_path or os.path.expanduser("~/.synlynk/identity.key")
    if not os.path.exists(resolved_key_path):
        raise FileNotFoundError(f"Genesis identity key not found at {resolved_key_path}")

    receipt = _ssh_sign(prop.canonical_bytes(), resolved_key_path)

    prop.status = ProposalStatus.APPROVED
    prop.signer_identity = GENESIS_IDENTITY
    prop.signed_at = time.time()
    prop.receipt = receipt
    _save_proposal(prop)
    return prop


def verify_proposal_receipt(prop: BoardProposal, public_key: str) -> bool:
    """Verify prop.receipt against a Genesis public key.

    `public_key` may be a path to an ssh `.pub` file, or a raw
    `ssh-ed25519 AAAA...` public key string.
    """
    if not prop.receipt or prop.status != ProposalStatus.APPROVED:
        return False

    try:
        pub_line = _load_pub_key_line(public_key)
    except OSError:
        return False

    return _ssh_verify(prop.canonical_bytes(), prop.receipt, pub_line)


def _load_pub_key_line(public_key: str) -> str:
    if os.path.exists(public_key):
        with open(public_key, "r", encoding="utf-8") as f:
            return f.read().strip()
    return public_key.strip()


def _ssh_sign(data: bytes, key_path: str) -> str:
    msg_file = None
    sig_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".proposal", delete=False) as f:
            f.write(data)
            msg_file = f.name
        sig_file = msg_file + ".sig"
        result = subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", SSH_SIGN_NAMESPACE, msg_file],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(sig_file):
            raise RuntimeError(f"ssh-keygen sign failed: {result.stderr.strip()}")
        with open(sig_file, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    finally:
        for f_path in (msg_file, sig_file):
            if f_path and os.path.exists(f_path):
                try:
                    os.unlink(f_path)
                except OSError:
                    pass


def _ssh_verify(data: bytes, receipt: str, pub_key_line: str) -> bool:
    sig_file = None
    allowed_signers_file = None
    try:
        sig_fd, sig_file = tempfile.mkstemp(suffix=".sig")
        with os.fdopen(sig_fd, "w", encoding="utf-8") as f:
            f.write(receipt)

        signers_fd, allowed_signers_file = tempfile.mkstemp(suffix=".allowed_signers")
        with os.fdopen(signers_fd, "w", encoding="utf-8") as f:
            f.write(f"{GENESIS_PRINCIPAL} {pub_key_line}\n")

        result = subprocess.run(
            [
                "ssh-keygen", "-Y", "verify",
                "-f", allowed_signers_file,
                "-I", GENESIS_PRINCIPAL,
                "-n", SSH_SIGN_NAMESPACE,
                "-s", sig_file,
            ],
            input=data,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        for f_path in (sig_file, allowed_signers_file):
            if f_path and os.path.exists(f_path):
                try:
                    os.unlink(f_path)
                except OSError:
                    pass
