from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DispatchRequest:
    agent: str
    task: str
    story_id: Optional[str] = None
    agent_id: Optional[str] = None
    force_agent: bool = False
    context_mode: Optional[str] = None
    cycle: str = "work"
    skip_preflight: bool = False
    requires_gh_write: bool = False
    static_baseline: bool = False
    task_type: Optional[str] = None
    requires: list = field(default_factory=list)
    grants: list = field(default_factory=list)
    revokes: list = field(default_factory=list)
    job_id: Optional[str] = None
    issue: Optional[int] = None
    base: Optional[str] = None
    scope_paths: list = field(default_factory=list)
    session_id: Optional[str] = None
    gh_write_target_kind: str = "issue"
    gh_write_expect: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    model_tier: Optional[str] = None
    role: Optional[str] = None
    task_domain: Optional[str] = None
    criticality: float = 1.0
    lambda_: float = 1.0
    permissions: list = field(default_factory=list)
    read_only: bool = False
    skip_permissions: bool = False
