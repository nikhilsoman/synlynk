import socket

from synlynk.viz import (
    DEFAULT_PORT,
    MEMORABLE_VIZOR_PORTS,
    find_available_vizor_port,
)


def test_memorable_port_list_and_default():
    assert MEMORABLE_VIZOR_PORTS == [33333, 44444, 55555, 22222, 11111]
    assert DEFAULT_PORT == 33333


def test_find_available_vizor_port_default(monkeypatch):
    def mock_bind(self, address):
        return None

    monkeypatch.setattr(socket.socket, "bind", mock_bind)

    assert find_available_vizor_port() == 33333


def test_find_available_vizor_port_uses_next_memorable_port(monkeypatch):
    def mock_bind(self, address):
        if address[1] == 33333:
            raise OSError("Address already in use")

    monkeypatch.setattr(socket.socket, "bind", mock_bind)

    assert find_available_vizor_port() == 44444


def test_find_available_vizor_port_uses_preferred_port_first(monkeypatch):
    probed = []

    def mock_is_available(port):
        probed.append(port)
        return True

    monkeypatch.setattr("synlynk.viz.is_port_available", mock_is_available)

    assert find_available_vizor_port(preferred=12345) == 12345
    assert probed == [12345]


def test_find_available_vizor_port_falls_back_to_legacy_port(monkeypatch):
    monkeypatch.setattr("synlynk.viz.is_port_available", lambda port: False)

    assert find_available_vizor_port() == 8721
