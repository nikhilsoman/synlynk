"""Shared constants used across synlynk modules."""

VERSION = "0.14.0"

_INSTALL_SCRIPT_URL = (
    "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh"
)

QUOTA_PATTERNS = [
    "rate limit", "quota exceeded", "resource exhausted",
    "billing", "insufficient_quota", "too many requests",
    "RESOURCE_EXHAUSTED",
]

HARNESS_TIMEOUT_PATTERNS = [
    "timeout waiting for response",
]

_ROLE_PERMISSION_DEFAULTS = {
    "pm": ["read:*"],
    "review": ["read:*"],
    "deploy": ["read:*"],
    "implement": ["read:*", "write:src/", "run:tests"],
    "test": ["read:*", "write:src/", "run:tests"],
    "refactor": ["read:*", "write:src/", "run:tests"],
    "css": ["read:*", "write:src/", "write:docs/"],
    "templates": ["read:*", "write:src/", "write:docs/"],
    "content": ["read:*", "write:src/", "write:docs/"],
    "canvas": ["read:*", "write:src/", "run:shell"],
    "js": ["read:*", "write:src/", "run:shell"],
    "infra": ["read:*", "write:src/", "run:shell"],
}

_PERMISSION_TO_TOOL_MAP = {
    "read:*": ["Read", "Glob", "Grep", "LS"],
    "write:src/": ["Edit", "Write", "MultiEdit"],
    "write:docs/": ["Edit", "Write"],
    "run:tests": ["Bash(pytest:*)"],
    "run:shell": ["Bash"],
}

# Known baseline capabilities per agent CLI.
# Roles: "architect" (design/docs), "builder" (implement), "verifier" (test/review)
AGENT_CAPABILITY_BASELINES = {
    "claude": {
        "cli": "claude",
        "can_gh_write": True,
        "non_interactive_flags": ["--print"],
        "dispatch_flags": {
            "valid_flags": ["--dangerously-skip-permissions", "--model", "--output-format"],
            "invalid_flags": ["--always-approve", "--non-interactive"],
            "required_flags": ["--dangerously-skip-permissions"],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--print",
        },
        "network_deps": {
            "required_endpoints": [],
            "optional_endpoints": [],
        },
        "roles": ["architect", "builder"],
        "env_passthrough": [],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
    "codex": {
        "cli": "codex",
        "can_gh_write": False,
        # 'exec' subcommand + '-' reads prompt from stdin without requiring a TTY.
        # 'codex exec' sets approval:never by default — no bypass flag needed.
        # '-s workspace-write' confines writes to workdir + /tmp while allowing
        # model-generated file edits. Do NOT add --dangerously-bypass-approvals-and-sandbox:
        # it silently overrides -s and runs at danger-full-access (full host access).
        "non_interactive_flags": [
            "exec", "-",
            "-s", "workspace-write",
        ],
        "dispatch_flags": {
            # Codex CLI renamed --approval-policy → --ask-for-approval (values:
            # untrusted|on-request|never). TC-2 scans `codex --help` for these names.
            # Keep --sandbox as a valid long form of -s used in non_interactive_flags.
            "valid_flags": ["--ask-for-approval", "--model", "--sandbox"],
            "invalid_flags": [
                "--dangerously-bypass-approvals-and-sandbox",
                "--dangerously-skip-permissions",
                "--print",
                "--approval-policy",  # removed from Codex CLI; must not reappear
            ],
            # Sandbox mode is already supplied with its value via non_interactive_flags
            # (-s workspace-write). Do NOT put --sandbox here: required_flags are appended
            # as bare flags with no values by _dispatch_flags_for_agent(), and a bare
            # --sandbox makes codex CLI fail with "a value is required".
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--version",
        },
        "network_deps": {
            "required_endpoints": [],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "env_passthrough": [],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
    "agy": {
        "cli": "agy",
        "can_gh_write": False,
        "non_interactive_flags": [],
        "prompt_flag": "-p",     # placed last: agy -p "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--print", "--model", "--add-dir", "--sandbox", "--dangerously-skip-permissions"],
            "invalid_flags": ["--always-approve", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "unbuffered",
            "env_vars_required": ["PYTHONUNBUFFERED=1"],
            "non_interactive_flag": "-p",
        },
        "network_deps": {
            "required_endpoints": ["generativelanguage.googleapis.com:443", "oauth2.googleapis.com:443"],
            "optional_endpoints": [],
        },
        "auth_check": {
            "probe": ["agy", "--version"],
            "required_paths": ["~/.gemini/antigravity-cli/jetski_state.pbtxt"],
            "unauthenticated_markers": [
                "not signed in",
                "sign in",
                "login",
            ],
        },
        "roles": ["builder", "verifier"],
        "env_passthrough": [],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
    "grok": {
        "cli": "grok",
        "can_gh_write": True,
        "non_interactive_flags": [],
        "prompt_flag": "--single",  # placed last: grok --single "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--always-approve", "--output-format", "--model", "--single"],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--single",
        },
        "network_deps": {
            "required_endpoints": ["cli-chat-proxy.grok.com:443"],
            "optional_endpoints": [],
        },
        "auth_check": {
            "probe": ["grok", "--version"],
            "unauthenticated_markers": [
                "not signed in",
                "sign in",
                "login",
            ],
        },
        "roles": ["builder", "architect"],
        "env_passthrough": [],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
    },
    "local": {
        "cli": "aider",
        "can_gh_write": False,
        "non_interactive_flags": [],
        "dispatch_flags": {
            "valid_flags": [
                "--no-auto-commits",
                "--yes-always",
                "--openai-api-base",
                "--model",
                "--edit-format",
            ],
            "invalid_flags": ["--dangerously-skip-permissions", "--non-interactive"],
            "required_flags": ["--no-auto-commits", "--yes-always"],
        },
        "prompt_file_flag": "--message-file",
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--version",
        },
        "network_deps": {
            "required_endpoints": ["127.0.0.1:8000"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "env_passthrough": ["OPENAI_API_KEY"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
}

# Core fleet = product-supported interactive + dispatch agents.
# local remains dispatchable via experimental path but is not in CORE_FLEET.
CORE_FLEET = frozenset({"claude", "agy", "codex", "grok"})
EXPERIMENTAL_FLEET = frozenset({"local"})
PROVEN_FRESHNESS_DAYS = 7
MATRIX_LIVE_BUDGET_USD = 10.0
AGENT_BUILDER_ONLY = frozenset({"codex"})
CORE_INSTRUCTION_FILES = {
    "claude": "CLAUDE.md",
    "agy": "GEMINI.md",
    "codex": "AGENTS.md",
    "grok": "GROK.md",
}

AGENT_PANEL_QUERY_TIMEOUT_SECONDS = {
    "codex": 300,
}


def _role_dispatch_story_id(org_role: str) -> str:
    """Deterministic synthetic story_id for role/agent_id-driven dispatches with no real story.

    Pure function — safe to call from both the read path (resolve_dispatch_harness,
    no DB access) and the write path (_write_capability_rating, seeds this ID lazily).
    Never persisted to daemon_jobs.story_id or any other real-story-consuming field.
    """
    return f"__role_dispatch_{org_role}__"
