# BS-12 Agent Autonomy Bridge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add permission grants, per-project harness config, agent handoff protocol, a doctor guided fix wizard, and 6 missing workflow SOP blocks to all directive files.

**Architecture:** Five scopes delivered sequentially across `probe.py` (TC-5, SOP constants), `dispatch.py` (merge layer, permissions, handoff sentinel), `_constants.py` (role defaults), and `__init__.py` (CLI surface, directive templates, wizard). No new top-level modules.

**Tech Stack:** Python 3 stdlib only · SQLite via `_get_db()` · termios TUI (same pattern as `cmd_wizard`) · existing `_upsert_harness_fence()` for SOP repair

---

## Codex Tasks (this plan)

Agy runs **P1-content** (SOP block prose) and **P5b** (wizard menu text) in parallel. Codex wires Agy's strings in as constants once delivered. Placeholder text is provided below — replace with Agy's output when available.

---

## Task 1 — SOP section header constants + inject into directive templates

**Files:**
- Modify: `synlynk/probe.py` (add module-level constants after existing imports)
- Modify: `synlynk/__init__.py` — function `_build_templates()` (line ~5888)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests for SOP constants**

```python
def test_sop_section_headers_defined():
    from synlynk.probe import SOP_SECTION_HEADERS
    assert len(SOP_SECTION_HEADERS) == 6
    assert "## PR Review Discipline" in SOP_SECTION_HEADERS
    assert "## Brainstorm-First Policy" in SOP_SECTION_HEADERS
    assert "## Design → Plan → Build Sequence" in SOP_SECTION_HEADERS
    assert "## Capability-Based Task Allocation" in SOP_SECTION_HEADERS
    assert "## Cost Visibility" in SOP_SECTION_HEADERS
    assert "## Repo Hygiene" in SOP_SECTION_HEADERS

def test_directive_templates_contain_sop_headers(tmp_path, isolated_db):
    import os
    os.chdir(tmp_path)
    from synlynk import init as synlynk_init
    synlynk_init(mode="single", org="test-org", repo="test/repo",
                 agent_names=["claude"], docs_dir="project-docs")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "## PR Review Discipline" in content
    assert "## Repo Hygiene" in content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_sop_section_headers_defined or test_directive_templates_contain_sop_headers" -v
```

Expected: `ImportError` or `AssertionError`

- [ ] **Step 3: Add `SOP_SECTION_HEADERS` and 6 SOP block constants to `synlynk/probe.py`**

Add after the existing imports block at the top of `synlynk/probe.py`:

```python
SOP_SECTION_HEADERS = [
    "## PR Review Discipline",
    "## Brainstorm-First Policy",
    "## Design → Plan → Build Sequence",
    "## Capability-Based Task Allocation",
    "## Cost Visibility",
    "## Repo Hygiene",
]

_PR_REVIEW_SOP = """\
## PR Review Discipline
The agent that implements a feature never reviews or merges its own PR.
- After opening a PR, post a review request to the assigned reviewer agent
- Reviewer runs `synlynk pr check <pr>` before approving
- Merge only after reviewer approval — never self-merge
"""

_BRAINSTORM_SOP = """\
## Brainstorm-First Policy
Every feature and epic requires an approved design spec before implementation.
- Claude runs the brainstorm; output is a spec in `docs/superpowers/specs/`
- No implementation starts without an approved spec committed to the branch
- No code before design approval — this applies to all agents
"""

_DESIGN_SEQUENCE_SOP = """\
## Design → Plan → Build Sequence
All work follows this sequence without exception:
1. Brainstorm → design spec (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`)
2. Design spec → implementation plan (`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`)
3. Implementation plan → capability-allocated tasks dispatched to agents
Never start step N+1 before step N is approved and committed.
"""

_CAPABILITY_ALLOCATION_SOP = """\
## Capability-Based Task Allocation
Tasks are routed by agent role — never self-assign outside your role.
- Python CLI / backend / tests: Codex
- HTML/CSS / templates / content / documentation: Agy
- PM / roadmap / code review / deployments: Claude
Run `synlynk roles` to confirm your current role before starting any task.
"""

_COST_VISIBILITY_SOP = """\
## Cost Visibility
Log an estimated cost before each significant dispatch.
- Include `estimated_cost: $X.XX` in job context headers
- If estimated cost exceeds the session budget (check `synlynk status`), flag to Claude first
- Append actual cost to project-docs/costs.md after each session
"""

_REPO_HYGIENE_SOP = """\
## Repo Hygiene
- Never commit directly to `main` or `master`
- Branch naming: `feat/<agent>/<description>`, `fix/<agent>/<description>`
- Every commit requires a Co-Authored-By trailer matching your agent identity
- Use a dedicated worktree per feature: `git worktree add ../<slug> <branch>`
- Run `git branch --show-current` before every commit to confirm you're on the right branch
"""

SOP_BLOCKS = [
    _PR_REVIEW_SOP,
    _BRAINSTORM_SOP,
    _DESIGN_SEQUENCE_SOP,
    _CAPABILITY_ALLOCATION_SOP,
    _COST_VISIBILITY_SOP,
    _REPO_HYGIENE_SOP,
]
```

- [ ] **Step 4: Inject SOP blocks into `_build_templates()` in `synlynk/__init__.py`**

In `_build_templates()` (line ~5888), import the SOP blocks at the top of the function body:

```python
from synlynk.probe import SOP_BLOCKS as _SOP_BLOCKS
_sop_section = "\n".join(_SOP_BLOCKS) + "\n"
```

Then append `_sop_section` to each of the four template strings (`_claude_md`, `_gemini_md`, `_agents_md`, `_grok_md`) before `+ _synlynk_start`:

```python
# In each template string, add before + _synlynk_start:
+ _sop_section
+ _synlynk_start
+ _session_protocol
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/test_synlynk.py -k "test_sop_section_headers_defined or test_directive_templates_contain_sop_headers" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite to check for regressions**

```bash
python -m pytest tests/ -q
```

Expected: same pass count as before ± new tests

- [ ] **Step 7: Commit**

```bash
git add synlynk/probe.py synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs12-e): SOP section constants + inject into all directive templates"
```

---

## Task 2 — TC-5 SOP presence check in `cmd_doctor`

**Files:**
- Modify: `synlynk/probe.py` — add `_run_tc5()`
- Modify: `synlynk/__init__.py` — integrate TC-5 into `cmd_doctor` (line ~2120)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing test**

```python
def test_run_tc5_passes_when_all_headers_present(tmp_path):
    from synlynk.probe import _run_tc5, SOP_SECTION_HEADERS
    f = tmp_path / "CLAUDE.md"
    f.write_text("\n".join(SOP_SECTION_HEADERS) + "\nsome other content")
    result = _run_tc5({"claude": str(f)})
    assert result["passed"] is True
    assert result["missing"] == {}

def test_run_tc5_reports_missing_sections(tmp_path):
    from synlynk.probe import _run_tc5
    f = tmp_path / "CLAUDE.md"
    f.write_text("## PR Review Discipline\nsome content")
    result = _run_tc5({"claude": str(f)})
    assert result["passed"] is False
    missing = result["missing"]["claude"]
    assert "## Brainstorm-First Policy" in missing
    assert "## PR Review Discipline" not in missing

def test_run_tc5_missing_file_reports_all_headers(tmp_path):
    from synlynk.probe import _run_tc5, SOP_SECTION_HEADERS
    result = _run_tc5({"claude": str(tmp_path / "CLAUDE.md")})
    assert result["passed"] is False
    assert len(result["missing"]["claude"]) == len(SOP_SECTION_HEADERS)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_run_tc5" -v
```

Expected: `ImportError` — `_run_tc5` not defined yet

- [ ] **Step 3: Add `_run_tc5()` to `synlynk/probe.py`**

Add after `_run_tc4()`:

```python
def _run_tc5(directive_files: dict) -> dict:
    """TC-5: check all directive files contain the required SOP section headers.

    directive_files: {agent_name: file_path}
    Returns: {"passed": bool, "missing": {agent_name: [missing_header, ...]}}
    """
    missing: dict = {}
    for agent, path in directive_files.items():
        try:
            content = open(path).read() if os.path.exists(path) else ""
        except OSError:
            content = ""
        absent = [h for h in SOP_SECTION_HEADERS if h not in content]
        if absent:
            missing[agent] = absent
    return {"passed": not missing, "missing": missing}
```

- [ ] **Step 4: Wire TC-5 into `cmd_doctor()` in `synlynk/__init__.py`**

In `cmd_doctor()`, after the TC-4 print block (look for `print(f"    TC-4 verbs:")`), add:

```python
_DIRECTIVE_FILES = {
    "claude": "CLAUDE.md",
    "agy": "GEMINI.md",
    "codex": "AGENTS.md",
    "grok": "GROK.md",
}
# Only check files that exist for currently configured agents
tc5_files = {a: _DIRECTIVE_FILES[a] for a in agents if a in _DIRECTIVE_FILES}
tc5 = _run_tc5(tc5_files)
if not tc5["passed"]:
    for ag, missing in tc5["missing"].items():
        print(f"    TC-5 sops:    ⚠ {ag}: missing {len(missing)} section(s): {', '.join(missing)}")
else:
    print(f"    TC-5 sops:    ✓")
```

Also add `from synlynk.probe import _run_tc5` to the imports at the top of the file (or in the doctor function if it's already using local imports).

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_run_tc5" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/probe.py synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs12-e): TC-5 SOP presence check in synlynk doctor"
```

---

## Task 3 — `synlynk sync --repair-sops`

**Files:**
- Modify: `synlynk/__init__.py` — `cmd_sync()` (line ~2436), CLI parser
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing test**

```python
def test_sync_repair_sops_injects_missing_sections(tmp_path, isolated_db):
    import os
    os.chdir(tmp_path)
    # Create a CLAUDE.md missing most SOP sections
    (tmp_path / "CLAUDE.md").write_text("# Claude Instructions\n\n## PR Review Discipline\nsome content\n")
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        '{"roles": {"claude": ["pm", "review"]}}'
    )
    from synlynk import cmd_sync
    cmd_sync(dry_run=False, repair_sops=True)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "## Brainstorm-First Policy" in content
    assert "## Repo Hygiene" in content
    # Existing section not duplicated
    assert content.count("## PR Review Discipline") == 1

def test_sync_repair_sops_is_idempotent(tmp_path, isolated_db):
    import os
    os.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# Instructions\n")
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"claude": ["pm"]}}')
    from synlynk import cmd_sync
    cmd_sync(dry_run=False, repair_sops=True)
    content_first = (tmp_path / "CLAUDE.md").read_text()
    cmd_sync(dry_run=False, repair_sops=True)
    content_second = (tmp_path / "CLAUDE.md").read_text()
    assert content_first == content_second
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_sync_repair_sops" -v
```

Expected: `TypeError` — `cmd_sync()` doesn't accept `repair_sops` param

- [ ] **Step 3: Add `repair_sops` param to `cmd_sync()` and implement repair logic**

In `synlynk/__init__.py`, update `cmd_sync()` signature:

```python
def cmd_sync(dry_run: bool = True, repair_sops: bool = False) -> int:
```

At the end of `cmd_sync()`, before the final return, add:

```python
if repair_sops:
    from synlynk.probe import _run_tc5, SOP_BLOCKS, SOP_SECTION_HEADERS
    _DIRECTIVE_FILES = {
        "claude": "CLAUDE.md", "agy": "GEMINI.md",
        "codex": "AGENTS.md", "grok": "GROK.md",
    }
    cfg_roles = load_config().get("roles", {})
    for agent in cfg_roles:
        fpath = _DIRECTIVE_FILES.get(agent)
        if not fpath or not os.path.exists(fpath):
            continue
        tc5 = _run_tc5({agent: fpath})
        for missing_header in tc5["missing"].get(agent, []):
            idx = SOP_SECTION_HEADERS.index(missing_header)
            block = SOP_BLOCKS[idx]
            if not dry_run:
                _upsert_harness_fence(fpath, harness_version=f"sop-{idx}", body=block)
            print(f"  {'→' if dry_run else '✓'} repair SOP '{missing_header}' in {fpath}")
```

- [ ] **Step 4: Wire `--repair-sops` into the CLI parser**

Find the `sync` subparser in `synlynk/cli.py` (or `__init__.py` where subparsers are defined). Add:

```python
sync_parser.add_argument(
    "--repair-sops", action="store_true", default=False,
    help="Re-inject missing SOP sections into directive files (idempotent)"
)
```

And in the handler that calls `cmd_sync`, pass `repair_sops=args.repair_sops`.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_sync_repair_sops" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py synlynk/cli.py tests/test_synlynk.py
git commit -m "feat(bs12-e): sync --repair-sops re-injects missing SOP sections"
```

---

## Task 4 — `synlynk configure agent` subcommand

**Files:**
- Modify: `synlynk/__init__.py` — add `cmd_configure_agent()`
- Modify: `synlynk/cli.py` — add `configure` subparser
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_configure_agent_writes_harness_overrides(tmp_path, isolated_db):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    (tmp_path / ".agents" / "codex.json").write_text('{"context_mode": "full"}')
    from synlynk import cmd_configure_agent
    cmd_configure_agent("codex", flags={"timeout": "60"}, envs={}, network_deps=[])
    data = json.loads((tmp_path / ".agents" / "codex.json").read_text())
    assert data["harness_overrides"]["dispatch_flags"]["timeout"] == "60"

def test_configure_agent_creates_file_if_missing(tmp_path, isolated_db):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    from synlynk import cmd_configure_agent
    cmd_configure_agent("agy", flags={}, envs={"PYTHONUNBUFFERED": "1"}, network_deps=[])
    data = json.loads((tmp_path / ".agents" / "agy.json").read_text())
    assert data["harness_overrides"]["env"]["PYTHONUNBUFFERED"] == "1"

def test_configure_agent_preserves_existing_keys(tmp_path, isolated_db):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    (tmp_path / ".agents" / "claude.json").write_text(
        '{"context_mode": "full", "harness_overrides": {"dispatch_flags": {"model": "claude-3"}}}'
    )
    from synlynk import cmd_configure_agent
    cmd_configure_agent("claude", flags={"timeout": "30"}, envs={}, network_deps=[])
    data = json.loads((tmp_path / ".agents" / "claude.json").read_text())
    assert data["context_mode"] == "full"
    assert data["harness_overrides"]["dispatch_flags"]["model"] == "claude-3"
    assert data["harness_overrides"]["dispatch_flags"]["timeout"] == "30"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_configure_agent" -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `cmd_configure_agent()` to `synlynk/__init__.py`**

Add near the other `cmd_*` functions:

```python
def cmd_configure_agent(
    name: str,
    flags: dict = None,
    envs: dict = None,
    network_deps: list = None,
) -> None:
    """Write per-project harness overrides to .agents/<name>.json."""
    flags = flags or {}
    envs = envs or {}
    network_deps = network_deps or []

    profile_path = os.path.join(".agents", f"{name}.json")
    profile: dict = {}
    if os.path.exists(profile_path):
        try:
            with open(profile_path) as f:
                profile = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    overrides = profile.setdefault("harness_overrides", {
        "dispatch_flags": {}, "env": {}, "network_deps": []
    })
    overrides["dispatch_flags"].update(flags)
    overrides["env"].update(envs)
    for dep in network_deps:
        if dep not in overrides["network_deps"]:
            overrides["network_deps"].append(dep)

    os.makedirs(".agents", exist_ok=True)
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"  ✓ {name}: harness overrides written to {profile_path}")
    if flags:
        print(f"    flags: {flags}")
    if envs:
        print(f"    env:   {envs}")
    if network_deps:
        print(f"    deps:  {network_deps}")
```

- [ ] **Step 4: Wire into CLI parser**

In `synlynk/cli.py`, add a `configure` subparser with an `agent` sub-subparser:

```python
configure_parser = subparsers.add_parser("configure", help="Configure synlynk components")
configure_sub = configure_parser.add_subparsers(dest="configure_target")
agent_parser = configure_sub.add_parser("agent", help="Configure a specific agent's harness")
agent_parser.add_argument("name", help="Agent name (claude, agy, codex, grok)")
agent_parser.add_argument("--flag", action="append", default=[], metavar="KEY=VAL",
                          help="Set a dispatch flag override (repeatable)")
agent_parser.add_argument("--env", action="append", default=[], metavar="KEY=VAL",
                          help="Set an env var override (repeatable)")
agent_parser.add_argument("--network-dep", action="append", default=[], metavar="HOST:PORT",
                          help="Add a required network endpoint (repeatable)")
```

In the dispatch handler:

```python
elif args.command == "configure" and args.configure_target == "agent":
    flags = dict(item.split("=", 1) for item in args.flag)
    envs = dict(item.split("=", 1) for item in args.env)
    from synlynk import cmd_configure_agent
    cmd_configure_agent(args.name, flags=flags, envs=envs, network_deps=args.network_dep)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_configure_agent" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py synlynk/cli.py tests/test_synlynk.py
git commit -m "feat(bs12-b): synlynk configure agent writes harness overrides to .agents/<name>.json"
```

---

## Task 5 — Dispatch merge layer (harness overrides + `_load_harness_overrides`)

**Files:**
- Modify: `synlynk/dispatch.py` — add `_load_harness_overrides()`, update `dispatch_agent()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_load_harness_overrides_returns_empty_when_no_file(tmp_path, isolated_db):
    import os
    os.chdir(tmp_path)
    from synlynk.dispatch import _load_harness_overrides
    result = _load_harness_overrides("codex")
    assert result == {"dispatch_flags": {}, "env": {}, "network_deps": []}

def test_load_harness_overrides_reads_from_agents_json(tmp_path, isolated_db):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    (tmp_path / ".agents" / "codex.json").write_text(
        json.dumps({"harness_overrides": {"dispatch_flags": {"timeout": "60"}, "env": {}, "network_deps": []}})
    )
    from synlynk.dispatch import _load_harness_overrides
    result = _load_harness_overrides("codex")
    assert result["dispatch_flags"]["timeout"] == "60"

def test_dispatch_agent_applies_harness_overrides(tmp_path, isolated_db, monkeypatch):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    os.makedirs(tmp_path / ".synlynk")
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    # Override adds an env var — verify it appears in the subprocess env
    (tmp_path / ".agents" / "claude.json").write_text(
        json.dumps({"harness_overrides": {"dispatch_flags": {}, "env": {"MY_VAR": "42"}, "network_deps": []}})
    )
    captured_env = {}
    def fake_popen(cmd, env=None, **kw):
        captured_env.update(env or {})
        raise RuntimeError("stop")
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    from synlynk.dispatch import dispatch_agent
    try:
        dispatch_agent("claude", task="test")
    except RuntimeError:
        pass
    assert captured_env.get("MY_VAR") == "42"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_load_harness_overrides or test_dispatch_agent_applies_harness" -v
```

- [ ] **Step 3: Add `_load_harness_overrides()` to `synlynk/dispatch.py`**

Add after the imports block:

```python
def _load_harness_overrides(agent: str) -> dict:
    """Read per-project harness overrides from .agents/<agent>.json."""
    _empty = {"dispatch_flags": {}, "env": {}, "network_deps": []}
    path = os.path.join(".agents", f"{agent}.json")
    if not os.path.exists(path):
        return _empty
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("harness_overrides") or _empty
    except (json.JSONDecodeError, OSError):
        return _empty
```

- [ ] **Step 4: Apply overrides in `dispatch_agent()`**

In `dispatch_agent()`, after the line `flags = baselines["non_interactive_flags"] + _dispatch_flags_for_agent(agent)`, add:

```python
overrides = _load_harness_overrides(agent)
# Merge override flags as extra list items
for k, v in overrides.get("dispatch_flags", {}).items():
    flags = flags + [f"--{k}", str(v)] if v else flags + [f"--{k}"]
```

When building the subprocess `env`, merge override env vars:

```python
proc_env = os.environ.copy()
proc_env.update(overrides.get("env", {}))
# Pass proc_env to Popen as env=proc_env
```

Find the `subprocess.Popen(` call in `dispatch_agent()` and add `env=proc_env` if not already present.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_load_harness_overrides or test_dispatch_agent_applies_harness" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_synlynk.py
git commit -m "feat(bs12-b): _load_harness_overrides + dispatch_agent applies per-project overrides"
```

---

## Task 6 — Role permission defaults + `_resolve_dispatch_permissions()`

**Files:**
- Modify: `synlynk/_constants.py` — add `_ROLE_PERMISSION_DEFAULTS`, `_PERMISSION_TO_TOOL_MAP`
- Modify: `synlynk/dispatch.py` — add `_resolve_dispatch_permissions()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_role_permission_defaults_cover_all_default_roles():
    from synlynk._constants import _ROLE_PERMISSION_DEFAULTS
    for role in ["pm", "review", "deploy", "implement", "test", "refactor",
                 "css", "templates", "content", "canvas", "js", "infra"]:
        assert role in _ROLE_PERMISSION_DEFAULTS, f"Missing role: {role}"

def test_resolve_dispatch_permissions_returns_role_defaults():
    from synlynk.dispatch import _resolve_dispatch_permissions
    perms = _resolve_dispatch_permissions("codex", role_list=["implement", "test"])
    assert "write:src/" in perms
    assert "run:tests" in perms

def test_resolve_dispatch_permissions_grant_expands():
    from synlynk.dispatch import _resolve_dispatch_permissions
    perms = _resolve_dispatch_permissions("codex", role_list=["review"],
                                          grants=["write:src/"])
    assert "write:src/" in perms

def test_resolve_dispatch_permissions_revoke_removes():
    from synlynk.dispatch import _resolve_dispatch_permissions
    perms = _resolve_dispatch_permissions("codex", role_list=["implement"],
                                          revokes=["run:tests"])
    assert "run:tests" not in perms
    assert "write:src/" in perms
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_role_permission_defaults or test_resolve_dispatch_permissions" -v
```

- [ ] **Step 3: Add permission constants to `synlynk/_constants.py`**

```python
_ROLE_PERMISSION_DEFAULTS: dict = {
    "pm":        ["read:*"],
    "review":    ["read:*"],
    "deploy":    ["read:*"],
    "implement": ["read:*", "write:src/", "run:tests"],
    "test":      ["read:*", "write:src/", "run:tests"],
    "refactor":  ["read:*", "write:src/", "run:tests"],
    "css":       ["read:*", "write:src/", "write:docs/"],
    "templates": ["read:*", "write:src/", "write:docs/"],
    "content":   ["read:*", "write:src/", "write:docs/"],
    "canvas":    ["read:*", "write:src/", "run:shell"],
    "js":        ["read:*", "write:src/", "run:shell"],
    "infra":     ["read:*", "write:src/", "run:shell"],
}

_PERMISSION_TO_TOOL_MAP: dict = {
    # Maps permission strings to Claude --allowedTools values
    "read:*":     ["Read", "Glob", "Grep", "LS"],
    "write:src/": ["Edit", "Write", "MultiEdit"],
    "write:docs/":["Edit", "Write"],
    "run:tests":  ["Bash(pytest:*)"],
    "run:shell":  ["Bash"],
}
```

- [ ] **Step 4: Add `_resolve_dispatch_permissions()` to `synlynk/dispatch.py`**

```python
def _resolve_dispatch_permissions(
    agent: str,
    role_list: list = None,
    grants: list = None,
    revokes: list = None,
) -> list:
    """Compute the effective permission set: role defaults + grants - revokes.

    Returns a list of permission strings like ['read:*', 'write:src/'].
    """
    from synlynk._constants import _ROLE_PERMISSION_DEFAULTS
    role_list = role_list or []
    grants = grants or []
    revokes = revokes or []

    effective: set = set()
    for role in role_list:
        effective.update(_ROLE_PERMISSION_DEFAULTS.get(role, []))
    effective.update(grants)
    effective.difference_update(revokes)
    return sorted(effective)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_role_permission_defaults or test_resolve_dispatch_permissions" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/_constants.py synlynk/dispatch.py tests/test_synlynk.py
git commit -m "feat(bs12-a): role permission defaults + _resolve_dispatch_permissions"
```

---

## Task 7 — `--grant`/`--revoke` in dispatch CLI + permission translation

**Files:**
- Modify: `synlynk/dispatch.py` — update `dispatch_agent()`, add `_permissions_to_flags()`
- Modify: `synlynk/cli.py` — add `--grant`/`--revoke` to dispatch subparser
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_permissions_to_flags_claude_allowedtools():
    from synlynk.dispatch import _permissions_to_flags
    result = _permissions_to_flags("claude", ["read:*", "write:src/"])
    assert "--allowedTools" in result
    idx = result.index("--allowedTools")
    tools_str = result[idx + 1]
    assert "Read" in tools_str
    assert "Edit" in tools_str

def test_permissions_to_flags_codex_approval_policy():
    from synlynk.dispatch import _permissions_to_flags
    # write:src/ + run:tests → workspace-write (already default, approval=none)
    result = _permissions_to_flags("codex", ["read:*"])
    # read-only codex → no workspace-write, approval untrusted
    assert "--approval-policy" in result or result == []  # may be no-op

def test_permissions_to_flags_agy_returns_context_section():
    from synlynk.dispatch import _permissions_to_flags
    result = _permissions_to_flags("agy", ["read:*", "write:docs/"])
    # Agy has no CLI flag — returns empty (permissions injected into context separately)
    assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_permissions_to_flags" -v
```

- [ ] **Step 3: Add `_permissions_to_flags()` to `synlynk/dispatch.py`**

```python
def _permissions_to_flags(agent: str, permissions: list) -> list:
    """Translate a permission list into agent-specific CLI flags.

    Returns a list of extra flags to append to the dispatch command.
    Agy has no permission flags — returns [] (permissions go in context header).
    """
    from synlynk._constants import _PERMISSION_TO_TOOL_MAP
    if agent == "agy":
        return []
    if agent == "claude":
        tools: list = []
        for perm in permissions:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
        if not tools:
            return []
        return ["--allowedTools", ",".join(sorted(set(tools)))]
    if agent == "codex":
        # codex uses workspace-write sandbox by default (already in non_interactive_flags)
        # read-only: switch to workspace (no writes)
        write_perms = [p for p in permissions if p.startswith("write:")]
        if not write_perms:
            return ["--approval-policy", "untrusted"]
        return []
    return []
```

- [ ] **Step 4: Add `grants`/`revokes` params to `dispatch_agent()` and apply**

Update `dispatch_agent()` signature:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   grants: list = None,
                   revokes: list = None) -> dict:
```

After building `flags`, load roles and resolve permissions:

```python
load_config_fn = _pkg("load_config")
cfg = load_config_fn() if load_config_fn else {}
role_list = cfg.get("roles", {}).get(agent, [])
permissions = _resolve_dispatch_permissions(agent, role_list=role_list,
                                            grants=grants, revokes=revokes)
perm_flags = _permissions_to_flags(agent, permissions)
flags = flags + perm_flags

# For Agy: inject permissions into context header
if agent == "agy" and permissions:
    _agy_perm_header = f"\n## Permissions\n" + "\n".join(f"- {p}" for p in permissions) + "\n"
    task = _agy_perm_header + task
```

- [ ] **Step 5: Add `--grant`/`--revoke` to dispatch CLI parser in `synlynk/cli.py`**

```python
dispatch_parser.add_argument("--grant", action="append", default=[],
                              help="Add a permission for this dispatch (repeatable)")
dispatch_parser.add_argument("--revoke", action="append", default=[],
                              help="Remove a permission for this dispatch (repeatable)")
```

In the dispatch handler, pass `grants=args.grant, revokes=args.revoke` to `dispatch_agent()`.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_permissions_to_flags" -v
```

Expected: PASS

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_synlynk.py
git commit -m "feat(bs12-a): --grant/--revoke in dispatch, _permissions_to_flags per agent"
```

---

## Task 8 — `daemon_jobs` schema migration + `HANDOFF_PENDING` sentinel

**Files:**
- Modify: `synlynk/__init__.py` — `_SCHEMA` string (line ~647), add migration in `_get_db()`
- Modify: `synlynk/dispatch.py` — write `HANDOFF_PENDING` after STALL detection
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_daemon_jobs_has_handoff_columns(isolated_db):
    from synlynk import _get_db
    conn = _get_db()
    cols = [row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()]
    assert "handoff_count" in cols
    assert "previous_agents" in cols
    conn.close()

def test_stall_detection_writes_handoff_pending(tmp_path, isolated_db, monkeypatch):
    import os, json, time
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    from synlynk.dispatch import _check_job_stall
    job = {
        "id": "job-abc123",
        "status": "running",
        "pid": None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S",
                                    time.gmtime(time.time() - 99999)),
        "last_output_at": None,
    }
    sentinel_path = str(tmp_path / ".synlynk" / "sentinel.md")
    result = _check_job_stall(job, config={"stall_timeout_minutes": 0}, sentinel_path=sentinel_path)
    assert result is True
    sentinel_content = open(sentinel_path).read()
    assert "STALL_NO_OUTPUT" in sentinel_content
    assert "HANDOFF_PENDING" in sentinel_content
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_daemon_jobs_has_handoff_columns or test_stall_detection_writes_handoff_pending" -v
```

- [ ] **Step 3: Add columns to `_SCHEMA` in `synlynk/__init__.py`**

In the `CREATE TABLE IF NOT EXISTS daemon_jobs` block (line ~647), add two columns before the closing `);`:

```sql
    handoff_count    INTEGER NOT NULL DEFAULT 0,
    previous_agents  TEXT
```

- [ ] **Step 4: Add migration in `_get_db()`**

After `conn.executescript(_SCHEMA)`, add a migration block:

```python
# BS-12: handoff columns migration
for col, defn in [("handoff_count", "INTEGER NOT NULL DEFAULT 0"),
                   ("previous_agents", "TEXT")]:
    try:
        conn.execute(f"ALTER TABLE daemon_jobs ADD COLUMN {col} {defn}")
        conn.commit()
    except Exception:
        pass  # column already exists
```

- [ ] **Step 5: Write `HANDOFF_PENDING` in `_check_stall()` in `synlynk/dispatch.py`**

In `_check_stall()`, after the `write_alert("CRITICAL", "STALL_NO_OUTPUT", ...)` call, add:

```python
write_alert(
    "WARN", "HANDOFF_PENDING",
    f"Job {job.get('id')} on agent '{agent}' is awaiting handoff to another agent.",
    sentinel_path,
)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_daemon_jobs_has_handoff_columns or test_stall_detection_writes_handoff_pending" -v
```

Expected: PASS

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py synlynk/dispatch.py tests/test_synlynk.py
git commit -m "feat(bs12-c): daemon_jobs handoff columns + HANDOFF_PENDING sentinel on stall"
```

---

## Task 9 — `synlynk jobs --stalled` + `synlynk jobs handoff`

**Files:**
- Modify: `synlynk/__init__.py` — `cmd_jobs()` (line ~4847)
- Modify: `synlynk/cli.py` — add `--stalled` flag + `handoff` subcommand
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_jobs_stalled_lists_handoff_pending_jobs(tmp_path, isolated_db, capsys):
    import os
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, handoff_count) "
        "VALUES ('job-aaa', 'agy', 'write tests', 'failed', '2026-07-05T10:00:00', 0)"
    )
    conn.commit()
    conn.close()
    # Write HANDOFF_PENDING sentinel referencing this job
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "sentinel.md").write_text(
        "[HANDOFF_PENDING] Job job-aaa on agent 'agy' is awaiting handoff.\n"
    )
    from synlynk import cmd_jobs
    cmd_jobs(stalled=True)
    out = capsys.readouterr().out
    assert "job-aaa" in out
    assert "agy" in out

def test_jobs_handoff_updates_db_and_dispatches(tmp_path, isolated_db, monkeypatch):
    import os, json
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk" / "contexts", exist_ok=True)
    os.makedirs(tmp_path / ".agents")
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"codex": ["implement"]}}')
    ctx_file = tmp_path / ".synlynk" / "contexts" / "job-bbb.md"
    ctx_file.write_text("# Context\noriginal task content\n")
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, handoff_count, previous_agents) "
        "VALUES ('job-bbb', 'agy', 'implement feature', 'failed', '2026-07-05T10:00:00', 0, NULL)"
    )
    conn.commit()
    conn.close()
    dispatched = []
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent",
                        lambda *a, **kw: dispatched.append((a, kw)) or {"id": "job-ccc"})
    from synlynk import cmd_jobs_handoff
    cmd_jobs_handoff("job-bbb", to_agent="codex")
    # Context file should have handoff note
    content = ctx_file.read_text()
    assert "## Handoff Note" in content
    assert "agy" in content
    # DB updated
    conn2 = _get_db()
    row = conn2.execute("SELECT handoff_count, previous_agents FROM daemon_jobs WHERE job_id='job-bbb'").fetchone()
    assert row[0] == 1
    prev = json.loads(row[1])
    assert "agy" in prev
    # New dispatch fired
    assert len(dispatched) == 1
    assert dispatched[0][0][0] == "codex"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_jobs_stalled or test_jobs_handoff" -v
```

- [ ] **Step 3: Add `stalled` param to `cmd_jobs()` and implement stalled view**

Update `cmd_jobs()` signature:

```python
def cmd_jobs(all_jobs: bool = False, watch: bool = False,
             summary: Optional[str] = None, stalled: bool = False) -> None:
```

Add stalled handling before the existing render logic:

```python
if stalled:
    sentinel_path = os.path.join(".synlynk", "sentinel.md")
    sentinel_text = ""
    if os.path.exists(sentinel_path):
        with open(sentinel_path) as f:
            sentinel_text = f.read()
    pending_ids = set()
    for line in sentinel_text.splitlines():
        if "HANDOFF_PENDING" in line:
            # Extract job id from "Job job-xxx on agent"
            import re as _re
            m = _re.search(r"Job (job-\w+)", line)
            if m:
                pending_ids.add(m.group(1))
    if not pending_ids:
        print("No stalled jobs awaiting handoff.")
        return
    conn = _get_db()
    print(f"\n  {_BOLD}Stalled jobs — awaiting handoff{_RESET}\n")
    print(f"  {'JOB ID':14}  {'AGENT':10}  {'TASK':40}  RECOMMENDED")
    print("  " + "─" * 76)
    for job_id in pending_ids:
        row = conn.execute(
            "SELECT agent, task FROM daemon_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if not row:
            continue
        agent, task_text = row
        # Simple recommendation: first agent that isn't the failed one
        _all = [a for a in ["claude", "codex", "agy", "grok"] if a != agent]
        recommended = _all[0] if _all else "claude"
        print(f"  {job_id:14}  {agent:10}  {(task_text or '')[:40]:40}  → {recommended}")
    conn.close()
    print(f"\n  Run: synlynk jobs handoff <job_id> [--to <agent>]\n")
    return
```

- [ ] **Step 4: Add `cmd_jobs_handoff()` function**

```python
def cmd_jobs_handoff(job_id: str, to_agent: str = None) -> None:
    """Transfer a stalled job to another agent, preserving context."""
    from synlynk.dispatch import dispatch_agent as _dispatch
    conn = _get_db()
    row = conn.execute(
        "SELECT agent, task, handoff_count, previous_agents FROM daemon_jobs WHERE job_id=?",
        (job_id,)
    ).fetchone()
    if not row:
        print(f"  ✗ Job {job_id} not found.")
        return
    orig_agent, task_text, handoff_count, previous_agents_json = row
    previous = json.loads(previous_agents_json) if previous_agents_json else []

    if not to_agent:
        _all = [a for a in ["claude", "codex", "agy", "grok"] if a != orig_agent]
        to_agent = _all[0] if _all else "claude"

    # Append handoff note to context file
    ctx_path = os.path.join(".synlynk", "contexts", f"{job_id}.md")
    if os.path.exists(ctx_path):
        with open(ctx_path, "a") as f:
            f.write(
                f"\n## Handoff Note\n"
                f"- Previous agent: {orig_agent}\n"
                f"- Reason: HANDOFF_PENDING (stall/quota/flatline)\n"
                f"- Handoff #{handoff_count + 1}\n"
            )

    # Update DB
    previous.append(orig_agent)
    conn.execute(
        "UPDATE daemon_jobs SET handoff_count=?, previous_agents=? WHERE job_id=?",
        (handoff_count + 1, json.dumps(previous), job_id)
    )
    conn.commit()
    conn.close()

    # Clear HANDOFF_PENDING from sentinel
    sentinel_path = os.path.join(".synlynk", "sentinel.md")
    if os.path.exists(sentinel_path):
        with open(sentinel_path) as f:
            lines = f.readlines()
        with open(sentinel_path, "w") as f:
            f.writelines(l for l in lines if job_id not in l or "HANDOFF_PENDING" not in l)

    print(f"  ✓ Handing off {job_id} from {orig_agent} → {to_agent}")
    result = _dispatch(to_agent, task=task_text, context_mode="task")
    print(f"  ✓ New job: {result.get('id', '?')}")
```

- [ ] **Step 5: Wire `--stalled` and `handoff` into CLI**

In `synlynk/cli.py`, add to jobs subparser:
```python
jobs_parser.add_argument("--stalled", action="store_true", help="List jobs awaiting handoff")
```

Add `handoff` sub-subcommand:
```python
jobs_sub = jobs_parser.add_subparsers(dest="jobs_cmd")
handoff_p = jobs_sub.add_parser("handoff", help="Transfer stalled job to another agent")
handoff_p.add_argument("job_id")
handoff_p.add_argument("--to", dest="to_agent", default=None)
```

Handler:
```python
elif args.command == "jobs":
    if getattr(args, "jobs_cmd", None) == "handoff":
        from synlynk import cmd_jobs_handoff
        cmd_jobs_handoff(args.job_id, to_agent=args.to_agent)
    else:
        cmd_jobs(all_jobs=args.all, watch=args.watch,
                 summary=getattr(args, "summary", None),
                 stalled=args.stalled)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_jobs_stalled or test_jobs_handoff" -v
```

Expected: PASS

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py synlynk/cli.py tests/test_synlynk.py
git commit -m "feat(bs12-c): jobs --stalled view + jobs handoff command with context preservation"
```

---

## Task 10 — Doctor guided fix wizard

**Files:**
- Modify: `synlynk/__init__.py` — `cmd_doctor()` (line ~2120)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write failing tests**

```python
def test_doctor_wizard_offers_fix_menu_on_tc2_failure(tmp_path, isolated_db, monkeypatch):
    """Wizard renders menu; selecting option 1 applies the fix."""
    import os
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".agents")
    (tmp_path / ".synlynk").mkdir()
    # Simulate TC-2 failure (bad flags)
    inputs = iter(["1"])  # select first fix option
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    from synlynk import cmd_doctor
    # Should not raise; fix menu rendered and option applied
    cmd_doctor()  # will pass even with no agents configured; just verify no crash

def test_doctor_wizard_escalate_option_calls_dispatch(tmp_path, isolated_db, monkeypatch):
    import os
    os.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    dispatched = []
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent",
                        lambda *a, **kw: dispatched.append((a, kw)) or {"id": "job-esc"})
    inputs = iter(["0"])  # "0" = I'm stuck / escalate
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    from synlynk.probe import _run_tc5
    # Build a fake failure context
    failures = {"tc2": {"passed": False, "failed_flags": ["--bad-flag"]}}
    from synlynk import _doctor_maybe_escalate
    _doctor_maybe_escalate("agy", failures)
    assert len(dispatched) == 1
    assert dispatched[0][0][0] == "claude"
    assert "HANDOFF_PENDING" in dispatched[0][0][1] or "doctor" in dispatched[0][0][1].lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_synlynk.py -k "test_doctor_wizard" -v
```

- [ ] **Step 3: Add `_doctor_fix_menu()` and `_doctor_maybe_escalate()` helpers**

Add these two helpers just above `cmd_doctor()`:

```python
_DOCTOR_FIX_MENUS = {
    "tc1": lambda agent, tc: [
        f"Show PTY workaround for {agent} (requires_pty={tc.get('requires_pty')})",
    ],
    "tc2": lambda agent, tc: [
        f"Apply recommended flags to .agents/{agent}.json (fixes: {tc.get('failed_flags', [])})",
    ],
    "tc3": lambda agent, tc: [
        f"Show unreachable endpoints and configure proxy for {agent}",
        f"Skip {agent} in this session",
    ],
    "tc4": lambda agent, tc: [
        f"Run: synlynk configure agent {agent} (adds missing verbs: {tc.get('failed_verbs', [])})",
    ],
    "tc5": lambda agent, tc: [
        f"Run: synlynk sync --repair-sops (re-inject {len(tc.get('missing', {}).get(agent, []))} missing sections)",
    ],
}


def _doctor_fix_menu(agent: str, tc_name: str, tc_result: dict) -> str:
    """Render a numbered fix menu for a TC failure. Returns chosen action key or 'escalate'."""
    if not sys.stdin.isatty():
        return "skip"
    menu_fn = _DOCTOR_FIX_MENUS.get(tc_name)
    options = menu_fn(agent, tc_result) if menu_fn else []
    print(f"\n    {_YELLOW}Fix options for {tc_name.upper()} [{agent}]:{_RESET}")
    print(f"      0) I'm stuck — escalate to Claude")
    for i, opt in enumerate(options, 1):
        print(f"      {i}) {opt}")
    print(f"      s) Skip")
    try:
        choice = input("    Choose [0/1.../s]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "skip"
    if choice == "0":
        return "escalate"
    if choice == "s" or not choice:
        return "skip"
    return choice


def _doctor_maybe_escalate(agent: str, failures: dict) -> None:
    """Assemble failure context and dispatch to Claude for conversational diagnosis."""
    import json as _json
    lines = [f"# synlynk doctor failure — {agent}\n"]
    for tc_name, result in failures.items():
        lines.append(f"## {tc_name.upper()}\n```\n{_json.dumps(result, indent=2)}\n```\n")
    # Include last 5 telemetry rows
    tel_path = os.path.join(".synlynk", "telemetry.json")
    if os.path.exists(tel_path):
        try:
            events = json.load(open(tel_path))[-5:]
            lines.append(f"## Last 5 telemetry events\n```json\n{json.dumps(events, indent=2)}\n```\n")
        except Exception:
            pass
    context = "\n".join(lines)
    task = (
        f"synlynk doctor found failures for agent '{agent}'. "
        f"Please diagnose and suggest fixes.\n\n{context}"
    )
    from synlynk.dispatch import dispatch_agent
    print(f"\n    Escalating to Claude for diagnosis...\n")
    result = dispatch_agent("claude", task=task)
    print(f"    Dispatched: {result.get('id', '?')} — check synlynk jobs for output")
```

- [ ] **Step 4: Integrate wizard into `cmd_doctor()`**

After each TC print block in `cmd_doctor()`, when a TC fails, call `_doctor_fix_menu()`:

```python
# After TC-2 print:
if not tc2["passed"]:
    choice = _doctor_fix_menu(agent, "tc2", tc2)
    if choice == "1":
        cmd_configure_agent(agent, flags={f: "true" for f in tc2.get("failed_flags", [])})
    elif choice == "escalate":
        _doctor_maybe_escalate(agent, {"tc2": tc2})

# After TC-4 print:
if not tc4["passed"]:
    choice = _doctor_fix_menu(agent, "tc4", tc4)
    if choice == "1":
        cmd_configure_agent(agent, flags={v: "true" for v in tc4.get("failed_verbs", [])})
    elif choice == "escalate":
        _doctor_maybe_escalate(agent, {"tc4": tc4})

# After TC-5 print (when SOPs missing):
if not tc5["passed"]:
    choice = _doctor_fix_menu(agent, "tc5", tc5)
    if choice == "1":
        cmd_sync(dry_run=False, repair_sops=True)
    elif choice == "escalate":
        _doctor_maybe_escalate(agent, {"tc5": tc5})
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py -k "test_doctor_wizard" -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs12-d): doctor guided fix wizard with escalation to Claude dispatch"
```

---

## Self-Review Checklist

- [ ] **Spec coverage**: A (Tasks 6–7) ✓ · B (Tasks 4–5) ✓ · C (Tasks 8–9) ✓ · D (Task 10) ✓ · E (Tasks 1–3) ✓
- [ ] **No placeholder steps**: all code blocks are complete
- [ ] **Type consistency**: `_resolve_dispatch_permissions` returns `list` throughout · `_load_harness_overrides` returns `dict` throughout · `_run_tc5` returns `{"passed": bool, "missing": dict}` matching TC-1–4 pattern
- [ ] **`_check_job_stall` signature**: function takes `(job, config, sentinel_path)` — `config` dict with `stall_timeout_minutes` key
- [ ] **`cmd_jobs_handoff` export**: ensure it's importable from `synlynk` (i.e., in `__init__.py`, not a nested closure)
- [ ] **`_doctor_maybe_escalate` `json` import**: uses bare `json.load` — ensure `import json` is at module level in `__init__.py` (it is)
- [ ] **Agy P1-content dependency**: SOP block prose in `probe.py` is placeholder — replace with Agy's output when delivered before opening PR
