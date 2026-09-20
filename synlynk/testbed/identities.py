"""Synthetic Credential Vault & 3-Tier Identity Attribution Provisioner."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from synlynk.testbed.driver import TestbedDriver


@dataclass
class SyntheticIdentity:
    username: str
    email: str
    role: str
    harness: str
    model_tier: str = "fast"
    model: Optional[str] = None
    api_keys: Dict[str, str] = field(default_factory=dict)

    @property
    def attribution_tag(self) -> str:
        return f"<@{self.username}, {self.role}, {self.harness}>"


STANDARD_IDENTITIES: Dict[str, SyntheticIdentity] = {
    "node-1": SyntheticIdentity(
        username="alice",
        email="alice@test.synlynk",
        role="dev",
        harness="codex",
        model_tier="fast",
        model="gpt-4o-mini",
        api_keys={
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "mock-openai-key-testbed"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "mock-anthropic-key-testbed"),
        },
    ),
    "node-2": SyntheticIdentity(
        username="bob",
        email="bob@test.synlynk",
        role="architect",
        harness="agy",
        model_tier="pro",
        model="gemini-1.5-pro",
        api_keys={
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", "mock-gemini-key-testbed"),
        },
    ),
    "node-3": SyntheticIdentity(
        username="charlie",
        email="charlie@test.synlynk",
        role="qa",
        harness="grok",
        model_tier="pro",
        model="grok-3",
        api_keys={
            "XAI_API_KEY": os.environ.get("XAI_API_KEY", "mock-xai-key-testbed"),
        },
    ),
}


def get_identity_for_node(node_index: int = 1) -> SyntheticIdentity:
    key = f"node-{node_index}"
    if key in STANDARD_IDENTITIES:
        return STANDARD_IDENTITIES[key]
    return SyntheticIdentity(
        username=f"synthetic_user_{node_index}",
        email=f"user_{node_index}@test.synlynk",
        role="dev",
        harness="codex",
    )


def provision_node_identity(
    driver: TestbedDriver,
    node_id: str,
    identity: SyntheticIdentity,
) -> bool:
    """Configures Git identity, synlynk role attribution, and BYOK credentials on the remote node."""
    # 1. Git configuration
    git_cmds = (
        f"git config --global user.name '{identity.username}' && "
        f"git config --global user.email '{identity.email}'"
    )
    res = driver.exec_command(node_id, git_cmds)
    if not res.ok:
        return False

    # 2. Environment credentials (.bashrc / synlynk env)
    env_exports = "\n".join([f"export {k}='{v}'" for k, v in identity.api_keys.items()])
    env_exports += f"\nexport SYNLYNK_DEFAULT_HARNESS='{identity.harness}'\n"
    env_exports += f"export SYNLYNK_DEFAULT_ROLE='{identity.role}'\n"
    env_exports += f"export SYNLYNK_MODEL_TIER='{identity.model_tier}'\n"
    if identity.model:
        env_exports += f"export SYNLYNK_MODEL='{identity.model}'\n"

    cmd = f"cat << 'EOF' >> ~/.bashrc\n{env_exports}\nEOF"
    res = driver.exec_command(node_id, cmd)
    return res.ok
