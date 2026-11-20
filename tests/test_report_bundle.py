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
