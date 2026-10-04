"""Memorable local ports for the Vizor HTTP listener."""
import socket
from typing import Optional
from synlynk.viz.constants import MEMORABLE_VIZOR_PORTS
def _pkg():
    """Package namespace tests and the Vizor daemon rebind."""
    import synlynk.viz as viz
    return viz

def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return whether Vizor can bind its local HTTP listener to ``port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def find_available_vizor_port(preferred: Optional[int] = None) -> int:
    """Choose a memorable free port, falling back to the legacy port."""
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(MEMORABLE_VIZOR_PORTS)
    for port in candidates:
        if _pkg().is_port_available(port):
            return port
    return 8721

