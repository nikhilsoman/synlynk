import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

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


def test_remote_withholds_local_paths_queries_and_ambiguous_values():
    assert rb.normalize_remote("file:///Users/alice/private/repo") == "none"
    assert (
        rb.normalize_remote("https://tok@github.com/o/r.git?access_token=secret#x")
        == "github.com/o/r"
    )
    assert rb.normalize_remote("/Users/alice/private/repo") == "none"
    assert rb.normalize_remote("C:/Users/alice/private/repo") == "none"
    assert rb.normalize_remote("host:/home/alice/private/repo") == "none"
    assert rb.normalize_remote("https://[malformed/repo") == "none"


def test_fingerprint_ignores_variable_parts():
    f1 = rb.fingerprint(
        ["doctor.cfg"], "init", 1, "error at /tmp/a1b2c3d4e5f6/x line 42"
    )
    f2 = rb.fingerprint(
        ["doctor.cfg"], "init", 1, "error at /tmp/ffeeddccbbaa/x line 99"
    )
    assert f1 == f2 and len(f1) == 12


def test_fingerprint_sorts_check_ids():
    assert rb.fingerprint(["b", "a"], "x", 1, "e") == rb.fingerprint(
        ["a", "b"], "x", 1, "e"
    )


def test_collect_emits_only_allowlisted_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-CANARY1234567890abcdef")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://tok:pw@gw.example.com")
    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")
    assert set(bundle) <= set(rb.ALLOWED_FIELDS)
    assert bundle["env_set"]["ANTHROPIC_API_KEY"] is True
    body = rb.render_body(bundle, description="")
    assert "CANARY" not in body and "gw.example.com" not in body


def test_env_set_uses_name_membership_even_for_empty_value(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")

    assert bundle["env_set"]["ANTHROPIC_API_KEY"] is True


def test_harness_collection_uses_configured_cli(monkeypatch):
    looked_up = []

    def which(executable):
        looked_up.append(executable)
        return f"/bin/{executable}"

    monkeypatch.setattr(rb.shutil, "which", which)
    rows = rb._collect_harnesses()

    assert "aider" in looked_up
    assert "synlynk" in looked_up
    assert all(row["version"] == "unavailable" for row in rows)


def test_collector_failure_yields_unavailable(monkeypatch, tmp_path):
    def fail_doctor():
        raise RuntimeError("x")

    monkeypatch.setattr(rb, "_collect_doctor", fail_doctor)
    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")
    assert bundle["doctor"] == "unavailable"


def test_salt_write_failure_withholds_identity(monkeypatch, tmp_path):
    def fail_salt(path):
        raise PermissionError("read-only home")

    monkeypatch.setattr(rb, "_salt", fail_salt)

    bundle = rb.collect_bundle(salt_path=tmp_path / "salt")

    assert bundle["identity"] == "unavailable"


def test_concurrent_salt_creation_is_stable_and_owner_only(tmp_path):
    salt_path = tmp_path / "install" / "report_salt"
    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = list(pool.map(lambda _: rb.salted_hash("alice", salt_path), range(20)))

    assert len(set(hashes)) == 1
    assert len(salt_path.read_bytes()) == 16
    assert salt_path.stat().st_mode & 0o777 == 0o600


def test_render_contains_fingerprint_line_and_description(tmp_path):
    body = rb.render_body(
        rb.collect_bundle(salt_path=tmp_path / "s"), description="init fails"
    )
    assert any(line.startswith("fingerprint: ") for line in body.splitlines())
    assert "init fails" in body


def test_joint_leak_is_flagged_by_whole_body_scan():
    from synlynk.report_scan import find_secrets

    body = "remote: github.com/acme/private-repo\npassword=hunter2hunter2"
    assert find_secrets(body)


def test_schema_collectors_return_versions_only(monkeypatch, tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "workspace.json").write_text(
        json.dumps({"schema_version": 7, "secret": "do-not-collect"})
    )
    (synlynk_dir / "billing.json").write_text(json.dumps({"schema_version": 3}))
    (synlynk_dir / "policy.json").write_text(
        json.dumps({"schema_version": 5, "token": "do-not-collect"})
    )

    assert rb._collect_config_schema(tmp_path) == {"billing": 3, "workspace": 7}
    assert rb._collect_policy_schema(tmp_path) == 5


def test_db_shape_contains_counts_but_no_row_content(tmp_path):
    db_path = tmp_path / "state.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 9")
        conn.execute("CREATE TABLE stories (id INTEGER, title TEXT)")
        conn.executemany(
            "INSERT INTO stories VALUES (?, ?)",
            [(1, "secret first title"), (2, "secret second title")],
        )

    shape = rb._collect_db_shape(db_path)

    assert shape == {"user_version": 9, "table_count": 1, "row_count": 2}
    assert "secret" not in repr(shape)


def test_db_shape_handles_uri_delimiters_in_filename(tmp_path):
    db_path = tmp_path / "state?#.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE stories (id INTEGER)")
        conn.execute("INSERT INTO stories VALUES (1)")

    assert rb._collect_db_shape(db_path)["row_count"] == 1


def test_no_fake_secret_appears_in_rendered_body(monkeypatch, tmp_path):
    fakes = {
        "ANTHROPIC_API_KEY": "sk-FAKEKEY0123456789abcdef",
        "ANTHROPIC_AUTH_TOKEN": "tok-FAKEAUTH0123456789",
        "USER": "zebulon-secret-user",
        "HOME": str(tmp_path / "zebulon-home"),
    }
    for key, value in fakes.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(rb.platform, "node", lambda: "secret-hostname.internal")
    body = rb.render_body(
        rb.collect_bundle(salt_path=tmp_path / "salt"), description=""
    )
    for needle in [*fakes.values(), "secret-hostname", "zebulon"]:
        assert needle not in body


def test_collect_bundle_does_not_initialize_bare_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    rb.collect_bundle(salt_path=tmp_path / "outside-local-synlynk-salt")

    assert not (tmp_path / ".synlynk").exists()


def test_doctor_collection_does_not_run_mutating_or_network_checks(monkeypatch):
    import synlynk.doctor as doctor

    forbidden = {"_hc_model_registry", "_hc_identity_roles", "_hc_version_current"}
    called = []

    def fake_check(name):
        def check():
            called.append(name)
            raise AssertionError(name)

        check.__name__ = name
        return check

    monkeypatch.setattr(
        doctor,
        "HEALTH_CHECKS",
        [fake_check(name) for name in sorted(forbidden)],
    )

    rows = rb._collect_doctor()

    assert called == []
    assert all(row["status"] == "unavailable" for row in rows)
