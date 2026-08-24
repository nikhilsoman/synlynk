# PM Competitive-Intelligence Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `synlynk pm sweep` command that composes a competitive-research prompt from a config file, hands it to a headless Claude session with web/gh tool access, and reports a cost/ticket summary — wired to a new weekly GH Actions cron and a revised PM charter.

**Architecture:** A new `synlynk/pm_agent.py` module owns prompt composition and the headless-invocation wrapper; `synlynk/cli.py` gets a new `pm sweep [--dry-run]` subcommand mirroring the existing `tpm sweep` subparser pattern. A new `docs/strategy/competitive-config.yaml` holds segments/competitors/panel/labels; a new `docs/strategy/competitive-landscape.md` is the living doc the headless session edits. A new `.github/workflows/pm-competitive-sweep.yml` triggers it weekly, mirroring `support-engineer.yml`'s shape.

**Tech Stack:** Python (stdlib `subprocess`, `json`, `yaml` — confirm PyYAML is already a dependency before Task 1), pytest with `unittest.mock.patch`, existing `synlynk.agent_store` charter API, existing `synlynk.team.HARNESS_CAPABILITY_BASELINES`.

---

## File Structure

- **Create:** `synlynk/pm_agent.py` — prompt composition (`_load_config`, `_compose_prompt`, `_resolve_decide_panel`), headless invocation wrapper (`_invoke_headless_claude`), and the top-level `cmd_pm_sweep(dry_run: bool = False) -> dict` entry point.
- **Modify:** `synlynk/cli.py` — new `pm` subparser (mirrors `tpm_parser` at line ~812) and dispatch branch (mirrors the `tpm sweep` dispatch at line ~1361).
- **Create:** `docs/strategy/competitive-config.yaml` — seed config.
- **Create:** `docs/strategy/competitive-landscape.md` — seed living doc, migrated from `docs/proposals/competitor-comparison-analysis.md`.
- **Modify:** `synlynk/agent_cli.py` — revise `SEED_CHARTERS["pm"]` (line 14).
- **Create:** `.github/workflows/pm-competitive-sweep.yml` — weekly cron workflow.
- **Test:** `tests/test_pm_agent.py` — new test file for `pm_agent.py`.
- **Test:** `tests/test_cli_pm.py` — new test file for the `pm sweep` CLI wiring.

---

### Task 1: `pm_agent.py` — config loading and prompt composition

**Files:**
- Create: `synlynk/pm_agent.py`
- Test: `tests/test_pm_agent.py`

- [ ] **Step 1: Write the failing test for `_load_config`**

```python
# tests/test_pm_agent.py
import os
import textwrap

from synlynk.pm_agent import _load_config


def test_load_config_reads_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.yaml", "w") as f:
        f.write(textwrap.dedent("""\
            segments:
              - name: "solo indie devs"
                competitors: ["Superpowers", "GStack"]
            decide_panel: auto
            research_issue_labels: ["competitive-research", "architect"]
            proposal_issue_labels: ["feature-proposal", "needs-user-review"]
        """))
    config = _load_config()
    assert config["segments"][0]["name"] == "solo indie devs"
    assert config["segments"][0]["competitors"] == ["Superpowers", "GStack"]
    assert config["decide_panel"] == "auto"
    assert config["research_issue_labels"] == ["competitive-research", "architect"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pm_agent.py::test_load_config_reads_yaml -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.pm_agent'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/pm_agent.py
"""PM competitive-intelligence sweep: config loading, prompt composition,
and the headless-Claude invocation wrapper for `synlynk pm sweep`.

See docs/superpowers/specs/2026-08-24-pm-competitive-intelligence-sweep-design.md.
"""
import json
import subprocess

import yaml

from synlynk.team import HARNESS_CAPABILITY_BASELINES

CONFIG_PATH = "docs/strategy/competitive-config.yaml"
DOC_PATH = "docs/strategy/competitive-landscape.md"


def _load_config(config_path: str = CONFIG_PATH) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pm_agent.py::test_load_config_reads_yaml -v`
Expected: PASS

- [ ] **Step 5: Confirm PyYAML is available**

Run: `python3 -c "import yaml; print(yaml.__version__)"`
Expected: prints a version (PyYAML is already a transitive dependency of this repo's tooling; if this fails, add `PyYAML` to `pyproject.toml`'s dependencies before continuing).

- [ ] **Step 6: Write the failing test for `_resolve_decide_panel`**

```python
# tests/test_pm_agent.py (append)
from synlynk.pm_agent import _resolve_decide_panel


def test_resolve_decide_panel_auto_returns_all_known_harnesses():
    panel = _resolve_decide_panel("auto")
    assert panel == sorted(HARNESS_CAPABILITY_BASELINES.keys())


def test_resolve_decide_panel_explicit_list():
    panel = _resolve_decide_panel("claude,codex")
    assert panel == ["claude", "codex"]
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_pm_agent.py::test_resolve_decide_panel_auto_returns_all_known_harnesses -v`
Expected: FAIL with `ImportError: cannot import name '_resolve_decide_panel'`

- [ ] **Step 8: Implement `_resolve_decide_panel`**

```python
# synlynk/pm_agent.py (append)
def _resolve_decide_panel(decide_panel_config: str) -> list:
    if decide_panel_config == "auto":
        return sorted(HARNESS_CAPABILITY_BASELINES.keys())
    return [name.strip() for name in decide_panel_config.split(",") if name.strip()]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_pm_agent.py -v`
Expected: 3 passed

- [ ] **Step 10: Write the failing test for `_compose_prompt`**

```python
# tests/test_pm_agent.py (append)
from synlynk.pm_agent import _compose_prompt


def test_compose_prompt_includes_segments_competitors_panel_labels():
    config = {
        "segments": [
            {"name": "solo indie devs", "competitors": ["Superpowers", "GStack"]},
        ],
        "decide_panel": "claude,codex",
        "research_issue_labels": ["competitive-research", "architect"],
        "proposal_issue_labels": ["feature-proposal", "needs-user-review"],
    }
    prompt = _compose_prompt(config)
    assert "solo indie devs" in prompt
    assert "Superpowers" in prompt
    assert "GStack" in prompt
    assert "claude" in prompt and "codex" in prompt
    assert "competitive-research" in prompt
    assert "feature-proposal" in prompt
    assert "docs/strategy/competitive-landscape.md" in prompt
```

- [ ] **Step 11: Run test to verify it fails**

Run: `pytest tests/test_pm_agent.py::test_compose_prompt_includes_segments_competitors_panel_labels -v`
Expected: FAIL with `ImportError: cannot import name '_compose_prompt'`

- [ ] **Step 12: Implement `_compose_prompt`**

```python
# synlynk/pm_agent.py (append)
def _compose_prompt(config: dict) -> str:
    panel = _resolve_decide_panel(config["decide_panel"])
    segment_lines = []
    for segment in config["segments"]:
        competitors = ", ".join(segment["competitors"]) or "(none known yet)"
        segment_lines.append(f"- {segment['name']}: {competitors}")
    segments_block = "\n".join(segment_lines)
    research_labels = ",".join(config["research_issue_labels"])
    proposal_labels = ",".join(config["proposal_issue_labels"])

    return (
        "You are running synlynk's weekly PM competitive-intelligence sweep.\n\n"
        "User segments and known competitors:\n"
        f"{segments_block}\n\n"
        "For each segment:\n"
        "1. Research the web for products/companies serving this segment that "
        "you don't already know about, and re-check known competitors for "
        "capability or positioning changes.\n"
        f"2. Update {DOC_PATH} in place: refresh existing rows, add new "
        "segments/competitors as new sections (never remove existing entries), "
        "bump the 'Last swept' date.\n"
        "3. For each genuine capability or marketing gap candidate you find, "
        f"open a GitHub research issue (`gh issue create --label {research_labels}`) "
        "describing what the competitor does, why it's a gap, and linking to the "
        f"relevant row in {DOC_PATH}.\n"
        "4. For each research candidate, run: "
        '`synlynk decide "<candidate>: should synlynk build this? Answer from '
        "your own harness-maintainer POV — implementation cost, maintenance "
        f'burden, fit with your role\'s workflow." --panel {",".join(panel)} --record`\n'
        "5. Judge fit against synlynk's stated vision and goals using the decide "
        "round's opinions plus your own research. For candidates you judge a "
        "strong fit, open a second issue titled `[Proposal] <candidate>` "
        f"(`gh issue create --label {proposal_labels}`), summarizing the research "
        "ticket, the decide-round opinions, and why it's a strong fit.\n\n"
        "Do not open a proposal issue for every research candidate — only ones "
        "with a strong fit. When finished, print a one-line JSON summary to "
        "stdout: "
        '{"research_tickets": <int>, "proposals": <int>, "segments_updated": <int>}.'
    )
```

- [ ] **Step 13: Run tests to verify they pass**

Run: `pytest tests/test_pm_agent.py -v`
Expected: 5 passed

- [ ] **Step 14: Commit**

```bash
git add synlynk/pm_agent.py tests/test_pm_agent.py
git commit -m "feat(pm_agent): config loading and prompt composition for competitive sweep"
```

---

### Task 2: `pm_agent.py` — headless invocation wrapper and `cmd_pm_sweep`

**Files:**
- Modify: `synlynk/pm_agent.py`
- Test: `tests/test_pm_agent.py`

- [ ] **Step 1: Write the failing test for `_invoke_headless_claude`**

```python
# tests/test_pm_agent.py (append)
from unittest.mock import MagicMock, patch

from synlynk.pm_agent import _invoke_headless_claude


def test_invoke_headless_claude_builds_expected_command():
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"result": "ok"}', stderr=""
        )
        result = _invoke_headless_claude("do the sweep")
    args = mock_run.call_args[0][0]
    assert args[0] == "claude"
    assert "-p" in args
    assert "do the sweep" in args
    assert "--allowedTools" in args
    tools_idx = args.index("--allowedTools") + 1
    assert set(args[tools_idx].split(",")) == {"WebSearch", "WebFetch", "Bash"}
    assert "--output-format" in args
    assert "json" in args
    assert result["returncode"] == 0
    assert result["stdout"] == '{"result": "ok"}'


def test_invoke_headless_claude_nonzero_exit_reported():
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        result = _invoke_headless_claude("do the sweep")
    assert result["returncode"] == 1
    assert result["stderr"] == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pm_agent.py::test_invoke_headless_claude_builds_expected_command -v`
Expected: FAIL with `ImportError: cannot import name '_invoke_headless_claude'`

- [ ] **Step 3: Implement `_invoke_headless_claude`**

```python
# synlynk/pm_agent.py (append)
def _invoke_headless_claude(prompt: str) -> dict:
    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", "WebSearch,WebFetch,Bash",
        "--output-format", "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pm_agent.py -v`
Expected: 7 passed

- [ ] **Step 5: Write the failing test for `cmd_pm_sweep` dry-run**

```python
# tests/test_pm_agent.py (append)
import os
import textwrap

from synlynk.pm_agent import cmd_pm_sweep


def _write_seed_config():
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.yaml", "w") as f:
        f.write(textwrap.dedent("""\
            segments:
              - name: "solo indie devs"
                competitors: ["Superpowers"]
            decide_panel: "claude,codex"
            research_issue_labels: ["competitive-research"]
            proposal_issue_labels: ["feature-proposal"]
        """))


def test_cmd_pm_sweep_dry_run_does_not_invoke_subprocess(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        summary = cmd_pm_sweep(dry_run=True)
    mock_run.assert_not_called()
    captured = capsys.readouterr()
    assert "solo indie devs" in captured.out
    assert summary is None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_pm_agent.py::test_cmd_pm_sweep_dry_run_does_not_invoke_subprocess -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_pm_sweep'`

- [ ] **Step 7: Write the failing test for `cmd_pm_sweep` real run**

```python
# tests/test_pm_agent.py (append)
def test_cmd_pm_sweep_real_run_parses_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    fake_stdout = (
        '{"result": "'
        '{\\"research_tickets\\": 2, \\"proposals\\": 1, \\"segments_updated\\": 1}"}'
    )
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_stdout, stderr="")
        summary = cmd_pm_sweep(dry_run=False)
    assert summary["research_tickets"] == 2
    assert summary["proposals"] == 1
    captured = capsys.readouterr()
    assert "research_tickets" in captured.out


def test_cmd_pm_sweep_real_run_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_seed_config()
    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="network error")
        with pytest.raises(SystemExit):
            cmd_pm_sweep(dry_run=False)
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `pytest tests/test_pm_agent.py::test_cmd_pm_sweep_real_run_parses_summary tests/test_pm_agent.py::test_cmd_pm_sweep_real_run_failure_exits_nonzero -v`
Expected: FAIL (missing `cmd_pm_sweep`, missing `import pytest` in test file)

- [ ] **Step 9: Add `import pytest` to the top of `tests/test_pm_agent.py`**

```python
# tests/test_pm_agent.py (top of file)
import pytest
```

- [ ] **Step 10: Implement `cmd_pm_sweep`**

```python
# synlynk/pm_agent.py (append)
import sys


def cmd_pm_sweep(dry_run: bool = False):
    config = _load_config()
    prompt = _compose_prompt(config)

    if dry_run:
        print(prompt)
        return None

    result = _invoke_headless_claude(prompt)
    if result["returncode"] != 0:
        print(
            f"pm sweep failed (exit {result['returncode']}): {result['stderr']}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        outer = json.loads(result["stdout"])
        summary = json.loads(outer["result"])
    except (json.JSONDecodeError, KeyError, TypeError):
        print("pm sweep: could not parse summary JSON from output", file=sys.stderr)
        summary = {"research_tickets": 0, "proposals": 0, "segments_updated": 0}

    print(
        f"pm sweep: {summary.get('research_tickets', 0)} research_tickets, "
        f"{summary.get('proposals', 0)} proposals, "
        f"{summary.get('segments_updated', 0)} segments_updated"
    )
    return summary
```

- [ ] **Step 11: Run all pm_agent tests to verify they pass**

Run: `pytest tests/test_pm_agent.py -v`
Expected: 11 passed

- [ ] **Step 12: Commit**

```bash
git add synlynk/pm_agent.py tests/test_pm_agent.py
git commit -m "feat(pm_agent): headless invocation wrapper and cmd_pm_sweep entry point"
```

---

### Task 3: Wire `pm sweep` into `synlynk/cli.py`

**Files:**
- Modify: `synlynk/cli.py:812` (add `pm_parser` next to `tpm_parser`)
- Modify: `synlynk/cli.py:1361` (add dispatch branch next to `tpm sweep` dispatch)
- Test: `tests/test_cli_pm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_pm.py
import subprocess
import sys


def test_pm_sweep_dry_run_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    import textwrap
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.yaml", "w") as f:
        f.write(textwrap.dedent("""\
            segments:
              - name: "solo indie devs"
                competitors: []
            decide_panel: "claude"
            research_issue_labels: ["competitive-research"]
            proposal_issue_labels: ["feature-proposal"]
        """))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "bin", "synlynk.py"), "pm", "sweep", "--dry-run"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "solo indie devs" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_pm.py -v`
Expected: FAIL — `pm` is not a recognized command (argparse error, non-zero exit)

- [ ] **Step 3: Add the `pm` subparser**

In `synlynk/cli.py`, immediately before the existing `tpm_parser = subparsers.add_parser("tpm", ...)` line (~812), add:

```python
    pm_parser = subparsers.add_parser("pm", help="PM agent commands")
    pm_subparsers = pm_parser.add_subparsers(dest="pm_command")
    pm_sweep_parser = pm_subparsers.add_parser(
        "sweep", help="Run one competitive-intelligence sweep pass"
    )
    pm_sweep_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the composed research prompt without invoking Claude"
    )
```

- [ ] **Step 4: Add the dispatch branch**

In `synlynk/cli.py`, immediately before the existing `elif args.command == "tpm" and args.tpm_command == "sweep":` line (~1361), add:

```python
    elif args.command == "pm" and args.pm_command == "sweep":
        from synlynk.pm_agent import cmd_pm_sweep

        cmd_pm_sweep(dry_run=args.dry_run)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_pm.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_pm.py
git commit -m "feat(cli): wire synlynk pm sweep subcommand"
```

---

### Task 4: Seed config and living comparison doc

**Files:**
- Create: `docs/strategy/competitive-config.yaml`
- Create: `docs/strategy/competitive-landscape.md`
- Modify: `docs/proposals/competitor-comparison-analysis.md` (archive)

- [ ] **Step 1: Read the existing stale comparison doc**

Run: `cat docs/proposals/competitor-comparison-analysis.md`

Use its competitor list and comparison table content as the source for the seed files below — do not invent competitor names not already present in that doc.

- [ ] **Step 2: Create the seed config**

```yaml
# docs/strategy/competitive-config.yaml
segments:
  - name: "solo indie devs building with AI agents"
    competitors: ["Superpowers", "GStack"]
decide_panel: auto
research_issue_labels: ["competitive-research", "architect"]
proposal_issue_labels: ["feature-proposal", "needs-user-review"]
```

- [ ] **Step 3: Create the seed living doc**

Migrate the existing "Architectural & Feature Comparison" table from `docs/proposals/competitor-comparison-analysis.md` into the new matrix format:

```markdown
# Competitive Landscape

_Last swept: 2026-08-24 (seed — migrated from docs/proposals/competitor-comparison-analysis.md)_

## Segment: solo indie devs building with AI agents
Competitors: Superpowers, GStack

### Capability Gaps
| Capability | synlynk | Superpowers | GStack | Gap? |
|---|---|---|---|---|
| State & Memory | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
| Tool/CLI Lock-in | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
| Multi-Agent Coordination | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
| Safety & Loop Control | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
| Cost & Budget Auditing | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |

### Marketing Gaps
| Positioning vector | synlynk | Superpowers | GStack | Gap? |
|---|---|---|---|---|
| Core Value Proposition | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
| UI Ergonomics | (fill from source doc) | (fill from source doc) | (fill from source doc) | (fill from source doc) |
```

Replace every `(fill from source doc)` cell with the corresponding content read from `docs/proposals/competitor-comparison-analysis.md` in Step 1 — this file must not be committed with literal placeholder text.

- [ ] **Step 4: Archive the stale source doc**

```bash
mkdir -p docs/archive
git mv docs/proposals/competitor-comparison-analysis.md docs/archive/competitor-comparison-analysis.md
```

Add a one-line note at the top of the archived file: `> Superseded by docs/strategy/competitive-landscape.md (2026-08-24) — content migrated, this file kept for history.`

- [ ] **Step 5: Verify the seed config loads via `_load_config`**

Run: `python3 -c "from synlynk.pm_agent import _load_config; import os; os.chdir('.'); print(_load_config())"`
Expected: prints the parsed dict with the "solo indie devs building with AI agents" segment

- [ ] **Step 6: Commit**

```bash
git add docs/strategy/competitive-config.yaml docs/strategy/competitive-landscape.md docs/archive/competitor-comparison-analysis.md
git rm docs/proposals/competitor-comparison-analysis.md 2>/dev/null || true
git commit -m "docs(strategy): seed competitive-intelligence config and living comparison doc"
```

---

### Task 5: GH Actions weekly cron workflow

**Files:**
- Create: `.github/workflows/pm-competitive-sweep.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: PM Competitive Sweep

on:
  schedule:
    - cron: '0 13 * * 1'
  workflow_dispatch: {}

jobs:
  pm-competitive-sweep:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install PyYAML
        run: pip install pyyaml

      - name: Install Claude CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Run PM competitive sweep
        run: python3 bin/synlynk.py pm sweep
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

- [ ] **Step 2: Validate the YAML is well-formed**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pm-competitive-sweep.yml'))"`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pm-competitive-sweep.yml
git commit -m "ci: add weekly PM competitive-intelligence sweep workflow"
```

---

### Task 6: PM charter revision

**Files:**
- Modify: `synlynk/agent_cli.py:14`
- Test: `tests/test_agent_cli.py`

- [ ] **Step 1: Read the existing charter test coverage**

Run: `grep -n "SEED_CHARTERS\[.pm.\]\|SEED_CHARTERS\[\"pm\"\]" tests/test_agent_cli.py`

If no existing test asserts on the literal `pm` charter string, proceed to Step 2 without modifying an existing test. If one exists and hardcodes the old string, note it — Step 4 updates it.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_agent_cli.py (append)
from synlynk.agent_cli import SEED_CHARTERS


def test_pm_charter_includes_competitive_sweep_responsibility():
    assert "competitive-intelligence sweep" in SEED_CHARTERS["pm"]
    assert "capability/marketing-gap comparison doc" in SEED_CHARTERS["pm"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_agent_cli.py::test_pm_charter_includes_competitive_sweep_responsibility -v`
Expected: FAIL — assertion error, charter string doesn't yet contain the phrase

- [ ] **Step 4: Update `SEED_CHARTERS["pm"]`**

In `synlynk/agent_cli.py` line 14, replace:

```python
    "pm": "Program management — roadmap, brainstorming, issue triage.",
```

with:

```python
    "pm": (
        "Program management — roadmap, brainstorming, issue triage. "
        "Runs a weekly competitive-intelligence sweep: tracks products serving "
        "synlynk's user segments, maintains a living capability/marketing-gap "
        "comparison doc, opens research tickets for candidate features, "
        "convenes harness-maintainer decide rounds, and escalates strong-fit "
        "candidates to the user as feature proposals."
    ),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_agent_cli.py::test_pm_charter_includes_competitive_sweep_responsibility -v`
Expected: PASS

- [ ] **Step 6: Run the full `test_agent_cli.py` suite to check for regressions**

Run: `pytest tests/test_agent_cli.py -v`
Expected: all pass — if any test hardcoded the old charter string, fix that assertion to match the new string rather than reverting the charter text

- [ ] **Step 7: Commit**

```bash
git add synlynk/agent_cli.py tests/test_agent_cli.py
git commit -m "feat(agent_cli): revise PM charter to include competitive-intelligence sweep"
```

---

### Task 7: Full-suite verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -x -q`
Expected: all tests pass, 0 failures

- [ ] **Step 2: Confirm no stray debug output or committed placeholder text**

Run: `grep -rn "fill from source doc\|TBD\|TODO" docs/strategy/ .github/workflows/pm-competitive-sweep.yml synlynk/pm_agent.py`
Expected: no matches (Task 4 must have replaced every placeholder cell)

- [ ] **Step 3: If Step 2 finds matches, go back to Task 4 Step 3 and fill them from the archived source doc before proceeding**

---

## Deviation from Spec

The spec's "Error Handling" section states that `gh issue create` calls should go through the existing `gh_write_verified` delivery-verification path. This plan does not wire that in: `gh_write_verified` is built into the `dispatch_agent`/daemon-job reconciliation loop (`synlynk/dispatch.py`, `synlynk/jobs.py`), and this sweep's ticket creation happens inside a single headless `claude -p` session's own `gh` calls (via `--allowedTools Bash`), not through `dispatch_agent`. There is no daemon job here to attach verification to. This mirrors `.github/workflows/support-engineer.yml`'s own precedent, which also issues `gh` commands directly without `gh_write_verified`. If stronger delivery guarantees are wanted later, that would require routing ticket creation through `dispatch_agent` instead — out of scope for this plan.

## Notes for the Implementer

- All Python/CLI tasks (1–3, 6) should be dispatched to Codex via:
  `python3 bin/synlynk.py dispatch codex --task "<task description + full task text from this plan>" --force-agent --context-mode full`
  run from this worktree's root — per this repo's role-split policy (Claude = PM/review/deploy; Codex = implement/test/refactor/cli-plumbing).
- Tasks 4 (docs) and 5 (CI YAML) are lightweight content/config tasks that may also be dispatched to Codex for consistency, or handled directly if trivial — use judgment, but per standing policy default to dispatch rather than direct edits.
- Task 7 (full-suite verification) and the eventual PR/merge are Claude's own PM/review/deploy work — do not dispatch these.
