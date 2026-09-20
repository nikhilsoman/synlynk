import json
import os
from unittest.mock import patch, MagicMock

import pytest

from synlynk.attribution import (
    IdentityTriplet,
    resolve_identity_triplet,
    cmd_whoami,
    HARNESS_METADATA,
)


def test_identity_triplet_tag_and_dict():
    triplet = IdentityTriplet(user="nikhilsoman", role="architect", harness="codex", email="nikhilsoman@gmail.com")
    assert triplet.tag == "<@nikhilsoman, architect, codex>"
    
    d = triplet.to_dict()
    assert d["user"] == "nikhilsoman"
    assert d["role"] == "architect"
    assert d["harness"] == "codex"
    assert d["email"] == "nikhilsoman@gmail.com"
    assert d["tag"] == "<@nikhilsoman, architect, codex>"


def test_identity_triplet_commit_trailers():
    triplet_codex = IdentityTriplet(user="nikhil", role="core", harness="codex")
    trailers_codex = triplet_codex.to_commit_trailers()
    assert "Co-Authored-By: Codex <noreply@openai.com>" in trailers_codex
    assert "Attributed-To: @nikhil <core/codex>" in trailers_codex

    triplet_agy = IdentityTriplet(user="@alice", role="dev", harness="agy")
    trailers_agy = triplet_agy.to_commit_trailers()
    assert "Co-Authored-By: AGY <noreply@antigravity.dev>" in trailers_agy
    assert "Attributed-To: @alice <dev/agy>" in trailers_agy

    triplet_claude = IdentityTriplet(user="bob", role="pm", harness="claude")
    trailers_claude = triplet_claude.to_commit_trailers()
    assert "Co-Authored-By: Claude Sonnet <noreply@anthropic.com>" in trailers_claude
    assert "Attributed-To: @bob <pm/claude>" in trailers_claude


def test_identity_triplet_prompt_header():
    triplet = IdentityTriplet(user="nikhilsoman", role="qa", harness="codex")
    header = triplet.to_prompt_header()
    assert "[Session Attribution: <@nikhilsoman, qa, codex>]" in header
    assert "• Operator: @nikhilsoman" in header
    assert "• Role Charter: qa" in header
    assert "• Harness Backend: codex" in header


def test_identity_triplet_from_tag_and_dict():
    parsed1 = IdentityTriplet.from_tag("<@nikhilsoman, architect, codex>")
    assert parsed1 is not None
    assert parsed1.user == "nikhilsoman"
    assert parsed1.role == "architect"
    assert parsed1.harness == "codex"

    parsed2 = IdentityTriplet.from_tag("alice:qa:grok")
    assert parsed2 is not None
    assert parsed2.user == "alice"
    assert parsed2.role == "qa"
    assert parsed2.harness == "grok"

    parsed3 = IdentityTriplet.from_dict({
        "user": "bob",
        "role": "pm",
        "harness": "claude",
        "email": "bob@example.com",
    })
    assert parsed3 is not None
    assert parsed3.user == "bob"
    assert parsed3.email == "bob@example.com"


def test_identity_triplet_validation():
    valid = IdentityTriplet(user="nikhil", role="dev", harness="agy")
    ok, errors = valid.validate()
    assert ok is True
    assert len(errors) == 0

    invalid = IdentityTriplet(user="", role="invalid_super_role", harness="unknown_ai")
    ok_inv, errors_inv = invalid.validate()
    assert ok_inv is False
    assert len(errors_inv) >= 2


def test_resolve_identity_triplet_env_and_args():
    # Direct arguments
    triplet = resolve_identity_triplet(user="custom_user", role="qa", harness="grok")
    assert triplet.user == "custom_user"
    assert triplet.role == "qa"
    assert triplet.harness == "grok"

    # Environment override
    with patch.dict(os.environ, {"SYNLYNK_IDENTITY_TRIPLET": "<@envuser, architect, codex>"}):
        triplet_env = resolve_identity_triplet()
        assert triplet_env.user == "envuser"
        assert triplet_env.role == "architect"
        assert triplet_env.harness == "codex"


def test_cmd_whoami_json_output(capsys):
    args = MagicMock()
    args.user = "tester"
    args.role = "qa"
    args.harness = "codex"
    args.json = True

    ret = cmd_whoami(args)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["user"] == "tester"
    assert data["role"] == "qa"
    assert data["harness"] == "codex"
    assert data["valid"] is True
    assert len(data["trailers"]) == 2
