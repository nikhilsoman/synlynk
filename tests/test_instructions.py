import json
import stat
import subprocess
from pathlib import Path

import pytest


def test_install_pre_commit_hook_writes_executable_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)

    from synlynk.instructions import install_pre_commit_hook

    install_pre_commit_hook(repo_root=tmp_path)

    hook_path = hook_dir / "pre-commit"
    assert hook_path.exists()
    assert hook_path.stat().st_mode & stat.S_IXUSR
    assert "-m synlynk instructions status --pre-commit" in hook_path.read_text()


def test_install_pre_commit_hook_appends_to_existing_shebang_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)
    hook_path = hook_dir / "pre-commit"
    hook_path.write_text("#!/bin/sh\nexit 0\n")

    from synlynk.instructions import install_pre_commit_hook

    install_pre_commit_hook(repo_root=tmp_path)

    text = hook_path.read_text()
    assert text.startswith("#!/bin/sh")
    assert "exit 0" in text
    assert text.count("-m synlynk instructions status --pre-commit") == 1
    assert hook_path.stat().st_mode & stat.S_IXUSR


def test_install_pre_commit_hook_rejects_non_shebang_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)
    hook_path = hook_dir / "pre-commit"
    hook_path.write_text("echo nope\n")

    from synlynk.instructions import install_pre_commit_hook

    with pytest.raises(RuntimeError, match="unexpected pre-commit hook content"):
        install_pre_commit_hook(repo_root=tmp_path)


def test_versioned_hook_blocks_feature_branch_in_main_worktree(tmp_path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"],
                   cwd=tmp_path, check=True)
    (tmp_path / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path,
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "switch", "-c", "feature/test"], cwd=tmp_path,
                   check=True, capture_output=True, text=True)

    hook = Path(__file__).parents[1] / "githooks" / "pre-commit"
    result = subprocess.run([str(hook)], cwd=tmp_path, capture_output=True,
                            text=True)

    assert result.returncode != 0
    assert "shared main worktree" in result.stderr
    assert "git worktree add worktrees/<name> -b <branch>" in result.stderr
    assert "CLAUDE.md" in result.stderr


def test_init_configures_versioned_hooks_path(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True,
                   capture_output=True, text=True)
    from synlynk.instructions import install_pre_commit_hook

    install_pre_commit_hook(repo_root=tmp_path)

    configured = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    assert configured.stdout.strip() == "githooks"


def test_tier0_fixture_only_gets_tier0_and_gateway_phrases():
    from synlynk.instructions import render_trigger_phrase_section

    section = render_trigger_phrase_section(current_tier=0)
    assert "let's build X" not in section
    assert "set up synlynk here" in section
    assert "where are we" in section


def test_tier2_fixture_gets_tier0_through_tier2_phrases():
    from synlynk.instructions import render_trigger_phrase_section

    section = render_trigger_phrase_section(current_tier=2)
    assert "let's build X" in section
    assert "set up synlynk here" in section
    assert "rate this agent's output" not in section


def test_render_lifecycle_checkpoint_section_returns_fixed_block():
    from synlynk.instructions import render_lifecycle_checkpoint_section

    section = render_lifecycle_checkpoint_section()
    assert section == (
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


def test_instructions_status_pre_commit_exits_on_drift(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)

    instruction_text = (
        "# Title\n"
        "<!-- synlynk:start version=\"0.4.1\" tool=\"claude\" -->\n"
        "old instruction text\n"
        "<!-- synlynk:end -->\n"
    )
    (tmp_path / "CLAUDE.md").write_text(instruction_text)

    from synlynk.instructions import (
        _compute_section_sha,
        _extract_synlynk_section,
        _write_instruction_manifest,
        cmd_instructions_status,
    )

    section = _extract_synlynk_section(instruction_text, "html")
    _write_instruction_manifest(
        {"CLAUDE.md": {"tool": "claude", "sha": "0" * 16}}
    )
    assert _compute_section_sha(section) != "0" * 16

    with pytest.raises(SystemExit) as exc:
        cmd_instructions_status(pre_commit=True)

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "Instruction drift detected. Commit blocked." in output
    assert "synlynk instructions diff CLAUDE.md" in output
    assert "synlynk instructions update CLAUDE.md" in output
    assert "synlynk instructions ack CLAUDE.md" in output


def test_register_backfills_existing_fenced_file_without_rewriting_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    instruction = tmp_path / "CLAUDE.md"
    original = (
        "# Project instructions\n"
        "Keep this content exactly as written.\n"
        "<!-- synlynk:start version=\"0.4.1\" tool=\"claude\" -->\n"
        "existing synlynk instructions\n"
        "<!-- synlynk:end -->\n"
    )
    instruction.write_text(original)

    from synlynk.instructions import (
        _compute_section_sha,
        _extract_synlynk_section,
        cmd_instructions_register,
    )

    cmd_instructions_register("CLAUDE.md")
    assert instruction.read_text() == original
    manifest = json.loads((tmp_path / ".synlynk" / "instructions.json").read_text())
    assert manifest["files"]["CLAUDE.md"] == {
        "tool": "claude",
        "sha": _compute_section_sha(_extract_synlynk_section(original)),
        "last_checked": manifest["files"]["CLAUDE.md"]["last_checked"],
    }


def test_register_is_idempotent_and_scans_known_fenced_targets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "GEMINI.md").write_text(
        '<!-- synlynk:start version="0.4.1" tool="agy" -->\n'
        "agy instructions\n<!-- synlynk:end -->\n"
    )
    (tmp_path / ".windsurfrules").write_text(
        '# synlynk:start version="0.4.1"\n'
        "windsurf instructions\n# synlynk:end\n"
    )

    from synlynk.instructions import cmd_instructions_register

    cmd_instructions_register()
    first_manifest = (tmp_path / ".synlynk" / "instructions.json").read_text()
    first_gemini = (tmp_path / "GEMINI.md").read_text()
    first_windsurf = (tmp_path / ".windsurfrules").read_text()
    cmd_instructions_register()
    assert (tmp_path / ".synlynk" / "instructions.json").read_text() == first_manifest
    assert (tmp_path / "GEMINI.md").read_text() == first_gemini
    assert (tmp_path / ".windsurfrules").read_text() == first_windsurf


def test_register_sniffs_tool_from_marker_on_nonstandard_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    custom = tmp_path / "docs" / "CUSTOM_INSTRUCTIONS.md"
    custom.parent.mkdir()
    custom.write_text(
        '  <!-- synlynk:start version="0.4.1" tool="claude" -->\n'
        "custom instructions\n<!-- synlynk:end -->\n"
    )

    from synlynk.instructions import cmd_instructions_register

    cmd_instructions_register(str(custom))
    manifest = json.loads((tmp_path / ".synlynk" / "instructions.json").read_text())
    assert manifest["files"][str(custom)]["tool"] == "claude"


def test_extract_instruction_version_html_marker():
    from synlynk.instructions import extract_instruction_version

    content = '<!-- synlynk:start version="0.9.4" tool="agy" -->\nmanaged\n<!-- synlynk:end -->'
    assert extract_instruction_version(content) == "0.9.4"


def test_extract_instruction_version_hash_marker():
    from synlynk.instructions import extract_instruction_version

    content = '# synlynk:start version="0.13.0"\nmanaged\n# synlynk:end'
    assert extract_instruction_version(content) == "0.13.0"


def test_extract_instruction_version_harness_marker():
    from synlynk.instructions import extract_instruction_version

    content = '<!-- synlynk:harness v2.0.0 verified:2026-08-29T18:53:59Z -->\nmanaged\n<!-- /synlynk:harness -->'
    assert extract_instruction_version(content) == "v2.0.0"

    content_named = '<!-- synlynk:harness vsop-repair verified:2026-08-29T07:09:44Z -->\nmanaged'
    assert extract_instruction_version(content_named) == "vsop-repair"


def test_extract_instruction_version_missing():
    from synlynk.instructions import extract_instruction_version

    assert extract_instruction_version("Just normal content without markers") is None
    assert extract_instruction_version("") is None


def test_instruction_templates_prohibit_direct_todo_edits():
    from synlynk.instructions import (
        _build_templates,
        _build_cursor_mdc,
        _build_copilot_instructions,
        _build_windsurf_rules,
    )

    templates_dict = _build_templates()
    templates = [
        templates_dict["CLAUDE.md"],
        templates_dict["GEMINI.md"],
        templates_dict["AGENTS.md"],
        templates_dict["GROK.md"],
        templates_dict["AI_INSTRUCTIONS.md"],
        _build_cursor_mdc(),
        _build_copilot_instructions(),
        _build_windsurf_rules(),
    ]

    for tmpl in templates:
        assert "[ ] active" not in tmpl
        assert "Update task status in project-docs/todo.md" not in tmpl
        assert "Update task status in `project-docs/todo.md`" not in tmpl
        if "todo.md" in tmpl:
            assert "state.db" in tmpl
            assert "synlynk story done" in tmpl or "synlynk checkpoint" in tmpl


def test_tool_templates_point_to_canonical_shared_protocol():
    from synlynk.instructions import _build_templates

    templates = _build_templates()
    for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md"):
        tmpl = templates[name]
        assert "## Identity & Attribution" in tmpl
        assert "## Shared synlynk Protocol" in tmpl
        assert "Load `AI_INSTRUCTIONS.md` for the full shared synlynk protocol" in tmpl
        assert "## Operating Mode: Home vs. Away" not in tmpl
        assert "## Live Issues SOP" not in tmpl


def test_tool_templates_preserve_harness_branch_naming_and_format_prefixes():
    from synlynk.instructions import _build_templates

    templates = _build_templates()
    expected = {
        "CLAUDE.md": "claude",
        "GEMINI.md": "agy",
        "AGENTS.md": "codex",
        "GROK.md": "grok",
    }

    for name, harness in expected.items():
        tmpl = templates[name]
        assert (
            f"## Branch Naming\n"
            f"- `feat/{harness}/<description>` — new functionality\n"
            f"- `fix/{harness}/<description>` — bug fixes\n"
            "- `chore/<description>` — deps, docs, config\n"
        ) in tmpl
        assert f"- **Branch prefix:** `feat/{harness}/` or `fix/{harness}/`\n" in tmpl
        assert f"- **Branch prefix:** ``feat/{harness}/` or `fix/{harness}/``" not in tmpl


def test_tool_templates_are_substantially_smaller_than_canonical_protocol():
    from synlynk.instructions import _build_templates

    templates = _build_templates()
    tool_sizes = [len(templates[name].encode()) for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md")]
    canonical = templates["AI_INSTRUCTIONS.md"]
    assert max(tool_sizes) < 5000
    assert len(canonical.encode()) > sum(tool_sizes)
    for section in (
        "## Operating Mode: Home vs. Away",
        "## Git Worktree-First Policy",
        "## Live Issues SOP",
        "## Mid-Session Anti-Amnesia Protocol",
        "## Mandatory 4-Doc Discipline",
        "## GitHub Projects v2 Integration",
        "## PR Review Discipline",
    ):
        assert section in canonical
