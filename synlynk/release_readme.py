"""README consistency checks for named releases (#1242)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from synlynk.taxonomy import COMMAND_TAXONOMY

WAIVABLE_CHECKS = frozenset(
    {"test_count", "hero", "install", "links", "commands"}
)
ALL_CHECKS = frozenset({"version"}) | WAIVABLE_CHECKS
PLANNED_MARKERS = (
    "coming soon",
    "planned",
    "not yet",
    "unreleased",
    "will ship",
)
COMMANDS_START = "<!-- commands:start -->"
COMMANDS_END = "<!-- commands:end -->"
_VERSION_BADGE_RE = re.compile(r"badge/version-(\d+\.\d+\.\d+)", re.IGNORECASE)
_TEST_BADGE_RE = re.compile(
    r"tests-(\d+)(?:%20|\s)+(passing|collected)", re.IGNORECASE
)
_TEST_PROSE_RE = re.compile(
    r"(\d+)\s+tests\s+(passing|collected)\b", re.IGNORECASE
)
_HERO_RE = re.compile(r"\*\*v(\d+\.\d+\.\d+):\*\*\s*(.*)", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_SYNLYNK_CMD_RE = re.compile(
    r"(?<![\w.-])synlynk(?:\.py)?\s+"
    r"([a-z][a-z0-9_-]*(?:\s+[a-z][a-z0-9_-]*)?)"
)
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected", re.IGNORECASE)
_GITHUB_RELATIVE_ROUTE_RE = re.compile(
    r"^(?:\.\./)+(discussions|issues|pulls|actions|releases|security|"
    r"wiki|projects|pulse|graphs|network|settings|packages)(?:/.*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReadmeFinding:
    check: str
    message: str
    waivable: bool = True


def parse_waivers(items: Optional[Sequence[str]]) -> Dict[str, str]:
    """Parse `--waive check=reason` values. Empty reasons are rejected."""
    waivers: Dict[str, str] = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValueError(
                f"invalid --waive {raw!r}: expected check=reason "
                f"(checks: {', '.join(sorted(ALL_CHECKS))})"
            )
        check, reason = raw.split("=", 1)
        check = check.strip()
        reason = reason.strip()
        if check not in ALL_CHECKS:
            raise ValueError(
                f"unknown README check {check!r}; "
                f"valid checks: {', '.join(sorted(ALL_CHECKS))}"
            )
        if not reason:
            raise ValueError(f"--waive {check}= requires a non-empty reason")
        waivers[check] = reason
    return waivers


def collect_pytest_test_count(root: str) -> Optional[int]:
    """Return pytest's *collected* test count (not pass/fail).

    Collection is the numeric source of truth for README test-count claims.
    This does not run the suite and does not attest that tests pass.
    Returns 0 if tests/ is absent, or None if collection fails.
    """
    tests_dir = os.path.join(root, "tests")
    if not os.path.isdir(tests_dir):
        return 0
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tests_dir, "--collect-only", "-q", "--noconftest"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    blob = (result.stdout or "") + "\n" + (result.stderr or "")
    if re.search(r"no tests collected", blob, re.IGNORECASE):
        return 0
    match = _COLLECTED_RE.search(blob)
    if match:
        return int(match.group(1))
    return None


def _taxonomy_commands() -> set:
    return {entry["command"] for entry in COMMAND_TAXONOMY}


def _generated_command_section() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.generate_command_docs import render_readme_section

    return render_readme_section()


def _relative_link_target(target: str) -> Optional[str]:
    path = target.strip()
    if not path or path.startswith(("#", "http://", "https://", "mailto:", "ftp://")):
        return None
    path = path.split("#", 1)[0].split("?", 1)[0]
    if not path or os.path.isabs(path):
        return None
    return path


def _is_github_relative_route(rel: str) -> bool:
    """GitHub README routes like ../../discussions are UI tabs, not repo files."""
    normalized = rel.replace("\\", "/").strip()
    return bool(_GITHUB_RELATIVE_ROUTE_RE.match(normalized))


def _path_is_inside_root(root: str, dest: str) -> bool:
    root_n = os.path.abspath(os.path.normpath(root))
    dest_n = os.path.abspath(os.path.normpath(dest))
    try:
        return os.path.commonpath([root_n, dest_n]) == root_n
    except ValueError:
        return False


def _line_is_planned(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in PLANNED_MARKERS)


def _extract_command_candidates(text: str) -> List[Tuple[str, str]]:
    """Command mentions from inline code and fenced blocks only — not prose."""
    candidates: List[Tuple[str, str]] = []
    for fence in _FENCE_RE.finditer(text):
        for line in fence.group(1).splitlines():
            if _line_is_planned(line):
                continue
            for match in _SYNLYNK_CMD_RE.finditer(line):
                candidates.append((line, match.group(1).strip()))

    remainder = _FENCE_RE.sub("\n", text)
    for inline in _INLINE_CODE_RE.finditer(remainder):
        line_start = remainder.rfind("\n", 0, inline.start()) + 1
        line_end = remainder.find("\n", inline.start())
        if line_end == -1:
            line_end = len(remainder)
        line = remainder[line_start:line_end]
        if _line_is_planned(line):
            continue
        for match in _SYNLYNK_CMD_RE.finditer(inline.group(1)):
            candidates.append((line, match.group(1).strip()))
    return candidates


def _command_is_shipped(cmd: str, shipped: set) -> bool:
    if cmd in shipped:
        return True
    first = cmd.split()[0]
    if first in shipped or any(
        cmd == item or cmd.startswith(item + " ") for item in shipped
    ):
        return True
    if first in {"--version", "help"} or first.startswith("-"):
        return True
    return False


def _split_test_count_claims(text: str) -> Tuple[List[int], List[int]]:
    """Return (collected_claims, passing_claims) from badge and prose."""
    collected: List[int] = []
    passing: List[int] = []
    for number, kind in _TEST_BADGE_RE.findall(text) + _TEST_PROSE_RE.findall(text):
        bucket = passing if kind.lower() == "passing" else collected
        bucket.append(int(number))
    return collected, passing


def _unique_claim(values: Sequence[int]) -> Optional[int]:
    unique = set(values)
    if len(unique) == 1:
        return next(iter(unique))
    return None


def validate_readme_for_release(
    root: str,
    expected_version: str,
    collected_test_count: Optional[int] = None,
    waivers: Optional[Dict[str, str]] = None,
    verified_passing_count: Optional[int] = None,
) -> List[ReadmeFinding]:
    """Return unwaived README findings for a named-release version."""
    expected = expected_version.strip().lstrip("v")
    waivers = waivers or {}
    root = os.path.abspath(os.path.normpath(root))
    readme_path = os.path.join(root, "README.md")
    findings: List[ReadmeFinding] = []

    if not os.path.isfile(readme_path):
        findings.append(
            ReadmeFinding("version", "README.md is missing", waivable=False)
        )
        return _apply_waivers(findings, waivers)

    text = open(readme_path, encoding="utf-8").read()

    badge_versions = _VERSION_BADGE_RE.findall(text)
    if not badge_versions:
        findings.append(
            ReadmeFinding(
                "version",
                f"README has no version badge; expected {expected}",
                waivable=False,
            )
        )
    else:
        advertised = badge_versions[0]
        if advertised != expected:
            findings.append(
                ReadmeFinding(
                    "version",
                    f"README version badge is {advertised}, expected {expected}",
                    waivable=False,
                )
            )

    collected_claims, passing_claims = _split_test_count_claims(text)
    unique_collected = set(collected_claims)
    unique_passing = set(passing_claims)
    if len(unique_collected) > 1:
        findings.append(
            ReadmeFinding(
                "test_count",
                "README collected-test-count claims disagree: "
                + ", ".join(str(n) for n in sorted(unique_collected)),
            )
        )
    if len(unique_passing) > 1:
        findings.append(
            ReadmeFinding(
                "test_count",
                "README passing-test-count claims disagree: "
                + ", ".join(str(n) for n in sorted(unique_passing)),
            )
        )

    if passing_claims:
        claimed_passing = _unique_claim(passing_claims)
        if verified_passing_count is None:
            shown = (
                str(claimed_passing)
                if claimed_passing is not None
                else ", ".join(str(n) for n in sorted(unique_passing))
            )
            findings.append(
                ReadmeFinding(
                    "test_count",
                    f"README claims {shown} tests passing, but this check only "
                    "runs pytest --collect-only (not a pass/fail run). Use "
                    "'N tests collected' wording, or supply a verified passing "
                    "count from a full-suite run.",
                )
            )
        elif claimed_passing is not None and claimed_passing != verified_passing_count:
            findings.append(
                ReadmeFinding(
                    "test_count",
                    f"README claims {claimed_passing} tests passing, full-suite "
                    f"verification reported {verified_passing_count} passing",
                )
            )

    if collected_test_count is None:
        collected_test_count = collect_pytest_test_count(root)

    if collected_test_count is None:
        findings.append(
            ReadmeFinding(
                "test_count",
                "could not collect pytest tests to verify README "
                "collected-test-count claims (collection is not a pass/fail run)",
            )
        )
    else:
        claimed_collected = _unique_claim(collected_claims)
        if unique_collected:
            if (
                claimed_collected is not None
                and claimed_collected != collected_test_count
            ):
                findings.append(
                    ReadmeFinding(
                        "test_count",
                        f"README claims {claimed_collected} tests collected, "
                        f"pytest collected {collected_test_count} "
                        "(count only; not pass/fail)",
                    )
                )
        elif collected_test_count > 0 and verified_passing_count is None:
            findings.append(
                ReadmeFinding(
                    "test_count",
                    "README has no collected-test-count claim; pytest collected "
                    f"{collected_test_count}. Use 'N tests collected' rather "
                    "than 'N tests passing'.",
                )
            )

    hero = _HERO_RE.search(text)
    if hero is None:
        findings.append(
            ReadmeFinding("hero", "README is missing a **vX.Y.Z:** hero/release summary")
        )
    else:
        hero_version, summary = hero.group(1), hero.group(2).strip()
        if hero_version != expected:
            findings.append(
                ReadmeFinding(
                    "hero",
                    f"README hero version is {hero_version}, expected {expected}",
                )
            )
        if len(summary) < 20:
            findings.append(
                ReadmeFinding("hero", "README hero/release summary is empty or too short")
            )

    install_ok = (
        "pipx install" in text
        or "install.sh" in text
        or "python3 bin/synlynk.py" in text
    )
    if not install_ok:
        findings.append(
            ReadmeFinding(
                "install",
                "README is missing current install instructions "
                "(pipx, install.sh, or python3 bin/synlynk.py)",
            )
        )

    for raw_target in _MD_LINK_RE.findall(text):
        rel = _relative_link_target(raw_target)
        if rel is None:
            continue
        if _is_github_relative_route(rel):
            continue
        dest = os.path.normpath(os.path.join(root, rel))
        if not _path_is_inside_root(root, dest):
            findings.append(
                ReadmeFinding("links", f"README link escapes repo root: {rel}")
            )
        elif not os.path.exists(dest):
            findings.append(
                ReadmeFinding("links", f"README links to missing path: {rel}")
            )

    start = text.find(COMMANDS_START)
    end = text.find(COMMANDS_END)
    generated = None
    if start == -1 or end == -1 or end < start:
        findings.append(
            ReadmeFinding(
                "commands",
                "README is missing <!-- commands:start --> / <!-- commands:end --> markers",
            )
        )
        body_for_mentions = text
    else:
        actual = text[start:end + len(COMMANDS_END)]
        try:
            generated = _generated_command_section()
        except Exception as exc:
            findings.append(
                ReadmeFinding("commands", f"could not render command section: {exc}")
            )
            generated = None
        if generated is not None and actual.strip() != generated.strip():
            findings.append(
                ReadmeFinding(
                    "commands",
                    "README command section is stale — run "
                    "`python3 scripts/generate_command_docs.py`",
                )
            )
        body_for_mentions = text[:start] + text[end + len(COMMANDS_END):]

    shipped = _taxonomy_commands()
    for _line, cmd in _extract_command_candidates(body_for_mentions):
        if _command_is_shipped(cmd, shipped):
            continue
        findings.append(
            ReadmeFinding(
                "commands",
                f"README claims shipped command `synlynk {cmd}` "
                "which is not in COMMAND_TAXONOMY (mark as planned or drop it)",
            )
        )

    return _apply_waivers(findings, waivers)


def _apply_waivers(
    findings: Iterable[ReadmeFinding], waivers: Dict[str, str]
) -> List[ReadmeFinding]:
    remaining: List[ReadmeFinding] = []
    for finding in findings:
        if finding.check in waivers and finding.waivable:
            continue
        remaining.append(finding)
    return remaining


def format_readme_check_report(
    findings: Sequence[ReadmeFinding],
    expected_version: str,
    waivers: Optional[Dict[str, str]] = None,
) -> str:
    """Human-readable named-release README checklist."""
    waivers = waivers or {}
    failed = {f.check for f in findings}
    lines = [f"README sync for v{expected_version.lstrip('v')}"]
    labels = (
        ("version", "version metadata"),
        (
            "test_count",
            "collected test count (pytest --collect-only; "
            "'passing' requires a verified full-suite run)",
        ),
        ("hero", "hero/release summary"),
        ("install", "install instructions"),
        ("links", "command/documentation links"),
        ("commands", "shipped vs planned commands"),
    )
    for check, label in labels:
        if check in failed:
            lines.append(f"[ ] {label}")
        elif check in waivers and check != "version":
            lines.append(f"[waived] {label}: {waivers[check]}")
        else:
            lines.append(f"[x] {label}")
    for finding in findings:
        lines.append(f"  - {finding.check}: {finding.message}")
        if finding.check == "version" and "version" in waivers:
            lines.append(
                "  - version cannot be waived; README must advertise the release version"
            )
    return "\n".join(lines)
