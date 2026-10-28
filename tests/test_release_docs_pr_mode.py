import subprocess

from scripts.generate_command_docs import render_readme_section, render_reference_doc
from synlynk.cli import build_parser
from synlynk.release_readme import validate_readme_for_release


def _git(root, *args):
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_pr_repo(root, *, readme_touched):
    (root / "docs" / "reference").mkdir(parents=True)
    (root / "docs" / "reference" / "commands.md").write_text(
        render_reference_doc(), encoding="utf-8"
    )
    (root / "README.md").write_text(
        """<img src="https://img.shields.io/badge/version-0.25.5-blue">
<img src="https://img.shields.io/badge/tests-5000%20collected-brightgreen">

**v0.25.5:** Release integrity stabilization with PR-aware documentation checks.

```bash
pipx install synlynk
```

"""
        + render_readme_section()
        + "\n",
        encoding="utf-8",
    )
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(root, "switch", "-c", "feature")
    if readme_touched:
        with (root / "README.md").open("a", encoding="utf-8") as handle:
            handle.write("\nPR documentation change.\n")
    else:
        (root / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "feature")


def test_pr_mode_ignores_count_drift_when_readme_is_untouched(tmp_path, monkeypatch):
    _init_pr_repo(tmp_path, readme_touched=False)
    # Push and tag workflows set this to "" rather than leaving it unset.
    monkeypatch.setenv("GITHUB_BASE_REF", "")

    findings = validate_readme_for_release(
        str(tmp_path), "0.25.5", collected_test_count=5010, pr_mode=True
    )

    assert not any(finding.check == "test_count" for finding in findings)


def test_pr_mode_still_enforces_count_when_base_ref_is_missing(tmp_path, monkeypatch):
    _init_pr_repo(tmp_path, readme_touched=False)
    monkeypatch.setenv("GITHUB_BASE_REF", "does-not-exist")

    findings = validate_readme_for_release(
        str(tmp_path), "0.25.5", collected_test_count=5010, pr_mode=True
    )

    assert any(finding.check == "test_count" for finding in findings)


def test_pr_mode_rejects_count_drift_when_readme_is_touched(tmp_path):
    _init_pr_repo(tmp_path, readme_touched=True)

    findings = validate_readme_for_release(
        str(tmp_path), "0.25.5", collected_test_count=5010, pr_mode=True
    )

    assert any(finding.check == "test_count" for finding in findings)


def test_full_release_mode_rejects_count_drift_when_readme_is_untouched(tmp_path):
    _init_pr_repo(tmp_path, readme_touched=False)

    findings = validate_readme_for_release(
        str(tmp_path), "0.25.5", collected_test_count=5010
    )

    assert any(finding.check == "test_count" for finding in findings)


def test_release_parser_accepts_pr_mode():
    args = build_parser().parse_args(["release", "--check-docs", "--pr-mode"])

    assert args.pr_mode is True
