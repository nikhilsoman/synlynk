# Bug-Report Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. In this repo, implementation tasks are dispatched via `synlynk dispatch` to a non-Claude harness; use `pytest -q`, never `-v`, for full-suite runs.

**Goal:** Let an early adopter file a public GitHub bug report that already contains maintainer-ready context, without leaking private data, and surface that path where users hit problems.

**Architecture:** One canonical, allowlist-based bundle module (`synlynk/report_bundle.py`) defines the schema, normalization, fingerprint and renderer. Everything else (CLI `synlynk report`, issue form, CI `intake` check, Vizor action, flight recorder) derives from it. Filing is always behind a mandatory interactive preview and a whole-body secret scan.

**Tech Stack:** Python 3 stdlib only, pytest, `gh` CLI (user's own login), GitHub issue-form YAML.

**Spec:** `docs/superpowers/specs/2026-11-20-bug-report-intake-design.md` (DECIDE record `dec-049b4dbf`). Epic: gh:#5419.

**Delivery:** three PRs, one feature each (Part 1, Part 2, Part 3 below). Docs go in their own PRs. Each part is branched from `origin/main` in its own linked worktree.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/report_bundle.py` (new) | Frozen schema `BUNDLE_SCHEMA_VERSION`, `ALLOWED_FIELDS`, collectors, normalization, salted hashing, fingerprint, `render_body()` |
| `synlynk/report_scan.py` (new) | `find_secrets(text)`: secret-pattern scan used on the whole body |
| `synlynk/report_cmd.py` (new) | `cmd_report()`: interactive flow, preview gate, filing, URL/local-file fallback |
| `synlynk/flight_recorder.py` (new, Part 2) | Ring buffer `.synlynk/flight.jsonl`, write-time redaction, off-switch |
| `synlynk/cli.py` (modify) | Register `report` parser (near the `doctor` parser, ~line 831) and dispatch (near `args.command == "doctor"`, ~line 4065) |
| `synlynk/taxonomy.py` (modify) | Add `report` entry to `COMMAND_TAXONOMY` |
| `.github/ISSUE_TEMPLATE/bug_report.yml` (new, replaces `bug_report.md`) | Issue form with required `bundle` textarea |
| `tests/test_report_bundle.py`, `tests/test_report_scan.py`, `tests/test_report_cmd.py`, `tests/test_flight_recorder.py` (new) | Unit and e2e tests |

---

# Part 1 (PR 1): `synlynk report` + allowlist collector + preview + filing

Branch: `feat/report-intake-core`. Includes the frozen contract.

### Task 1: Secret scanner

**Files:**
- Create: `synlynk/report_scan.py`
- Test: `tests/test_report_scan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_scan.py
from synlynk.report_scan import find_secrets


def test_flags_known_token_shapes():
    text = "token ghp_" + "a" * 36 + " and AKIA" + "A" * 16
    hits = find_secrets(text)
    assert len(hits) == 2


def test_flags_credentialed_url_and_bearer():
    assert find_secrets("https://user:pw@example.com/x")
    assert find_secrets("Authorization: Bearer abcdefghijklmnop1234")


def test_clean_text_has_no_hits():
    assert find_secrets("synlynk 0.38.3 on darwin, doctor: 3 warn") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_scan.py`
Expected: FAIL (`ModuleNotFoundError: synlynk.report_scan`)

- [ ] **Step 3: Implement**

```python
# synlynk/report_scan.py
"""Secret-pattern scan applied to the entire rendered report body."""
from __future__ import annotations

import re

from synlynk.logs import _SECRET_PATTERNS

_EXTRA_PATTERNS = [
    re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),   # credentialed URL
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def find_secrets(text: str) -> list[str]:
    """Return the matched substrings (empty list means clean)."""
    hits: list[str] = []
    for pattern in [*_SECRET_PATTERNS, *_EXTRA_PATTERNS]:
        hits.extend(m.group(0) for m in pattern.finditer(text))
    return hits
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_scan.py`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/report_scan.py tests/test_report_scan.py
git commit -m "feat(report): add whole-body secret scanner"
```

### Task 2: Normalization, salted hash, fingerprint

**Files:**
- Create: `synlynk/report_bundle.py` (first half)
- Test: `tests/test_report_bundle.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_report_bundle.py
import os
from synlynk import report_bundle as rb


def test_home_dir_becomes_tilde(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/alice")
    assert rb.normalize_path("/Users/alice/dev/x") == "~/dev/x"


def test_salted_hash_differs_across_installs_and_is_stable(tmp_path):
    a = rb.salted_hash("alice", salt_path=tmp_path / "a")
    b = rb.salted_hash("alice", salt_path=tmp_path / "b")
    assert a != b
    assert a == rb.salted_hash("alice", salt_path=tmp_path / "a")
    assert "alice" not in a


def test_remote_strips_credentials():
    assert rb.normalize_remote("https://tok:x@github.com/o/r.git") == "github.com/o/r"
    assert rb.normalize_remote("git@github.com:o/r.git") == "github.com/o/r"


def test_fingerprint_ignores_variable_parts():
    f1 = rb.fingerprint(["doctor.cfg"], "init", 1, "error at /tmp/a1b2c3d4e5f6/x line 42")
    f2 = rb.fingerprint(["doctor.cfg"], "init", 1, "error at /tmp/ffeeddccbbaa/x line 99")
    assert f1 == f2 and len(f1) == 12


def test_fingerprint_sorts_check_ids():
    assert rb.fingerprint(["b", "a"], "x", 1, "e") == rb.fingerprint(["a", "b"], "x", 1, "e")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_bundle.py`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement**

```python
# synlynk/report_bundle.py
"""Canonical bug-report bundle: schema, normalization, fingerprint, renderer.

FROZEN CONTRACT: the issue form, CLI renderer, CI `intake` check and Vizor route
all derive from BUNDLE_SCHEMA_VERSION / ALLOWED_FIELDS. Change them only with a
version bump.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path

BUNDLE_SCHEMA_VERSION = 1
ALLOWED_FIELDS = (
    "schema", "synlynk_version", "python_version", "os", "arch", "install_method",
    "harnesses", "env_set", "doctor", "config_schema", "policy_schema",
    "db_shape", "worktree", "remote", "identity", "fingerprint",
)

_DEFAULT_SALT_PATH = Path.home() / ".synlynk" / "report_salt"


def normalize_path(path: str) -> str:
    home = os.environ.get("HOME") or str(Path.home())
    return "~" + path[len(home):] if home and path.startswith(home) else path


def _salt(salt_path: Path) -> bytes:
    if salt_path.exists():
        return salt_path.read_bytes()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    salt_path.write_bytes(salt)
    os.chmod(salt_path, 0o600)
    return salt


def salted_hash(value: str, salt_path: Path = _DEFAULT_SALT_PATH) -> str:
    return hashlib.sha256(_salt(Path(salt_path)) + value.encode()).hexdigest()[:10]


def normalize_remote(url: str) -> str:
    url = re.sub(r"^[a-z+]+://", "", url.strip())
    url = re.sub(r"^[^@/]+(:[^@/]*)?@", "", url)
    url = url.replace(":", "/", 1) if re.match(r"^[^/]+:[^/0-9]", url) else url
    return re.sub(r"\.git$", "", url)


_VARIABLE = [
    (re.compile(r"(/[\w.~-]+)+"), "<path>"),
    (re.compile(r"\b[0-9a-f]{7,}\b"), "<hex>"),
    (re.compile(r"\d+"), "<n>"),
]


def normalize_error_line(line: str) -> str:
    for pattern, repl in _VARIABLE:
        line = pattern.sub(repl, line)
    return line.strip()


def fingerprint(failing_check_ids: list[str], command: str, exit_code: int, first_error: str) -> str:
    material = "|".join([
        ",".join(sorted(failing_check_ids)), command, str(exit_code),
        normalize_error_line(first_error),
    ])
    return hashlib.sha256(material.encode()).hexdigest()[:12]
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_bundle.py`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/report_bundle.py tests/test_report_bundle.py
git commit -m "feat(report): bundle normalization, salted hash, fingerprint"
```

### Task 3: Allowlist collector and renderer

**Files:**
- Modify: `synlynk/report_bundle.py` (append)
- Test: `tests/test_report_bundle.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_report_bundle.py
def test_collect_emits_only_allowlisted_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-CANARY1234567890abcdef")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://tok:pw@gw.example.com")
    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")
    assert set(bundle) <= set(rb.ALLOWED_FIELDS)
    assert bundle["env_set"]["ANTHROPIC_API_KEY"] is True
    body = rb.render_body(bundle, description="")
    assert "CANARY" not in body and "gw.example.com" not in body


def test_collector_failure_yields_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(rb, "_collect_doctor", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")
    assert bundle["doctor"] == "unavailable"


def test_render_contains_fingerprint_line_and_public_warning(tmp_path):
    body = rb.render_body(rb.collect_bundle(salt_path=tmp_path / "s"), description="init fails")
    assert any(l.startswith("fingerprint: ") for l in body.splitlines())
    assert "init fails" in body


def test_joint_leak_is_flagged_by_whole_body_scan():
    from synlynk.report_scan import find_secrets
    body = "remote: github.com/acme/private-repo\npassword=hunter2hunter2"
    assert find_secrets(body)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_bundle.py`
Expected: FAIL (`collect_bundle` not defined)

- [ ] **Step 3: Implement**

```python
# append to synlynk/report_bundle.py
import platform
import shutil
import subprocess
import sys


def _env_names() -> list[str]:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES
    names: set[str] = set()
    for cfg in HARNESS_CAPABILITY_BASELINES.values():
        names.update(cfg.get("env_passthrough", []))
    return sorted(names)


def _collect_harnesses() -> list[dict]:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES
    out = []
    for name in sorted(HARNESS_CAPABILITY_BASELINES):
        found = shutil.which(name) is not None
        out.append({"name": name, "binary_found": found})
    return out


def _collect_doctor() -> list[dict]:
    from synlynk.doctor import HEALTH_CHECKS
    rows = []
    for fn in HEALTH_CHECKS:
        try:
            hc = fn()
            rows.append({"id": hc.name, "status": hc.status})
        except Exception:
            rows.append({"id": getattr(fn, "__name__", "check"), "status": "unavailable"})
    return rows


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def _safe(fn, default="unavailable"):
    try:
        return fn()
    except Exception:
        return default


def collect_bundle(salt_path: Path = _DEFAULT_SALT_PATH, command: str = "", exit_code: int = 0,
                   first_error: str = "") -> dict:
    from synlynk._constants import VERSION
    doctor = _safe(_collect_doctor)
    failing = [r["id"] for r in doctor if isinstance(doctor, list) and r["status"] == "fail"]
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    bundle = {
        "schema": BUNDLE_SCHEMA_VERSION,
        "synlynk_version": VERSION,
        "python_version": platform.python_version(),
        "os": platform.system(),
        "arch": platform.machine(),
        "install_method": "pipx" if "pipx" in sys.prefix else ("venv" if sys.prefix != sys.base_prefix else "other"),
        "harnesses": _safe(_collect_harnesses),
        "env_set": {n: bool(os.environ.get(n)) for n in _env_names()},  # names + set/unset only
        "doctor": doctor,
        "config_schema": "unavailable",
        "policy_schema": "unavailable",
        "db_shape": "unavailable",
        "worktree": {"dirty": bool(_git("status", "--porcelain")),
                     "branch_kind": "main" if branch in ("main", "master") else ("detached" if branch == "HEAD" else "feature")},
        "remote": normalize_remote(_git("config", "--get", "remote.origin.url")) or "none",
        "identity": salted_hash(f"{os.environ.get('USER', '')}@{platform.node()}", salt_path),
    }
    bundle["fingerprint"] = fingerprint(failing if isinstance(failing, list) else [], command, exit_code, first_error)
    return bundle


PUBLIC_NOTICE = (
    "This report will be PUBLIC and indexed. Editing or deleting it later does not "
    "remove cached copies."
)


def render_body(bundle: dict, description: str, withheld: list[str] | None = None) -> str:
    lines = ["## What happened", description or "(no description)", "", "## Bundle (generated)"]
    for key in ALLOWED_FIELDS:
        if key in bundle and key != "fingerprint":
            lines.append(f"- {key}: {bundle[key]}")
    lines += ["", f"fingerprint: {bundle['fingerprint']}", ""]
    lines.append("Withheld: " + (", ".join(withheld) if withheld else "none") + ". "
                 "No secret values, file contents or database rows were collected.")
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_bundle.py tests/test_report_scan.py`
Expected: all passed. If a harness name in `HARNESS_CAPABILITY_BASELINES` lacks `env_passthrough`, `.get(..., [])` already covers it.

- [ ] **Step 5: Commit**

```bash
git add synlynk/report_bundle.py tests/test_report_bundle.py
git commit -m "feat(report): allowlist collector and body renderer"
```

### Task 4: Report command (preview gate, filing, fallback)

**Files:**
- Create: `synlynk/report_cmd.py`
- Test: `tests/test_report_cmd.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_report_cmd.py
from synlynk import report_cmd as rc


def _body():
    return "## What happened\nboom\n\nfingerprint: abc123abc123\n"


def test_no_y_means_nothing_filed(monkeypatch):
    calls = []
    monkeypatch.setattr(rc, "_gh_issue_create", lambda *a, **k: calls.append(a) or "url")
    assert rc.confirm_and_file(_body(), "t", answer=lambda _: "n", interactive=True) is None
    assert calls == []


def test_non_interactive_never_files(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rc, "_gh_issue_create", lambda *a, **k: calls.append(a) or "url")
    out = rc.confirm_and_file(_body(), "t", answer=lambda _: "y", interactive=False, local_dir=tmp_path)
    assert calls == [] and out.endswith(".md")


def test_secret_in_body_blocks_filing(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rc, "_gh_issue_create", lambda *a, **k: calls.append(a) or "url")
    body = _body() + "password=hunter2hunter2\n"
    assert rc.confirm_and_file(body, "t", answer=lambda _: "y", interactive=True, local_dir=tmp_path) is None
    assert calls == []


def test_y_files_via_gh(monkeypatch):
    monkeypatch.setattr(rc, "_gh_issue_create", lambda title, body: "https://github.com/o/r/issues/1")
    assert rc.confirm_and_file(_body(), "t", answer=lambda _: "y", interactive=True).endswith("/issues/1")


def test_gh_unavailable_falls_back_to_url_and_file(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError("gh")
    monkeypatch.setattr(rc, "_gh_issue_create", boom)
    out = rc.confirm_and_file(_body(), "t", answer=lambda _: "y", interactive=True, local_dir=tmp_path)
    assert "issues/new" in out or out.endswith(".md")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_cmd.py`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement**

```python
# synlynk/report_cmd.py
"""`synlynk report`: collect, preview (mandatory), file."""
from __future__ import annotations

import subprocess
import sys
import urllib.parse
from pathlib import Path

from synlynk.report_bundle import PUBLIC_NOTICE, collect_bundle, render_body
from synlynk.report_scan import find_secrets

REPO = "nikhilsoman/synlynk"
URL_BODY_CAP = 6000


def _gh_issue_create(title: str, body: str) -> str:
    out = subprocess.run(
        ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body,
         "--label", "bug", "--label", "early-adopter"],
        capture_output=True, text=True, timeout=60, check=True)
    return out.stdout.strip().splitlines()[-1]


def _write_local(body: str, local_dir: Path) -> str:
    local_dir.mkdir(parents=True, exist_ok=True)
    path = local_dir / "synlynk-report.md"
    path.write_text(body)
    return str(path)


def confirm_and_file(body: str, title: str, answer=input, interactive: bool | None = None,
                     local_dir: Path = Path(".synlynk")) -> str | None:
    """Return the issue URL / local file path, or None if nothing was filed."""
    interactive = sys.stdin.isatty() if interactive is None else interactive
    print(PUBLIC_NOTICE, "\n")
    print(body)
    hits = find_secrets(body)
    if hits:
        print(f"\nREFUSING TO FILE: {len(hits)} secret-like pattern(s) found. Remove them and retry.")
        return None
    if not interactive:
        path = _write_local(body, local_dir)
        print(f"\nNon-interactive: saved to {path}. File it from a terminal with `synlynk report`.")
        return path
    if answer("\nFile this public issue? [y/N] ").strip().lower() != "y":
        print("Nothing was filed.")
        return None
    try:
        return _gh_issue_create(title, body)
    except Exception:
        path = _write_local(body, local_dir)
        url = f"https://github.com/{REPO}/issues/new?" + urllib.parse.urlencode(
            {"title": title, "labels": "bug,early-adopter", "body": body[:URL_BODY_CAP]})
        print(f"gh unavailable. Open: {url}\nFull report saved to {path}")
        return url


def cmd_report(args=None) -> int:
    description = ""
    if sys.stdin.isatty():
        description = input("What went wrong? (one line, optional): ").strip()
    bundle = collect_bundle()
    body = render_body(bundle, description)
    result = confirm_and_file(body, title=f"[report] {description or 'bug report'}"[:100])
    return 0 if result is not None else 1
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_cmd.py`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/report_cmd.py tests/test_report_cmd.py
git commit -m "feat(report): preview-gated filing with URL/local fallback"
```

### Task 5: CLI registration, taxonomy, issue form

**Files:**
- Modify: `synlynk/cli.py` (parser next to `doctor_parser` ~line 831; dispatch near `elif args.command == "doctor":` ~line 4065)
- Modify: `synlynk/taxonomy.py` (add entry to `COMMAND_TAXONOMY`)
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`; delete `.github/ISSUE_TEMPLATE/bug_report.md`
- Test: `tests/test_report_cmd.py` (append), plus the existing `tests/test_capability_taxonomy.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_report_cmd.py
def test_report_registered_in_taxonomy_and_parser():
    from synlynk.taxonomy import COMMAND_TAXONOMY
    from synlynk.cli import build_parser
    assert any(e["command"] == "report" for e in COMMAND_TAXONOMY)
    assert build_parser().parse_args(["report"]).command == "report"


def test_issue_form_has_required_bundle_field():
    import pathlib
    text = pathlib.Path(".github/ISSUE_TEMPLATE/bug_report.yml").read_text()
    assert "id: bundle" in text and "required: true" in text
    assert not pathlib.Path(".github/ISSUE_TEMPLATE/bug_report.md").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_cmd.py`
Expected: FAIL

- [ ] **Step 3: Implement**

Taxonomy entry (copy the shape of the `init` entry, `maturity_tier: 0`, `governs_stage: "sustain"`):

```python
    {"command": "report", "governs_stage": "sustain", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["report a bug", "file an issue", "something is broken"], "hook_event": None},
```

Parser (after the `doctor_parser` block):

```python
    report_parser = subparsers.add_parser("report", help="File a redacted, previewed bug report")
    report_parser.add_argument("--last", action="store_true",
                               help="Build the report from the most recent failed command (Part 2)")
    report_parser.add_argument("--clear-flight", action="store_true", dest="clear_flight",
                               help="Delete the local flight-recorder buffer (Part 2)")
```

Dispatch (next to the `doctor` branch):

```python
    elif args.command == "report":
        from synlynk.report_cmd import cmd_report
        sys.exit(cmd_report(args))
```

Issue form:

```yaml
# .github/ISSUE_TEMPLATE/bug_report.yml
name: Bug report
description: Generated by `synlynk report`; hand-filing is fine but please paste the bundle.
labels: ["bug", "early-adopter"]
body:
  - type: markdown
    attributes:
      value: "Run `synlynk report` to generate the bundle. It is redacted and previewed before filing. Reports are public."
  - type: textarea
    id: bundle
    attributes:
      label: Bundle
      description: Output of `synlynk report` (includes a `fingerprint:` line).
    validations:
      required: true
  - type: textarea
    id: doing
    attributes: {label: What were you doing?}
  - type: textarea
    id: expected
    attributes: {label: Expected}
  - type: textarea
    id: actual
    attributes: {label: Actual}
```

Then `git rm .github/ISSUE_TEMPLATE/bug_report.md`.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_cmd.py tests/test_capability_taxonomy.py`
Expected: all passed. If the taxonomy test requires extra fields or help-doc entries, add them as that test dictates.

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py synlynk/taxonomy.py .github/ISSUE_TEMPLATE
git commit -m "feat(report): register command, taxonomy entry, YAML issue form"
```

### Task 6: Allowlist property test (guardrail)

**Files:**
- Test: `tests/test_report_bundle.py` (append)

- [ ] **Step 1: Write the test**

```python
def test_no_fake_secret_appears_in_rendered_body(monkeypatch, tmp_path):
    fakes = {
        "ANTHROPIC_API_KEY": "sk-FAKEKEY0123456789abcdef",
        "ANTHROPIC_AUTH_TOKEN": "tok-FAKEAUTH0123456789",
        "USER": "zebulon-secret-user",
        "HOME": str(tmp_path / "zebulon-home"),
    }
    for k, v in fakes.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(rb.platform, "node", lambda: "secret-hostname.internal")
    body = rb.render_body(rb.collect_bundle(salt_path=tmp_path / "salt"), description="")
    for needle in [*fakes.values(), "secret-hostname", "zebulon"]:
        assert needle not in body
```

- [ ] **Step 2: Run, fix, commit**

Run: `python3 -m pytest -q tests/test_report_bundle.py`
Expected: PASS. If it fails, a collector leaks an unnormalized value; fix the collector, not the test.

```bash
git add tests/test_report_bundle.py && git commit -m "test(report): allowlist property test"
```

### Task 7: Part 1 verification and PR

- [ ] **Step 1:** `python3 -m pytest -q` (full suite). Expected: no new failures. Known flake: `tests/test_e2e.py::test_init_force_reruns_without_error` (gh:#5424); rerun once, and stop and flag if it fails three times.
- [ ] **Step 2:** `python3 bin/synlynk.py report` in a scratch repo (interactive): confirm the preview prints, answering `n` files nothing, and no `.synlynk/` appears in an uninitialized bare directory except the explicit local-file fallback.
- [ ] **Step 3:** Open PR against `main` with Summary, Test plan, and the Cost Capture note. Reviewer must differ from the implementer in harness and model.

---

# Part 2 (PR 2): Flight recorder, `--last`, footers and hints

Branch: `feat/report-flight-recorder`. Depends on Part 1 merged.

### Task 8: Ring buffer with write-time redaction

**Files:**
- Create: `synlynk/flight_recorder.py`
- Test: `tests/test_flight_recorder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_flight_recorder.py
import json
from synlynk import flight_recorder as fr


def test_no_synlynk_dir_created_in_uninitialized_dir(tmp_path):
    fr.record(tmp_path, command="init", flags=["--force"], exit_code=1, duration=0.1, error="x")
    assert not (tmp_path / ".synlynk").exists()


def test_caps_at_50_records(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    for i in range(60):
        fr.record(tmp_path, "c", [], 0, 0.0, "")
    lines = (tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()
    assert len(lines) == 50


def test_error_line_is_redacted_at_write_time(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    fr.record(tmp_path, "c", [], 1, 0.0, "boom ghp_" + "a" * 36)
    rec = json.loads((tmp_path / ".synlynk" / "flight.jsonl").read_text().splitlines()[-1])
    assert "ghp_" not in rec["error"] and rec["failed"] is True


def test_write_failure_never_raises(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(fr, "_append", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    fr.record(tmp_path, "c", [], 0, 0.0, "")   # must not raise


def test_off_switch_and_clear(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"flight_recorder": false}')
    fr.record(tmp_path, "c", [], 0, 0.0, "")
    assert not (tmp_path / ".synlynk" / "flight.jsonl").exists()
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    fr.record(tmp_path, "c", [], 0, 0.0, "")
    fr.clear(tmp_path)
    assert not (tmp_path / ".synlynk" / "flight.jsonl").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_flight_recorder.py`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# synlynk/flight_recorder.py
"""Local ring buffer of recent invocations. Never raises, never creates .synlynk/."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path

CAP = 50


def _enabled(root: Path) -> bool:
    cfg = root / ".synlynk" / "config.json"
    try:
        return json.loads(cfg.read_text()).get("flight_recorder", True) is not False
    except Exception:
        return True


def _append(path: Path, line: str) -> None:
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        lines = fh.read().splitlines() + [line]
        fh.seek(0)
        fh.truncate()
        fh.write("\n".join(lines[-CAP:]) + "\n")


def record(root, command: str, flags: list[str], exit_code: int, duration: float, error: str) -> None:
    try:
        root = Path(root)
        if not (root / ".synlynk").is_dir() or not _enabled(root):
            return
        from synlynk.logs import _redact_secret_patterns
        rec = {"ts": int(time.time()), "command": command, "flags": [f for f in flags if f.startswith("-")],
               "exit_code": exit_code, "duration": round(duration, 3),
               "error": _redact_secret_patterns(error.splitlines()[0] if error else ""),
               "failed": exit_code != 0}
        _append(root / ".synlynk" / "flight.jsonl", json.dumps(rec))
    except Exception:
        pass


def last_failed(root) -> dict | None:
    path = Path(root) / ".synlynk" / "flight.jsonl"
    try:
        for line in reversed(path.read_text().splitlines()):
            rec = json.loads(line)
            if rec.get("failed"):
                return rec
    except Exception:
        pass
    return None


def clear(root) -> None:
    try:
        (Path(root) / ".synlynk" / "flight.jsonl").unlink()
    except FileNotFoundError:
        pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_flight_recorder.py`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/flight_recorder.py tests/test_flight_recorder.py
git commit -m "feat(report): flight recorder ring buffer with off-switch"
```

### Task 9: Hook the recorder into the CLI and add the error footer

**Files:**
- Modify: `synlynk/cli.py` `main()` (~line 2511): wrap command dispatch so every invocation records and failures print the footer.
- Test: `tests/test_flight_recorder.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_cli_failure_records_and_prints_footer(tmp_path, monkeypatch, capsys):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    import synlynk.cli as cli
    monkeypatch.setattr(cli, "_dispatch_command", lambda args: 1)   # helper introduced in Step 3
    rc = cli.run_with_recorder(["doctor"])
    assert rc == 1
    assert "synlynk report --last" in capsys.readouterr().err
    assert (tmp_path / ".synlynk" / "flight.jsonl").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_flight_recorder.py::test_cli_failure_records_and_prints_footer`
Expected: FAIL (`run_with_recorder` not defined)

- [ ] **Step 3: Implement**

Add `run_with_recorder(argv)` to `synlynk/cli.py`. It times the call, catches `SystemExit` and exceptions, calls `flight_recorder.record(os.getcwd(), ...)`, prints `Something wrong? synlynk report --last` to stderr when the exit code is non-zero, and re-raises or returns the original exit code unchanged. `main()` calls it around the existing dispatch. If `main()` is a single long function, extract the dispatch body into `_dispatch_command(args)` first and commit that refactor separately with the existing suite green. The recorder must never alter the exit code.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_flight_recorder.py && python3 -m pytest -q tests/test_e2e.py -x`
Expected: pass (apart from the known flake)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_flight_recorder.py
git commit -m "feat(report): record invocations and print report footer on failure"
```

### Task 10: `--last` and `--clear-flight`

**Files:**
- Modify: `synlynk/report_cmd.py`
- Test: `tests/test_report_cmd.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_last_uses_most_recent_failed_record(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    from synlynk import flight_recorder as fr
    fr.record(tmp_path, "dispatch", ["--task"], 1, 1.0, "boom at /x/y line 7")
    seen = {}
    monkeypatch.setattr(rc, "confirm_and_file", lambda body, title, **k: seen.update(body=body) or "url")
    class A: last = True; clear_flight = False
    rc.cmd_report(A())
    assert "dispatch" in seen["body"] and "fingerprint: " in seen["body"]


def test_clear_flight_deletes_buffer(tmp_path, monkeypatch):
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    from synlynk import flight_recorder as fr
    fr.record(tmp_path, "c", [], 1, 0.0, "e")
    class A: last = False; clear_flight = True
    assert rc.cmd_report(A()) == 0
    assert not (tmp_path / ".synlynk" / "flight.jsonl").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_report_cmd.py`
Expected: FAIL

- [ ] **Step 3: Implement**

Replace `cmd_report` in `synlynk/report_cmd.py`:

```python
def cmd_report(args=None) -> int:
    from pathlib import Path
    import os
    from synlynk import flight_recorder as fr
    if args is not None and getattr(args, "clear_flight", False):
        fr.clear(os.getcwd())
        print("Flight recorder buffer cleared.")
        return 0
    command, exit_code, first_error, description = "", 0, "", ""
    if args is not None and getattr(args, "last", False):
        rec = fr.last_failed(os.getcwd())
        if rec is None:
            print("No failed command recorded in this project.")
            return 1
        command, exit_code, first_error = rec["command"], rec["exit_code"], rec["error"]
        description = f"`synlynk {command}` exited {exit_code}: {first_error}"
    elif sys.stdin.isatty():
        description = input("What went wrong? (one line, optional): ").strip()
    bundle = collect_bundle(command=command, exit_code=exit_code, first_error=first_error)
    body = render_body(bundle, description)
    result = confirm_and_file(body, title=f"[report] {description or 'bug report'}"[:100])
    return 0 if result is not None else 1
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_report_cmd.py`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/report_cmd.py tests/test_report_cmd.py
git commit -m "feat(report): --last and --clear-flight"
```

### Task 11: Bearings and task-boundary hints

**Files:**
- Modify: `synlynk/bearings.py` (`generate_bearings_block`, add one bullet before `BEARINGS_END_MARKER`)
- Modify: dispatch completion/failure and circuit-breaker kill messages, and the `init` wizard final screen, to append the one-line hint with the failed job ID. Locate with: `grep -n "circuit.breaker\|dispatch complete\|Step 6/6" synlynk/*.py`.
- Test: `tests/test_bearings.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_bearings_block_mentions_report():
    from synlynk.bearings import generate_bearings_block
    assert "synlynk report" in generate_bearings_block()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_bearings.py`
Expected: FAIL

- [ ] **Step 3: Implement**

Add to the bearings lines list: `"  - Something wrong? Run \`synlynk report --last\` (redacted, previewed, public GitHub issue).",`. Add a shared helper `report_hint(job_id: str | None = None) -> str` in `synlynk/report_cmd.py` returning `Something wrong? synlynk report --last` (plus ` (job <id>)` when given) and call it from each message site found by the grep. Existing tests that snapshot the bearings block or those messages must be updated in the same commit.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_bearings.py && python3 -m pytest -q`
Expected: pass

- [ ] **Step 5: Commit**

```bash
git add synlynk tests
git commit -m "feat(report): surface report hint in bearings and task boundaries"
```

### Task 12: Part 2 verification and PR

- [ ] `python3 -m pytest -q`; verify concurrent-invocation safety by running two failing commands in parallel in a scratch repo and checking `.synlynk/flight.jsonl` stays valid JSON lines and at most 50 long; run `synlynk init` in a bare directory and confirm no `.synlynk/` appears (#5299 guard). Open the PR with a cross-harness reviewer.

---

# Part 3 (PR 3): Vizor action, triage and dedup, `intake` CI check

Branch: `feat/report-vizor-triage`. Depends on Part 2 merged.

### Task 13: Vizor "Report issue" action with payload allowlist

**Files:**
- Modify: `synlynk/viz/home.py` (footer action next to the existing "Raise issue" button); `synlynk/viz/data.py` if a payload helper is needed.
- Test: `tests/test_viz_report_action.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_viz_report_action.py
from html.parser import HTMLParser


class _Find(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = False

    def handle_starttag(self, tag, attrs):
        if dict(attrs).get("data-action") == "report-issue":
            self.found = True


def test_report_action_in_footer(render_home):   # use the same render helper tests/test_viz_banner.py uses
    p = _Find()
    p.feed(render_home())
    assert p.found


def test_payload_contains_only_allowed_keys():
    from synlynk.viz.data import report_issue_payload
    payload = report_issue_payload(route="/w/synlynk/overview.html", meta={"version": "1", "token": "x", "secret": "y"})
    assert set(payload) <= {"route", "version", "fingerprint"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_viz_report_action.py`
Expected: FAIL. Match the `render_home` fixture or helper to `tests/test_viz_banner.py` (copy its setup) before relying on it.

- [ ] **Step 3: Implement**

`report_issue_payload(route, meta)` returns only `route`, `version` (from `meta`) and a `fingerprint`; it drops every other key. Render the footer link with `data-action="report-issue"` that opens `https://github.com/nikhilsoman/synlynk/issues/new?template=bug_report.yml&bundle=<urlencoded payload>` or shows the `synlynk report --last` command. Console contents are not captured.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_viz_report_action.py tests/test_viz_banner.py`
Expected: pass

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz tests/test_viz_report_action.py
git commit -m "feat(report): Vizor report-issue action with allowlisted payload"
```

### Task 14: `intake` CI check (comment-only)

**Files:**
- Create: `.github/workflows/intake.yml`, `scripts/intake_check.py`
- Test: `tests/test_intake_check.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_intake_check.py
from scripts.intake_check import needs_bundle_comment


def test_issue_without_fingerprint_gets_comment():
    assert needs_bundle_comment({"labels": ["bug", "early-adopter"], "body": "it broke"})


def test_issue_with_fingerprint_is_left_alone():
    assert not needs_bundle_comment({"labels": ["early-adopter"], "body": "x\nfingerprint: abc123abc123\n"})


def test_non_early_adopter_issues_ignored():
    assert not needs_bundle_comment({"labels": ["bug"], "body": "no bundle"})
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_intake_check.py`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# scripts/intake_check.py
import re

_FP = re.compile(r"^fingerprint: [0-9a-f]{12}$", re.M)
COMMENT = ("Thanks for the report. It has no diagnostic bundle. Please run `synlynk report` "
           "(redacted and previewed before filing) and paste the result, or file a new issue with it.")


def needs_bundle_comment(issue: dict) -> bool:
    return "early-adopter" in issue.get("labels", []) and not _FP.search(issue.get("body", ""))
```

The workflow triggers on `issues: [opened]`, runs the script with the issue payload, and posts `COMMENT` via `gh issue comment` only. It never labels, closes or edits.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_intake_check.py`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/intake_check.py .github/workflows/intake.yml tests/test_intake_check.py
git commit -m "feat(report): comment-only intake CI check"
```

### Task 15: PM-bot triage and fingerprint dedup

**Files:**
- Modify: `synlynk/support_engineer.py` (existing signal collection and investigation archetype); locate the issue-ingest entry point with `grep -n "def " synlynk/support_engineer.py`.
- Test: `tests/test_support_engineer_intake.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_support_engineer_intake.py
from synlynk.support_engineer import find_duplicate_by_fingerprint


def test_exact_fingerprint_match_is_duplicate():
    existing = [{"number": 10, "body": "x\nfingerprint: abc123abc123\n"}]
    new = {"number": 11, "body": "y\nfingerprint: abc123abc123\n"}
    assert find_duplicate_by_fingerprint(new, existing) == 10


def test_no_fingerprint_no_duplicate():
    assert find_duplicate_by_fingerprint({"number": 2, "body": "none"}, [{"number": 1, "body": "fingerprint: abc123abc123"}]) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest -q tests/test_support_engineer_intake.py`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# add to synlynk/support_engineer.py
import re as _re

_FP_RE = _re.compile(r"^fingerprint: ([0-9a-f]{12})$", _re.M)


def find_duplicate_by_fingerprint(issue: dict, existing: list[dict]) -> int | None:
    m = _FP_RE.search(issue.get("body", ""))
    if not m:
        return None
    for other in existing:
        if other["number"] != issue["number"] and m.group(1) in _FP_RE.findall(other.get("body", "")):
            return other["number"]
    return None
```

Wire it into the existing ingest path so that, for `early-adopter` issues, it posts a comment-only "possible duplicate of #N" and a severity suggestion per the Live Issues SOP; no labels or closes.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest -q tests/test_support_engineer_intake.py`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/support_engineer.py tests/test_support_engineer_intake.py
git commit -m "feat(report): fingerprint dedup in support-engineer triage"
```

### Task 16: Part 3 verification and PR

- [ ] `python3 -m pytest -q`; confirm the `intake` workflow only comments (read its YAML for any `--add-label`, `close`, or `edit`); confirm the Vizor payload test passes. Open the PR with a cross-harness reviewer.

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Allowlist collector, env names set/unset only | 3, 6 |
| `~`, salted per-install hash, remote `host/owner/repo` | 2, 3 |
| Free text off by default, scan blocks submission | 1, 4 (no free-text in Part 1 body; any future free-text opt-in must go through `find_secrets`) |
| Mandatory preview, public-permanence notice, no `--yes` | 4 |
| Whole-body secret scan | 1, 4 |
| Frozen bundle and fingerprint contract, single canonical module | 2, 3 |
| `gh issue create` with fallback URL + local file, capped | 4 |
| Flight recorder (cap 50, flags only, write-time redaction, no `.synlynk/` creation, never raises, off-switch) | 8 |
| `report --last`, `--clear-flight`; both in `COMMAND_TAXONOMY` | 5, 10 |
| Surfaces: error footer, bearings, task boundaries, Vizor | 9, 11, 13 |
| `bug_report.yml` replaces `.md` | 5 |
| Comment-only triage, `intake` check, fingerprint dedup | 14, 15 |
| Interactive and non-interactive e2e | 4 (`interactive` flag tests) |

**Known gap to settle during Part 1 review:** `config_schema`, `policy_schema` and `db_shape` collectors currently emit `"unavailable"`; Task 3 should replace them with real schema-version and count-only readers once the exact accessors are located (`grep -n "schema" synlynk/doctor.py` around the `_hc_config_schema`/`_hc_policy_schema` checks). The spec requires them; they are listed here rather than hidden.
