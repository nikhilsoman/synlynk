"""3-Tier Identity Attribution Protocol for multi-human and multi-agent coordination."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from synlynk.charter_schema import KNOWN_ROLES


SUPPORTED_HARNESSES = ("codex", "agy", "grok", "claude", "omlx", "native")

HARNESS_METADATA = {
    "claude": {"name": "Claude Sonnet", "email": "noreply@anthropic.com"},
    "agy": {"name": "AGY", "email": "noreply@antigravity.dev"},
    "codex": {"name": "Codex", "email": "noreply@openai.com"},
    "grok": {"name": "Grok", "email": "noreply@x.ai"},
    "omlx": {"name": "oMLX", "email": "local@omlx.local"},
    "native": {"name": "Native Shell", "email": "noreply@synlynk.dev"},
}

_TRIPLET_TAG_RE = re.compile(r"<\s*@?([a-zA-Z0-9_\-\.]+)\s*,\s*([a-zA-Z0-9_\-]+)\s*,\s*([a-zA-Z0-9_\-]+)\s*>")
_COLON_TAG_RE = re.compile(r"^@?([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-]+):([a-zA-Z0-9_\-]+)$")


@dataclass(frozen=True)
class IdentityTriplet:
    """Represents a 3-tier identity attribution triplet: <@user, role, harness>."""
    user: str
    role: str
    harness: str
    email: Optional[str] = None

    @property
    def tag(self) -> str:
        """Formatted canonical tag string: <@user, role, harness>."""
        u = self.user.lstrip("@")
        return f"<@{u}, {self.role}, {self.harness}>"

    def to_dict(self) -> Dict[str, str]:
        """Convert triplet to a dictionary representation."""
        d = {
            "user": self.user.lstrip("@"),
            "role": self.role,
            "harness": self.harness,
            "tag": self.tag,
        }
        if self.email:
            d["email"] = self.email
        return d

    def to_commit_trailers(self) -> List[str]:
        """Generate standard git commit trailers for attribution."""
        trailers = []
        # Co-Authored-By for the AI harness
        harness_key = self.harness.lower()
        meta = HARNESS_METADATA.get(harness_key, {"name": self.harness.capitalize(), "email": f"noreply@{self.harness}.local"})
        trailers.append(f"Co-Authored-By: {meta['name']} <{meta['email']}>")

        # Attributed-To for the 3-tier triplet
        u = self.user.lstrip("@")
        trailers.append(f"Attributed-To: @{u} <{self.role}/{self.harness}>")
        return trailers

    def to_prompt_header(self) -> str:
        """Generate identity attestation block for prompt context injection."""
        return (
            f"[Session Attribution: {self.tag}]\n"
            f"• Operator: @{self.user.lstrip('@')}\n"
            f"• Role Charter: {self.role}\n"
            f"• Harness Backend: {self.harness}\n"
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate triplet attributes against declared known schemas."""
        errors = []
        if not self.user or not self.user.strip():
            errors.append("User cannot be empty.")
        if not self.role or not self.role.strip():
            errors.append("Role cannot be empty.")
        elif self.role not in KNOWN_ROLES and self.role not in ("core", "infra", "lead", "architecture", "tester"):
            errors.append(f"Unknown role '{self.role}'.")
        if not self.harness or not self.harness.strip():
            errors.append("Harness cannot be empty.")
        elif self.harness.lower() not in SUPPORTED_HARNESSES:
            errors.append(f"Unknown harness '{self.harness}'. Supported: {', '.join(SUPPORTED_HARNESSES)}")
        return len(errors) == 0, errors

    @classmethod
    def from_tag(cls, tag_str: str) -> Optional[IdentityTriplet]:
        """Parse canonical tag format `<@user, role, harness>` or `@user:role:harness`."""
        if not tag_str or not isinstance(tag_str, str):
            return None
        tag_clean = tag_str.strip()
        match = _TRIPLET_TAG_RE.search(tag_clean)
        if match:
            return cls(
                user=match.group(1).strip(),
                role=match.group(2).strip(),
                harness=match.group(3).strip(),
            )
        match_colon = _COLON_TAG_RE.match(tag_clean)
        if match_colon:
            return cls(
                user=match_colon.group(1).strip(),
                role=match_colon.group(2).strip(),
                harness=match_colon.group(3).strip(),
            )
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional[IdentityTriplet]:
        """Construct IdentityTriplet from dictionary."""
        if not isinstance(data, dict):
            return None
        user = str(data.get("user") or data.get("operator") or "").strip()
        role = str(data.get("role") or data.get("charter") or "").strip()
        harness = str(data.get("harness") or data.get("backend") or "").strip()
        email = data.get("email")
        if user and role and harness:
            return cls(user=user, role=role, harness=harness, email=email)
        return None


def resolve_identity_triplet(
    user: Optional[str] = None,
    role: Optional[str] = None,
    harness: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> IdentityTriplet:
    """Cascading resolution of the active 3-tier identity attribution triplet."""
    # 1. Environment tag override
    env_tag = os.environ.get("SYNLYNK_IDENTITY_TRIPLET")
    if env_tag:
        parsed = IdentityTriplet.from_tag(env_tag)
        if parsed:
            return parsed

    # 2. Resolve User
    resolved_user = user or os.environ.get("SYNLYNK_USER")
    if not resolved_user:
        # Check git config
        try:
            cwd = repo_root or "."
            res = subprocess.run(
                ["git", "-C", cwd, "config", "user.name"],
                capture_output=True, text=True, check=False,
            )
            git_name = res.stdout.strip()
            if git_name:
                resolved_user = git_name.lower().replace(" ", "")
        except Exception:
            pass
    if not resolved_user:
        resolved_user = os.environ.get("USER", "unknown")

    # 3. Resolve Role
    resolved_role = role or os.environ.get("SYNLYNK_ROLE") or os.environ.get("SYNLYNK_GH_ROLE")
    if not resolved_role:
        resolved_role = "dev"

    # 4. Resolve Harness
    resolved_harness = harness or os.environ.get("SYNLYNK_HARNESS") or os.environ.get("SYNLYNK_HOME_HARNESS")
    if not resolved_harness:
        # Check if running in agy/gemini or claude or codex
        if os.environ.get("GEMINI_CLI") or os.environ.get("ANTIGRAVITY"):
            resolved_harness = "agy"
        elif os.environ.get("CODEX_CLI") or os.environ.get("OPENAI_CODEX"):
            resolved_harness = "codex"
        elif os.environ.get("CLAUDE_CLI"):
            resolved_harness = "claude"
        else:
            resolved_harness = "agy"

    # Resolve email
    resolved_email = None
    try:
        cwd = repo_root or "."
        res_email = subprocess.run(
            ["git", "-C", cwd, "config", "user.email"],
            capture_output=True, text=True, check=False,
        )
        resolved_email = res_email.stdout.strip() or None
    except Exception:
        pass

    return IdentityTriplet(
        user=resolved_user.lstrip("@"),
        role=resolved_role,
        harness=resolved_harness.lower(),
        email=resolved_email,
    )


def cmd_whoami(args) -> int:
    """CLI handler for `synlynk whoami` / `synlynk identity`."""
    user_arg = getattr(args, "user", None)
    role_arg = getattr(args, "role", None)
    harness_arg = getattr(args, "harness", None)
    as_json = getattr(args, "json", False)

    triplet = resolve_identity_triplet(user=user_arg, role=role_arg, harness=harness_arg)
    is_valid, errors = triplet.validate()

    if as_json:
        payload = triplet.to_dict()
        payload["valid"] = is_valid
        payload["errors"] = errors
        payload["trailers"] = triplet.to_commit_trailers()
        print(json.dumps(payload, indent=2))
        return 0

    print("\n🪪 Active 3-Tier Identity Attribution:")
    print(f"  Canonical Tag: {triplet.tag}")
    print(f"  Operator:      @{triplet.user.lstrip('@')}")
    print(f"  Role Charter:  {triplet.role}")
    print(f"  Harness:       {triplet.harness}")
    if triplet.email:
        print(f"  Git Email:     {triplet.email}")

    status_icon = "🟢 Valid" if is_valid else f"🟡 Warnings: {'; '.join(errors)}"
    print(f"  Schema Status: {status_icon}")

    print("\n  Git Commit Trailers:")
    for tr in triplet.to_commit_trailers():
        print(f"    {tr}")
    print()
    return 0
