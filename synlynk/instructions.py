"""synlynk instructions: CLAUDE.md/GEMINI.md/AGENTS.md/.cursorrules generation and drift detection."""

import hashlib
import json
import os
import shlex
import re
import subprocess
import sys
import time
import stat
from pathlib import Path
from typing import Optional

from synlynk._constants import AGENT_CAPABILITY_BASELINES, VERSION, _INSTALL_SCRIPT_URL
from synlynk.probe import SOP_BLOCKS
from synlynk.sentinel import _write_sentinel_alert
from synlynk.taxonomy import entries_up_to_tier


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


def _current_trigger_registry_tier() -> int:
    """Return the tier used to scope trigger phrases in generated instructions.

    No live maturity-tier signal exists in committed code outside taxonomy, so
    this defaults to Tier 2 until that signal is available.
    """
    return 2


def render_trigger_phrase_section(current_tier: int) -> str:
    """Render the trigger-registry subsection injected into instruction files."""
    entries = [
        entry for entry in entries_up_to_tier(current_tier)
        if entry["audience"] == "human" and entry["trigger_phrases"]
    ]
    lines = ["## Trigger registry", ""]
    for entry in entries:
        phrases = ", ".join(f'"{phrase}"' for phrase in entry["trigger_phrases"])
        lines.append(f"- {phrases} -> `synlynk {entry['command']}`")
    return "\n".join(lines)


def render_lifecycle_checkpoint_section() -> str:
    """Render the fixed GOVERNS-lifecycle checkpoint subsection injected into
    instruction files, directly beneath the trigger registry.

    Unlike render_trigger_phrase_section, this is not derived from
    COMMAND_TAXONOMY — it's a small, hand-written set of skill-completion
    checkpoints (brainstorming-skill and writing-plans-skill conclusion),
    not a per-command phrase-matching registry.
    """
    return (
        "## Lifecycle checkpoint directives\n"
        "\n"
        "- When a brainstorming session (per the brainstorming skill) concludes with\n"
        "  an approved, written spec, and no active GOVERNS goal is linked to the\n"
        "  work: suggest `synlynk goal create --outcome <spec's one-line thesis>\n"
        "  --criterion <spec's stated success condition>` before transitioning to\n"
        "  implementation planning. This is a suggestion, not a gate — proceed if\n"
        "  the user declines or the work is explicitly one-shot/maintenance.\n"
        "- When an implementation plan (per the writing-plans skill) is approved\n"
        "  and about to enter execution, and the plan's spec has no linked goal:\n"
        "  same suggestion, offered once.\n"
        "- Do not suggest goal creation at any other point in a session (not on\n"
        "  ordinary command usage, not on phrase matches, not mid-brainstorm)."
    )


def _generate_ai_context_files(arch_context: str, git_summary: str) -> None:
    """Appends a context snapshot section to CLAUDE.md, GEMINI.md, AGENTS.md.
    Creates files if absent. Never overwrites existing content."""
    today = time.strftime("%Y-%m-%d")
    snapshot = (
        f"\n## Context Snapshot (joined {today})\n\n"
        f"### Recent Git Activity\n```\n{git_summary}\n```\n\n"
        f"### Source Architecture\n{arch_context}\n"
    )
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        if os.path.exists(fname):
            with open(fname, "a") as f:
                f.write(snapshot)
        else:
            with open(fname, "w") as f:
                f.write(f"# {fname.replace('.md', '')} — Project Context\n")
                f.write(snapshot)

def _strip_synlynk_section(path: str, marker_style: str) -> bool:
    """Remove the synlynk-managed block from a file, leaving surrounding content.

    Returns True if a section was found and removed, False otherwise.
    """
    if not os.path.exists(path):
        return False
    with open(path) as f:
        content = f.read()
    if marker_style == "none":
        os.remove(path)
        return True
    if marker_style == "html":
        pattern = r'\n?[ \t]*<!-- synlynk:start[^>]* -->[ \t]*\n.*?\n[ \t]*<!-- synlynk:end -->[ \t]*\n?'
    else:
        pattern = r'\n?[ \t]*# synlynk:start[^\n]*\n.*?\n[ \t]*# synlynk:end[ \t]*\n?'
    new_content, n = re.subn(pattern, "", content, flags=re.DOTALL)
    if n:
        with open(path, "w") as f:
            f.write(new_content.rstrip("\n") + "\n" if new_content.strip() else "")
    return bool(n)

def _extract_synlynk_section(content: str, marker_style: str = "html") -> Optional[str]:
    """Return the text inside synlynk markers, or the whole content for marker_style='none'."""
    if marker_style == "none":
        return content
    if marker_style == "html":
        m = re.search(
            r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$(.*?)^[ \t]*<!-- synlynk:end -->[ \t]*$',
            content, re.DOTALL | re.MULTILINE
        )
    else:  # hash
        m = re.search(
            r'^[ \t]*# synlynk:start[^\n]*\n(.*?)\n[ \t]*# synlynk:end[ \t]*$',
            content, re.DOTALL | re.MULTILINE
        )
    return m.group(1) if m else None

def _compute_section_sha(content: str) -> str:
    """Return first 16 hex chars of SHA-256 of content string."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _write_instruction_file(path: str, tool: str, content: str,
                             marker_style: str = "html") -> bool:
    """Write or update the synlynk block in an instruction file.

    marker_style='none': synlynk owns the whole file (overwrites).
    marker_style='html': <!-- synlynk:start --> markers.
    marker_style='hash': # synlynk:start markers.

    Behaviour:
    1. File absent            → create with markers
    2. File present, no marks → append block at end
    3. File present, has marks → replace section between markers
    Returns True always.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if marker_style == "none":
        with open(path, "w") as f:
            f.write(content)
        return True

    start = f'<!-- synlynk:start version="{VERSION}" tool="{tool}" -->'
    end = "<!-- synlynk:end -->"
    start_pattern = "<!-- synlynk:start"
    if marker_style == "hash":
        start = f'# synlynk:start version="{VERSION}"'
        end = "# synlynk:end"
        start_pattern = "# synlynk:start"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(f"{start}\n{content}\n{end}\n")
        return True

    with open(path) as f:
        existing = f.read()

    if start_pattern in existing:
        # Replace section between markers — anchored to line boundaries so inline
        # mentions of the marker strings (e.g. in prose or code blocks) are ignored.
        if marker_style == "html":
            pattern = r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$'
        else:
            pattern = r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$'
        replacement = f"{start}\n{content}\n{end}"
        new_content = re.sub(pattern, replacement, existing, flags=re.DOTALL | re.MULTILINE)
        with open(path, "w") as f:
            f.write(new_content)
        return True

    # Append block
    with open(path, "a") as f:
        f.write(f"\n{start}\n{content}\n{end}\n")
    return True

def _find_existing_doc(basename: str, target_dir: str, project_name: str) -> Optional[str]:
    """Searches for existing project doc content at alternate locations.

    Checks: root-level, project-docs/, project-prefixed variants (rxcc_memory.md),
    and uppercase variants. Returns the first path with >200 bytes of content,
    or None if nothing substantial exists.
    """
    slug = re.sub(r"[^a-z0-9]", "", project_name.lower()) if project_name else ""
    candidates = []
    # Root level (if target isn't already root)
    if target_dir not in (".", ""):
        candidates.append(basename)
    # project-docs/ (if target isn't project-docs)
    if target_dir != "project-docs":
        candidates.append(os.path.join("project-docs", basename))
    # Project-prefixed variants: rxcc_memory.md, rxcc-memory.md
    stem, ext = os.path.splitext(basename)
    if slug:
        candidates += [f"{slug}_{stem}{ext}", f"{slug}-{stem}{ext}"]
        candidates += [os.path.join("project-docs", f"{slug}_{stem}{ext}")]
    # Uppercase / alternative names
    candidates.append(basename.upper())
    for c in candidates:
        if os.path.exists(c):
            try:
                if os.path.getsize(c) > 200:
                    return c
            except OSError:
                pass
    return None

def _write_informed_skeleton(scan: dict, skip_existing: bool = True) -> list:
    """Writes project-docs skeleton, seeding from existing docs when available.

    Priority order for each file:
    1. File already exists at target path → skip (when skip_existing=True)
    2. Rich existing doc found at an alternate location → migrate content
    3. No existing content → generate skeleton from git history

    Returns list of (path, source) tuples describing what was written and why.
    """
    name = scan.get("project_name", "this project")
    desc = scan.get("description") or f"A project named {name}."
    topics = scan.get("recent_topics", [])
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    commit_count = scan.get("commit_count", 0)
    caveat = (
        "\n> ⚠ Skeleton generated from git history — results vary by commit style. "
        "Review before proceeding.\n"
        if not scan.get("has_structured_commits") else ""
    )

    recent_work = "\n".join(f"- {t}" for t in topics[:5]) or "- (no commits found)"

    fallback_roadmap = f"""\
# {name} Roadmap
{caveat}
**Positioning:** [Describe what {name} is building toward]

## Business Goals
[Define outcomes here with `synlynk goal create --outcome "..." --criterion "..."`.
Each arc below can be tagged `<!-- goal:goal-xxxxxxxx -->` to link it to a goal.]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
| v0.1.0 | Initial release | ✅ Shipped | — |
| v0.2.0 | [Next milestone] | 🔜 Next | — |

## Recent work (from git history — {commit_count} commits, {langs})
{recent_work}
"""

    fallback_memory = f"""\
# {name} Memory

## Project Overview
- **Name:** {name}
- **Description:** {desc}
- **Languages:** {langs}
- **Directories:** {", ".join(scan.get("top_dirs", [])) or "—"}

## Decisions
[Document key decisions here with [@username] attribution in team mode]

## Architecture
[Document key architectural decisions here]
"""

    fallback_todo = f"""\
# {name} — Todo

<!-- Status: [ ] active  [x] done  [-] deferred  [~] superseded  [>] absorbed -->

## Active Tasks
- [ ] Review and refine the generated roadmap.md <!-- id: 1 -->
- [ ] Review and update memory.md with actual decisions <!-- id: 2 -->
- [ ] Define first milestone in roadmap <!-- id: 3 -->

## Completed
"""

    dd = _pkg("_docs_dir")()
    targets = [
        (os.path.join(dd, "roadmap.md"), fallback_roadmap),
        (os.path.join(dd, "memory.md"),  fallback_memory),
        (os.path.join(dd, "todo.md"),    fallback_todo),
    ]

    written = []
    for path, fallback in targets:
        if skip_existing and os.path.exists(path):
            continue

        basename = os.path.basename(path)
        source = _find_existing_doc(basename, dd, name)
        if source:
            with open(source) as fh:
                content = fh.read()
            label = f"migrated from {source}"
        else:
            content = fallback
            label = "generated from git history"

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        written.append((path, label))
    return written

def _llm_enrich(agent_name: str, agent_cli: str, scan: dict) -> bool:
    """Calls the configured agent non-interactively to enrich project-docs.

    Passes the static scan result + current doc drafts as context.
    Writes enriched roadmap.md if the agent responds successfully.
    Returns True on success, False on failure.
    """
    name = scan.get("project_name", "this project")
    topics = "\n".join(f"- {t}" for t in scan.get("recent_topics", []))
    langs = ", ".join(scan.get("languages", [])) or "unknown"
    readme = scan.get("readme_summary", "")[:400]

    prompt = f"""\
You are helping initialise a synlynk project context for a software project.

Project: {name}
Description: {scan.get('description', '')}
Languages: {langs}
Commit count: {scan.get('commit_count', 0)}
Recent commit messages:
{topics}

README excerpt:
{readme}

Based on this, write a concise `roadmap.md` for this project in this exact format:

# {name} Roadmap

**Positioning:** [one sentence describing the product goal]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
[3-5 plausible milestone rows based on the commit history]

Keep it short. Infer from the evidence. Do not invent features not supported by the commits.
"""

    # Write prompt to a temp file to avoid shell escaping issues.
    os.makedirs(_pkg("PROMPTS_DIR"), exist_ok=True)
    prompt_file = os.path.join(_pkg("PROMPTS_DIR"), "llm-enrich.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    baselines = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    flags = baselines.get("non_interactive_flags", ["--print"])
    cmd = [agent_cli] + flags

    try:
        with open(prompt_file) as pf:
            result = subprocess.run(cmd, stdin=pf, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not result.stdout.strip():
            return False
        enriched = result.stdout.strip()
        with open("project-docs/roadmap.md", "w") as f:
            f.write(enriched + "\n")
        return True
    except Exception:
        return False

SECTION_SIGNALS: dict = {
    "## Live Issues SOP": [
        "live issue", "live-issue", "sev1", "sev2", "sev3", "rca", "[live-",
    ],
    "## Mid-Session Anti-Amnesia Protocol": [
        "25,000 tokens", "25k tokens", "compaction", "compaction imminent",
        "mid-session", "checkpoint every",
    ],
    "## Mandatory 4-Doc Discipline": [
        "roadmap.md", "devlog", "costs.md", "memory.md",
        "mandatory document", "four doc", "4-doc",
    ],
    "## GitHub Projects v2 Integration": [
        "updateProjectV2", "projectId", "PVT_", "PVTSSF_",
        "github projects", "programme board",
    ],
    "## Git Worktree-First Policy": [
        "git worktree", "worktree add", "never commit to main",
        "never commit to master",
    ],
}

def _is_evolved_repo(content: str) -> bool:
    """Returns True if file content indicates evolved (non-template) agent instructions."""
    if len(content.splitlines()) > 100:
        return True
    unknown = sum(
        1 for line in content.splitlines()
        if line.startswith("## ") and line.rstrip() not in SECTION_SIGNALS
    )
    return unknown >= 3

def _is_section_covered(content: str, section_header: str) -> bool:
    """Returns True if file content semantically covers a synlynk section (2+ signals)."""
    signals = SECTION_SIGNALS.get(section_header, [])
    content_lower = content.lower()
    matches = sum(1 for sig in signals if sig.lower() in content_lower)
    return matches >= 2

def _extract_gh_ids(content: str) -> dict:
    """Extracts GH Projects v2 node IDs from file content.

    Returns {"project_id": str | None}.
    """
    result = {"project_id": None}
    match = re.search(r'(PVT_[A-Za-z0-9_]+)', content)
    if match:
        result["project_id"] = match.group(1)
    return result

def _build_templates(org: str = None, repo: str = None, project_id: str = None,
                     owner: str = None, agent_slots: dict = None) -> dict:
    """Returns TEMPLATES dict with parameterized values filled in."""
    _pid = project_id or "TODO: PROJECT_ID"
    _agent_slots = agent_slots or {"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}
    _trigger_registry_section = render_trigger_phrase_section(_current_trigger_registry_tier())
    _lifecycle_checkpoint_section = render_lifecycle_checkpoint_section()
    _session_protocol = """\
## Session Start (every session, no exceptions)
1. Run: `git config user.name` — this is your @username for all attribution
2. Run: `synlynk watch status` — if stopped, run `synlynk watch start`
3. Read: `.synlynk/context.md` — your full project state snapshot
4. Check `.synlynk/sentinel.md` for any active alerts
5. Greet with 3 rows:
   - Row 1: Last task YOU completed [by @username] — from your devlog entry
   - Row 2: Your next active task — from project-docs/todo.md
   - Row 3 (team mode only): Last 1 entry per teammate from project-docs/devlogs/

## During the session
- Update task status in project-docs/todo.md — do NOT delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message
"""

    _worktree_policy = """\
## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a dedicated worktree for every feature or fix:
```
git worktree add ../feat+<name> feat/<agent-prefix>/<name>
git branch --show-current   # confirm before every commit
```
Delete the worktree only after its branch is merged.
"""

    _live_issues_sop = """\
## Live Issues SOP
Production defects use `[LIVE-N]` issues. N increments per project per incident.

| Severity | Trigger | RCA |
|:---|:---|:---|
| Sev1 | Core broken / data loss / correctness bug | `docs/rca/YYYY-MM-DD-LIVE-N-<slug>.md` |
| Sev2 | Major feature degraded, workaround exists | Comment-level RCA on ticket |
| Sev3 | Minor UX / edge case | None required |

Process: Declare → Investigate (no fixes before root cause confirmed) → Post findings as issue comment → Sev1: write RCA doc → Action tickets (`live-issue sev<N> priority:p0`) → Resolution comment → Close.
"""

    _anti_amnesia = """\
## Mid-Session Anti-Amnesia Protocol
**Phase 1 (context ≤ 75%):** Every ~25,000 tokens — write devlog entry + memory update.
Commit: `docs: mid-session checkpoint [N] — <topic>`

**Phase 2 (context > 75%):** Every ~5,000 tokens — same + add `⚠️ Compaction imminent:` rescue bullet listing open threads and "about to do X" states.

Any numbered list of fixes, options, or recommendations: write to devlog in the same response — never wait.
"""

    _four_doc = """\
## Mandatory 4-Doc Discipline
Update all four during the session, not only at session end:
- `project-docs/roadmap.md` — status on in-progress items
- `project-docs/devlogs/<username>.md` — append at each task boundary
- `project-docs/costs.md` — log each significant AI operation
- `project-docs/memory.md` — decisions with `[@username]` attribution
"""

    _ghp_block = (
        "## GitHub Projects v2 Integration\n"
        "Move board items via GraphQL. Replace TODO values with your project's IDs.\n\n"
        "```graphql\n"
        "mutation MoveItem {\n"
        "  updateProjectV2ItemFieldValue(input: {\n"
        f'    projectId: "{_pid}"\n'
        '    itemId: "<item-node-id>"\n'
        '    fieldId: "TODO: STATUS_FIELD_ID"\n'
        '    value: { singleSelectOptionId: "TODO: IN_PROGRESS_OPTION_ID" }\n'
        "  }) { projectV2Item { id } }\n"
        "}\n"
        "```\n\n"
        "Look up field/option IDs:\n"
        "```bash\n"
        f"gh api graphql -f query='{{ node(id: \"{_pid}\") {{ ... on ProjectV2 {{"
        " fields(first: 20) { nodes { ... on ProjectV2SingleSelectField"
        " { id name options { id name } } } } } } } }'\n"
        "```\n"
    )

    _synlynk_start = """\
## synlynk Start
```bash
synlynk start <issue-id>    # claims board item, injects context, launches agent session
```
"""

    _sop_section = "\n".join(SOP_BLOCKS) + "\n"

    _claude_md = (
        "# synlynk Claude Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** claude-sonnet-4-6\n"
        "- **Commit trailer:** `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`\n"
        "- **Branch prefix:** `feat/claude/` or `fix/claude/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/claude/<description>` — new functionality\n"
        "- `fix/claude/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _sop_section
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )

    _gemini_md = (
        "# synlynk AGY (AntiGravity) Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** agy-2.x\n"
        "- **Commit trailer:** `Co-Authored-By: AGY <noreply@antigravity.dev>`\n"
        "- **Branch prefix:** `feat/agy/` or `fix/agy/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/agy/<description>` — new functionality\n"
        "- `fix/agy/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _sop_section
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )

    _agents_md = (
        "# synlynk Codex Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** openai-codex\n"
        "- **Commit trailer:** `Co-Authored-By: Codex <noreply@openai.com>`\n"
        "- **Branch prefix:** `feat/codex/` or `fix/codex/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/codex/<description>` — new functionality\n"
        "- `fix/codex/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _sop_section
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )

    _grok_md = (
        "# synlynk Grok Instructions\n\n"
        "## Identity & Attribution\n"
        "- **Engine:** grok-composer-2.5-fast\n"
        "- **Commit trailer:** `Co-Authored-By: Grok <noreply@x.ai>`\n"
        "- **Branch prefix:** `feat/grok/` or `fix/grok/`\n\n"
        "## Domain Ownership\n"
        "| Domain | Owned by this agent | Notes |\n"
        "|:---|:---|:---|\n"
        "| TODO: fill domains for this agent | | |\n\n"
        + _worktree_policy + "\n"
        "## Branch Naming\n"
        "- `feat/grok/<description>` — new functionality\n"
        "- `fix/grok/<description>` — bug fixes\n"
        "- `chore/<description>` — deps, docs, config\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _sop_section
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )

    _ai_instructions_md = (
        "# synlynk Universal AI Instructions\n\n"
        "Apply the following as your system prompt or custom instructions "
        "before starting any session in this repository.\n\n"
        + _live_issues_sop + "\n"
        + _anti_amnesia + "\n"
        + _four_doc + "\n"
        + _ghp_block + "\n"
        + _synlynk_start + "\n"
        + _session_protocol + "\n\n"
        + _trigger_registry_section + "\n\n"
        + _lifecycle_checkpoint_section
    )

    return {
        "roadmap.md": (
            "# synlynk Roadmap\n\n"
            "| Priority | Feature | Description | Status | Target Release | Owner |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            "| P0 | Project Setup | Initialize synlynk and project-docs. | In Progress | v0.1.0 | [Unassigned] |\n"
        ),
        "todo.md": (
            "# Project Todo List\n## Active Tasks\n"
            "- [ ] Initialize repository with synlynk <!-- id: 0 -->\n"
        ),
        "memory.md": (
            "# synlynk Memory\n\n## Decisions\n"
            "- **Structure:** Uses `/project-docs` for core records.\n\n"
            "## Conventions\n- **Session Protocol:** Use synlynk project-docs for context.\n"
        ),
        "costs.md": (
            "# synlynk Costs\n\n"
            "| Date | Type | Task/Command | Tokens (I/O) | Requests | Cost (USD) | Notes |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        ),
        "CLAUDE.md": _claude_md,
        "GEMINI.md": _gemini_md,
        "AGENTS.md": _agents_md,
        "GROK.md": _grok_md,
        "AI_INSTRUCTIONS.md": _ai_instructions_md,
        "config.json": json.dumps({
            "schema_version": 1,
            "budget": {"limit_usd": 10.0, "limit_requests": 100},
            "watch_interval_seconds": 30,
            "org": org,
            "owner": owner,
            "repo": repo,
            "project_id": project_id,
            "agent_slots": _agent_slots,
            "workgroup_agents": [],
            "last_housekeeping_date": None,
            "team": None,
            "sync_endpoint": None,
            "exec_timeout_minutes": 30,
            "stall_timeout_minutes": 30,
            "agents": {},
        }, indent=2),
    }

def _build_cursor_mdc() -> str:
    """Returns content for .cursor/rules/synlynk.mdc (Cursor MDC format, no markers)."""
    return """\
---
description: synlynk project protocol — session start, task tracking, git discipline
alwaysApply: true
---

# synlynk Protocol

## Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

## During Session
- Update task status in `project-docs/todo.md` — do not delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a worktree for every feature or fix:
```
git worktree add .worktrees/<name> feat/<name>
git branch --show-current   # confirm before every commit
```

## At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""

def _build_copilot_instructions() -> str:
    """Returns content for .github/copilot-instructions.md synlynk block (plain markdown)."""
    return """\
## synlynk Session Protocol

### Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

### During Session
- Update task status in `project-docs/todo.md` — do not delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary
- Never commit directly to `main`/`master` — create a worktree or branch first

### At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time
"""

def _build_windsurf_rules() -> str:
    """Returns content for .windsurfrules synlynk block (terse directive format)."""
    return """\
Read .synlynk/context.md at session start.
Update task status in project-docs/todo.md ([ ] active [x] done [-] deferred [~] superseded [>] absorbed).
Run `synlynk checkpoint` at task boundaries.
Never commit directly to main or master — use a worktree.
Append decisions to project-docs/memory.md with [@username].
Check .synlynk/sentinel.md for active alerts before starting work.
"""

_INSTRUCTIONS_MANIFEST = ".synlynk/instructions.json"

_MARKER_STYLE_FOR_TOOL = {
    "claude":    "html",
    "agy":       "html",
    "codex":     "html",
    "grok":      "html",
    "cursor":    "none",
    "copilot":   "html",
    "windsurf":  "hash",
    "universal": "html",
}

def _load_instruction_manifest() -> dict:
    """Returns files dict from .synlynk/instructions.json, or {} if absent."""
    if not os.path.exists(_INSTRUCTIONS_MANIFEST):
        return {}
    try:
        return json.load(open(_INSTRUCTIONS_MANIFEST)).get("files", {})
    except (json.JSONDecodeError, KeyError):
        return {}

def _write_instruction_manifest(entries: dict) -> None:
    """Write .synlynk/instructions.json with schema_version, synlynk_version, and file SHAs."""
    os.makedirs(os.path.dirname(_INSTRUCTIONS_MANIFEST), exist_ok=True)
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    existing = _load_instruction_manifest()
    existing.update({
        path: {
            "tool": info["tool"],
            "sha": info["sha"],
            "last_checked": ts,
        }
        for path, info in entries.items()
    })
    manifest = {
        "schema_version": 1,
        "generated_at": ts,
        "synlynk_version": VERSION,
        "files": existing,
    }
    with open(_INSTRUCTIONS_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

_PRE_COMMIT_HOOK_MARKER = "-m synlynk instructions status --pre-commit"

def _build_pre_commit_hook_script(repo_root: Path) -> str:
    """Build the pre-commit hook script for a specific repo root."""
    repo_root_str = shlex.quote(str(Path(repo_root).resolve()))
    code_root_str = shlex.quote(str(Path(__file__).resolve().parents[1]))
    python_exe = shlex.quote(sys.executable)
    return f"""#!/bin/sh
# Installed by synlynk init to gate instruction drift before commit.
REPO_ROOT={repo_root_str}
CODE_ROOT={code_root_str}
cd "$REPO_ROOT" || exit 1
PYTHONPATH="$CODE_ROOT${{PYTHONPATH:+:$PYTHONPATH}}" exec {python_exe} -m synlynk instructions status --pre-commit
"""

def _resolve_git_dir(repo_root: Path) -> Path:
    """Resolve the actual git dir for a repo root, including worktree .git files."""
    git_path = Path(repo_root) / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        raw = git_path.read_text().strip()
        if raw.startswith("gitdir:"):
            gitdir = raw.split("gitdir:", 1)[1].strip()
            gitdir_path = Path(gitdir)
            if not gitdir_path.is_absolute():
                gitdir_path = (Path(repo_root) / gitdir_path).resolve()
            return gitdir_path
    return git_path

def install_pre_commit_hook(repo_root: Path) -> None:
    """Install a git pre-commit hook that blocks unreviewed instruction drift."""
    git_dir = _resolve_git_dir(Path(repo_root))
    hook_path = git_dir / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)

    existing = hook_path.read_text() if hook_path.exists() else ""
    if _PRE_COMMIT_HOOK_MARKER in existing:
        return
    if existing and not existing.startswith("#!"):
        raise RuntimeError(
            f"unexpected pre-commit hook content at {hook_path}, not overwriting"
        )

    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    content += _build_pre_commit_hook_script(Path(repo_root))

    hook_path.write_text(content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def _check_instruction_drift() -> list:
    """Check tracked instruction files for external modifications to the synlynk section.

    Fires INSTRUCTION_DRIFT sentinel entries for any drifted file.
    Updates manifest SHA after each check (deduplicates re-firing).
    Returns list of drifted file paths.
    """
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        return []

    drifted = []
    updated_entries = {}
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')

    for fpath, info in manifest_data.items():
        tool = info.get("tool", "unknown")
        recorded_sha = info.get("sha", "")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        file_content = open(fpath).read()
        section = _extract_synlynk_section(file_content, marker_style)
        if section is None:
            updated_entries[fpath] = {**info, "last_checked": ts}
            continue

        current_sha = _compute_section_sha(section)
        updated_entries[fpath] = {**info, "sha": current_sha, "last_checked": ts}

        if current_sha != recorded_sha:
            drifted.append(fpath)
            _write_sentinel_alert(
                "WARN", "INSTRUCTION_DRIFT",
                f"{fpath} (tool: {tool}) — synlynk section modified externally. "
                f"Run `synlynk instructions diff {fpath}` to review. "
                f"Run `synlynk instructions update {fpath}` to reset. "
                f"[ack: synlynk instructions ack {fpath}]"
            )

    _write_instruction_manifest(updated_entries)
    return drifted

def cmd_instructions_status(pre_commit: bool = False) -> None:
    """Print status table for all tracked instruction files."""
    if pre_commit:
        drifted = _check_instruction_drift()
        if drifted:
            print("  Instruction drift detected. Commit blocked.")
            for fpath in drifted:
                print(
                    f"  {fpath}: run `synlynk instructions diff {fpath}`, "
                    f"`synlynk instructions update {fpath}`, or "
                    f"`synlynk instructions ack {fpath}`"
                )
            sys.exit(1)
        return

    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    col = {"file": 38, "tool": 10, "status": 16, "checked": 12}
    header = (f"{'File':<{col['file']}}{'Tool':<{col['tool']}}"
              f"{'Status':<{col['status']}}{'Last checked':<{col['checked']}}")
    print(f"\n{_pkg('_BOLD')}{header}{_pkg('_RESET')}")
    print("─" * (col["file"] + col["tool"] + col["status"] + col["checked"]))

    for fpath, info in sorted(manifest_data.items()):
        tool = info.get("tool", "?")
        recorded_sha = info.get("sha", "")
        checked = info.get("last_checked", "")[:10]
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if not os.path.exists(fpath):
            status = f"{_pkg('_YELLOW')}✗ missing{_pkg('_RESET')}"
        else:
            file_content = open(fpath).read()
            section = _extract_synlynk_section(file_content, marker_style)
            if section is None:
                status = f"{_pkg('_YELLOW')}? no markers{_pkg('_RESET')}"
            elif _compute_section_sha(section) != recorded_sha:
                status = f"{_pkg('_YELLOW')}⚠ drifted{_pkg('_RESET')}"
            else:
                has_user = bool(re.sub(
                    r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$',
                    '', file_content, flags=re.DOTALL | re.MULTILINE
                ).strip() if marker_style == "html" else re.sub(
                    r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$',
                    '', file_content, flags=re.DOTALL | re.MULTILINE
                ).strip())
                status = (f"{_pkg('_DIM')}+ user-content{_pkg('_RESET')}" if has_user
                          else f"{_pkg('_GREEN')}✓ clean{_pkg('_RESET')}")

        print(f"{fpath:<{col['file']}}{tool:<{col['tool']}}"
              f"{status:<{col['status'] + 10}}{checked}")
    print()

def cmd_instructions_diff(file_path: Optional[str] = None) -> None:
    """Show user/tool content outside the synlynk section for deliberate review."""
    manifest_data = _load_instruction_manifest()
    if not manifest_data:
        print("  No instruction manifest found. Run `synlynk init` first.")
        return

    targets = ([file_path] if file_path else list(manifest_data.keys()))
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked in manifest")
            continue
        if not os.path.exists(fpath):
            print(f"  {fpath}: {_pkg('_YELLOW')}missing{_pkg('_RESET')}")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")
        file_content = open(fpath).read()

        print(f"\n{_pkg('_BOLD')}── {fpath} (tool: {tool}) ──{_pkg('_RESET')}")

        if marker_style == "html":
            user_content = re.sub(
                r'^[ \t]*<!-- synlynk:start[^>]* -->[ \t]*$.*?^[ \t]*<!-- synlynk:end -->[ \t]*$',
                '', file_content, flags=re.DOTALL | re.MULTILINE
            ).strip()
        elif marker_style == "hash":
            user_content = re.sub(
                r'^[ \t]*# synlynk:start[^\n]*$.*?^[ \t]*# synlynk:end[ \t]*$',
                '', file_content, flags=re.DOTALL | re.MULTILINE
            ).strip()
        else:
            user_content = ""

        if user_content:
            print(f"{_pkg('_DIM')}User/tool content outside synlynk section:{_pkg('_RESET')}")
            print(user_content)
        else:
            print(f"{_pkg('_DIM')}No user content outside synlynk section.{_pkg('_RESET')}")

def cmd_instructions_update(file_path: Optional[str] = None,
                             new_content: Optional[str] = None) -> None:
    """Re-generate the synlynk section for file(s) and refresh manifest SHAs.

    file_path=None updates all tracked files.
    new_content is used in tests; production callers pass None and content
    is rebuilt from the relevant template function.
    """
    manifest_data = _load_instruction_manifest()
    targets = ([file_path] if file_path else list(manifest_data.keys()))

    _tool_content_builders = {
        "cursor":    (_build_cursor_mdc,            "none"),
        "copilot":   (_build_copilot_instructions,  "html"),
        "windsurf":  (_build_windsurf_rules,        "hash"),
        "universal": (lambda: _build_templates().get("AI_INSTRUCTIONS.md", ""), "html"),
    }

    updated = {}
    for fpath in targets:
        if fpath not in manifest_data:
            print(f"  {fpath}: not tracked — skipping")
            continue
        info = manifest_data[fpath]
        tool = info.get("tool", "unknown")
        marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")

        if new_content is not None:
            content = new_content
        elif tool in _tool_content_builders:
            builder, _ = _tool_content_builders[tool]
            content = builder()
        else:
            templates = _build_templates()
            fname = os.path.basename(fpath)
            content = templates.get(fname, "")

        _write_instruction_file(fpath, tool, content, marker_style)

        if os.path.exists(fpath):
            section = _extract_synlynk_section(open(fpath).read(), marker_style)
            if section:
                updated[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}

        print(f"  {_pkg('_GREEN')}✓{_pkg('_RESET')} Updated {fpath}")

    if updated:
        _write_instruction_manifest(updated)

def cmd_instructions_ack(file_path: str) -> None:
    """Acknowledge an INSTRUCTION_DRIFT event for a specific file.

    Removes matching INSTRUCTION_DRIFT lines from sentinel.md.
    """
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return
    with open(sentinel_file) as f:
        lines = f.readlines()
    filtered = [
        l for l in lines
        if not ("INSTRUCTION_DRIFT" in l and file_path in l)
    ]
    with open(sentinel_file, "w") as f:
        f.writelines(filtered)
    print(f"  {_pkg('_GREEN')}✓{_pkg('_RESET')} Acknowledged drift for {file_path}")
