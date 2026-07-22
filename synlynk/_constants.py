"""Shared constants used across synlynk modules."""

VERSION = "0.13.0"

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
        "dispatch_flags": ["--dangerously-skip-permissions"],
        "roles": ["architect", "builder"],
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
        "roles": ["builder"],
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
        "roles": ["builder", "verifier"],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
    "grok": {
        "cli": "grok",
        "can_gh_write": True,
        "non_interactive_flags": [],
        "prompt_flag": "--single",  # placed last: grok --always-approve --single "$PROMPT"
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--always-approve", "--output-format", "--model", "--single"],
            "invalid_flags": ["--yes", "--dangerously-skip-permissions", "--print", "--non-interactive"],
            "required_flags": ["--always-approve"],
        },
        "network_deps": {
            "required_endpoints": ["cli-chat-proxy.grok.com:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder", "architect"],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
    },
    "local": {
        "cli": "aider",
        "can_gh_write": False,
        "non_interactive_flags": [],
        "dispatch_flags": ["--no-auto-commits", "--yes-always"],
        "prompt_file_flag": "--message-file",
        "network_deps": {
            "required_endpoints": ["127.0.0.1:8080"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
}
