"""Doctor reports the graphify binary without installing it."""

from types import SimpleNamespace

from synlynk import doctor
from synlynk.doctor import HEALTH_CHECKS, _hc_task_leases_integrity, cmd_doctor


def _hc_graphify_dependency():
    fn = getattr(doctor, "_hc_graphify_dependency", None)
    assert fn is not None, "graphify health check is not registered"
    return fn()


def test_graphify_check_is_appended_after_existing_checks():
    names = [fn.__name__ for fn in HEALTH_CHECKS]
    assert names[-1] == "_hc_graphify_dependency"
    assert names.index("_hc_task_leases_integrity") < names.index("_hc_graphify_dependency")
    assert _hc_task_leases_integrity in HEALTH_CHECKS


def test_graphify_check_fails_when_binary_missing(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda name: False)
    called = []
    monkeypatch.setattr(
        "synlynk.tool_installer.install_tool",
        lambda name: called.append(name) or True,
    )
    check = _hc_graphify_dependency()
    assert check.name == "graphify_dependency"
    assert check.status == "fail"
    assert "synlynk doctor --fix graphify" in check.fix
    assert called == []


def test_graphify_check_passes_when_version_exits_zero(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda name: True)

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd == ["graphify", "--version"]
        class Res:
            returncode = 0
            stdout = "graphify 0.4.0\n"
            stderr = ""
        return Res()

    monkeypatch.setattr("synlynk.doctor.subprocess.run", fake_run)
    check = _hc_graphify_dependency()
    assert check.status == "ok"
    assert "0.4.0" in check.message


def test_graphify_check_fails_when_version_exits_nonzero(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda name: True)

    def fake_run(cmd, capture_output, text, timeout):
        class Res:
            returncode = 2
            stdout = ""
            stderr = "boom"
        return Res()

    monkeypatch.setattr("synlynk.doctor.subprocess.run", fake_run)
    check = _hc_graphify_dependency()
    assert check.status == "fail"
    assert "synlynk doctor --fix graphify" in check.fix


def test_plain_doctor_does_not_install_graphify(monkeypatch):
    installed = []
    monkeypatch.setattr(
        "synlynk.tool_installer.install_tool",
        lambda name: installed.append(name) or True,
    )

    def report(checks):
        for fn in checks:
            fn()
        return False

    monkeypatch.setattr("synlynk.doctor._print_health_check_report", report)
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda name: False)
    code = cmd_doctor(
        args=SimpleNamespace(fix=None, version=False, readiness=False, provision=False),
        checks=[_hc_graphify_dependency],
    )
    assert code == 0
    assert installed == []


def test_doctor_fix_graphify_installs_and_rechecks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "synlynk.tool_installer.install_tool",
        lambda name: calls.append(("install", name)) or True,
    )

    def fake_check():
        calls.append(("recheck",))
        from synlynk.doctor import HealthCheck
        return HealthCheck("graphify_dependency", "ok", "graphify 0.4.0")

    monkeypatch.setattr("synlynk.doctor._hc_graphify_dependency", fake_check)
    code = cmd_doctor(args=SimpleNamespace(fix="graphify"))
    assert code == 0
    assert calls == [("install", "graphify"), ("recheck",)]


def test_doctor_fix_graphify_returns_nonzero_when_install_fails(monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.install_tool", lambda name: False)

    def fake_check():
        from synlynk.doctor import HealthCheck
        return HealthCheck("graphify_dependency", "fail", "missing", fix="synlynk doctor --fix graphify")

    monkeypatch.setattr("synlynk.doctor._hc_graphify_dependency", fake_check)
    code = cmd_doctor(args=SimpleNamespace(fix="graphify"))
    assert code == 1
