# tests/test_instruction_reach.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))


def test_agy_baseline_replaces_gemini():
    from synlynk import AGENT_CAPABILITY_BASELINES
    assert "gemini" not in AGENT_CAPABILITY_BASELINES
    assert "agy" in AGENT_CAPABILITY_BASELINES


def test_gemini_md_template_has_no_transition_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _build_templates
    templates = _build_templates()
    assert "2026-06-18" not in templates["GEMINI.md"]
    assert "agy-2.x" in templates["GEMINI.md"]
    assert "gemini-2.x" not in templates["GEMINI.md"]


def test_extract_synlynk_section_html_markers():
    from synlynk import _extract_synlynk_section
    content = 'Before\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nmy block\n<!-- synlynk:end -->\nAfter'
    assert _extract_synlynk_section(content, "html") == "\nmy block\n"


def test_extract_synlynk_section_hash_markers():
    from synlynk import _extract_synlynk_section
    content = "Before\n# synlynk:start version=\"0.4.1\"\nmy block\n# synlynk:end\nAfter"
    assert _extract_synlynk_section(content, "hash") == "my block"


def test_extract_synlynk_section_none_marker_returns_whole():
    from synlynk import _extract_synlynk_section
    content = "entire file content"
    assert _extract_synlynk_section(content, "none") == content


def test_extract_synlynk_section_returns_none_when_absent():
    from synlynk import _extract_synlynk_section
    assert _extract_synlynk_section("no markers here", "html") is None


def test_compute_section_sha_is_deterministic():
    from synlynk import _compute_section_sha
    assert _compute_section_sha("hello") == _compute_section_sha("hello")
    assert _compute_section_sha("hello") != _compute_section_sha("world")
    assert len(_compute_section_sha("hello")) == 16


def test_write_instruction_file_creates_new_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    result = _write_instruction_file("CLAUDE.md", "claude", "synlynk content", "html")
    assert result is True
    text = open("CLAUDE.md").read()
    assert "<!-- synlynk:start" in text
    assert "synlynk content" in text
    assert "<!-- synlynk:end -->" in text


def test_write_instruction_file_appends_to_existing_no_markers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    open("CLAUDE.md", "w").write("# User content\nsome existing rules\n")
    from synlynk import _write_instruction_file
    _write_instruction_file("CLAUDE.md", "claude", "synlynk block", "html")
    text = open("CLAUDE.md").read()
    assert "# User content" in text          # preserved
    assert "synlynk block" in text           # appended
    assert text.index("# User content") < text.index("synlynk block")  # user content first


def test_write_instruction_file_replaces_existing_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = '# User\n<!-- synlynk:start version="0.4.0" tool="claude" -->\nold content\n<!-- synlynk:end -->\n# After'
    open("CLAUDE.md", "w").write(existing)
    from synlynk import _write_instruction_file
    _write_instruction_file("CLAUDE.md", "claude", "new content", "html")
    text = open("CLAUDE.md").read()
    assert "old content" not in text
    assert "new content" in text
    assert "# User" in text       # user content above preserved
    assert "# After" in text      # user content below preserved


def test_write_instruction_file_hash_markers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    _write_instruction_file(".windsurfrules", "windsurf", "line one\nline two", "hash")
    text = open(".windsurfrules").read()
    assert "# synlynk:start" in text
    assert "line one" in text
    assert "# synlynk:end" in text


def test_write_instruction_file_none_marker_owns_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".cursor/rules", exist_ok=True)
    from synlynk import _write_instruction_file
    _write_instruction_file(".cursor/rules/synlynk.mdc", "cursor", "---\nalwaysApply: true\n---\ncontent", "none")
    text = open(".cursor/rules/synlynk.mdc").read()
    assert "alwaysApply: true" in text
    assert "<!-- synlynk" not in text  # no markers for "none" style


def test_write_instruction_file_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _write_instruction_file
    _write_instruction_file(".github/copilot-instructions.md", "copilot", "synlynk rules", "html")
    assert os.path.exists(".github/copilot-instructions.md")


def test_build_cursor_mdc_has_frontmatter():
    from synlynk import _build_cursor_mdc
    content = _build_cursor_mdc()
    assert "alwaysApply: true" in content
    assert "---" in content
    assert "Session Start" in content
    assert "Git Worktree" in content


def test_build_copilot_instructions_no_frontmatter():
    from synlynk import _build_copilot_instructions
    content = _build_copilot_instructions()
    assert "---" not in content.splitlines()[0]  # no frontmatter on first line
    assert "Session Start" in content
    assert "synlynk checkpoint" in content


def test_build_windsurf_rules_is_terse():
    from synlynk import _build_windsurf_rules
    content = _build_windsurf_rules()
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) <= 8        # terse — no headers, bullet-style directives
    assert "context.md" in content
    assert "worktree" in content.lower() or "main" in content


def test_write_instruction_manifest_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _write_instruction_manifest
    import json
    entries = {"CLAUDE.md": {"tool": "claude", "sha": "abc123"}}
    _write_instruction_manifest(entries)
    manifest = json.load(open(".synlynk/instructions.json"))
    assert manifest["schema_version"] == 1
    assert manifest["files"]["CLAUDE.md"]["sha"] == "abc123"
    assert manifest["files"]["CLAUDE.md"]["tool"] == "claude"
    assert "last_checked" in manifest["files"]["CLAUDE.md"]


def test_load_instruction_manifest_returns_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _load_instruction_manifest
    assert _load_instruction_manifest() == {}


def test_manifest_sha_covers_only_synlynk_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk import _extract_synlynk_section, _compute_section_sha
    content_with_user = '# User stuff\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n# More user'
    section = _extract_synlynk_section(content_with_user, "html")
    sha = _compute_section_sha(section)
    # Changing user content outside markers must not change the sha
    content_modified = '# CHANGED user stuff\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n# More user'
    section2 = _extract_synlynk_section(content_modified, "html")
    sha2 = _compute_section_sha(section2)
    assert sha == sha2


def test_init_writes_cursor_rules_when_cursor_dir_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".cursor", exist_ok=True)
    os.makedirs(".synlynk", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert os.path.exists(".cursor/rules/synlynk.mdc")
    content = open(".cursor/rules/synlynk.mdc").read()
    assert "alwaysApply: true" in content


def test_init_skips_cursor_when_no_cursor_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert not os.path.exists(".cursor/rules/synlynk.mdc")


def test_init_appends_to_existing_copilot_instructions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".github", exist_ok=True)
    os.makedirs(".synlynk", exist_ok=True)
    open(".github/copilot-instructions.md", "w").write("# Existing rules\nDo something.\n")
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    text = open(".github/copilot-instructions.md").read()
    assert "# Existing rules" in text           # preserved
    assert "synlynk" in text.lower()            # appended
    assert text.index("# Existing rules") < text.index("<!-- synlynk:start")


def test_manifest_written_after_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    def mock_input(prompt):
        if "[y/N]" in prompt: return "n"
        if "Email" in prompt: return ""
        if "Industry" in prompt: return ""
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    assert os.path.exists(".synlynk/instructions.json")
    import json
    manifest = json.load(open(".synlynk/instructions.json"))
    assert manifest["schema_version"] == 1
    assert "AI_INSTRUCTIONS.md" in manifest["files"]


def test_check_instruction_drift_detects_section_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json
    # Write a file with a synlynk section
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\noriginal\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    import importlib
    sl = importlib.import_module("synlynk")
    original_sha = sl._compute_section_sha("\noriginal\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": original_sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    # Now modify the synlynk section externally
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\nmodified\n<!-- synlynk:end -->\n')
    drifted = sl._check_instruction_drift()
    assert "CLAUDE.md" in drifted


def test_check_instruction_drift_ignores_user_content_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json, importlib
    content = '# User\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sl = importlib.import_module("synlynk")
    sha = sl._compute_section_sha("\nblock\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    # Change only user content — synlynk section unchanged
    open("CLAUDE.md", "w").write('# CHANGED USER\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n')
    drifted = sl._check_instruction_drift()
    assert "CLAUDE.md" not in drifted


def test_check_instruction_drift_returns_empty_when_no_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import importlib
    sl = importlib.import_module("synlynk")
    assert sl._check_instruction_drift() == []


def test_instruction_drift_sentinel_fires_once_per_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json, importlib
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\noriginal\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sl = importlib.import_module("synlynk")
    sha = sl._compute_section_sha("\noriginal\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17T10:00:00"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\nmodified\n<!-- synlynk:end -->\n')
    sl._check_instruction_drift()  # first call — fires sentinel, updates manifest sha
    # second call — sha in manifest now matches file; must not fire again
    drifted2 = sl._check_instruction_drift()
    assert "CLAUDE.md" not in drifted2


def test_cmd_instructions_status_shows_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json, importlib
    content = '<!-- synlynk:start version="0.4.1" tool="claude" -->\nblock\n<!-- synlynk:end -->\n'
    open("CLAUDE.md", "w").write(content)
    sl = importlib.import_module("synlynk")
    sha = sl._compute_section_sha("\nblock\n")
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": sha, "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    sl.cmd_instructions_status()
    out = capsys.readouterr().out
    assert "CLAUDE.md" in out
    assert "clean" in out


def test_cmd_instructions_status_shows_drifted(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json, importlib
    open("CLAUDE.md", "w").write('<!-- synlynk:start version="0.4.1" tool="claude" -->\ncurrent\n<!-- synlynk:end -->\n')
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": "stale_sha_000", "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    sl = importlib.import_module("synlynk")
    sl.cmd_instructions_status()
    out = capsys.readouterr().out
    assert "drifted" in out


def test_cmd_instructions_status_shows_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json, importlib
    manifest = {
        "schema_version": 1, "generated_at": "2026-06-17T10:00:00",
        "synlynk_version": "0.4.1",
        "files": {"CLAUDE.md": {"tool": "claude", "sha": "abc", "last_checked": "2026-06-17"}}
    }
    json.dump(manifest, open(".synlynk/instructions.json", "w"))
    sl = importlib.import_module("synlynk")
    sl.cmd_instructions_status()
    out = capsys.readouterr().out
    assert "missing" in out
