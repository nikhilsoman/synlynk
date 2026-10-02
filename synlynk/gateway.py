"""Registry-driven connectivity probes for external model gateways.

Gateway dispatch is intentionally out of scope for this preview.  The probe
only validates that a configured provider can be reached and reports a small
model roster when the provider exposes one.
"""

import json
import os
import urllib.error
import urllib.request


def _read_gateway_config(config_path: str) -> dict:
    """Return the ``gateways`` mapping from a registry file.

    Missing, malformed, or unreadable registries are treated as having no
    configured gateways so the command remains safe to run in any checkout.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as registry_file:
            payload = json.load(registry_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    gateways = payload.get("gateways", {})
    return gateways if isinstance(gateways, dict) else {}


def _probe_gateway(name: str, cfg: dict) -> int:
    """Probe one gateway, returning zero on success and one on failure."""
    if not cfg.get("enabled", False):
        print(f"  - {name}: disabled (skipped)")
        return 0

    api_key_env = cfg.get("api_key_env", "")
    api_key = os.environ.get(api_key_env) if api_key_env else None
    if not api_key:
        print(f"  ✗ {name}: {api_key_env} not set in environment")
        return 1

    base_url = cfg.get("base_url")
    if not base_url:
        print(f"  ✗ {name}: base_url is not configured")
        return 1

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        print(f"  ✗ {name}: unreachable — {exc}")
        return 1

    models = payload.get("data", []) if isinstance(payload, dict) else []
    model_ids = [model.get("id", "?") for model in models[:5]]
    print(f"  ✓ {name}: reachable ({len(models)} models available)")
    if model_ids:
        print(f"    top models: {', '.join(model_ids)}")
    if not cfg.get("dispatch_active", False):
        print(f"  ⚠ {name}: dispatch integration not yet active (ships in v0.26.0)")
    return 0


def cmd_gateway_probe(gateway: str = None, config_path: str = ".synlynk/registry.json") -> int:
    """Probe one named gateway or every configured gateway."""
    gateways = _read_gateway_config(config_path)
    if not gateways:
        print("  No gateways configured in registry.json")
        return 0

    if gateway is not None and gateway not in gateways:
        print(f"  ✗ Unknown gateway: {gateway!r}. Available: {list(gateways)}")
        return 1

    targets = {gateway: gateways[gateway]} if gateway else gateways
    exit_code = 0
    for name, cfg in targets.items():
        result = _probe_gateway(name, cfg)
        if result != 0:
            exit_code = result
    return exit_code
