import json
import sqlite3

from synlynk.policy import check_authority, load_policy
from synlynk.product_store import state_db_path


def _repo(tmp_path, slug="hitchcock"):
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": slug}))
    return repo


def test_product_db_schema_has_repo_and_type_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    import synlynk

    conn = synlynk._get_db(str(tmp_path / "legacy.db"))
    assert "repo_id" in {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "type_id" in {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "type_id" in {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    conn.close()
    assert state_db_path("hitchcock") != tmp_path / "legacy.db"


def test_product_policy_wins_and_resolves_canonical_qa(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    policy_path = state_db_path("hitchcock").parent / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps({
        "schema_version": 1,
        "defaults": {"merge_authority": {"can_merge": ["qa"]}},
    }))
    types_path = policy_path.parent / "types.yaml"
    types_path.write_text(json.dumps({"types": {
        "director": {"kind": "pm", "canonical": True},
        "qa": {"kind": "qa", "canonical": True},
    }}))
    (repo / ".synlynk" / "policy.json").write_text(json.dumps({
        "overrides": {"merge_authority": {"can_merge": ["architect"]}}
    }))
    policy = load_policy(str(repo))
    assert policy["merge_authority"]["can_merge"] == ["qa"]
    assert check_authority("merge", "director", str(repo)).allowed is False
    assert check_authority("merge", "qa", str(repo)).allowed is True


def test_unknown_merge_type_keeps_legacy_string_matching(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    product_policy = state_db_path("hitchcock").parent / "policy.json"
    product_policy.parent.mkdir(parents=True, exist_ok=True)
    product_policy.write_text(json.dumps({"defaults": {"merge_authority": {"can_merge": ["qa"]}}}))
    assert check_authority("merge", "qa", str(repo)).allowed is True
