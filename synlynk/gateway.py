"""Registry-driven OpenRouter dispatch and connectivity probes."""

import json
import os
import urllib.error
import urllib.request


GATEWAY_TIMEOUT_SECONDS = 30


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
        print(f"  ⚠ {name}: dispatch integration not yet active (enable with 'synlynk configure openrouter')")
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


def dispatch_openrouter(
    model: str,
    messages: list,
    config_path: str = ".synlynk/registry.json",
    timeout: int = GATEWAY_TIMEOUT_SECONDS,
) -> dict:
    """Send a chat completion through OpenRouter, trying configured models in order.

    The requested model is always attempted first. Distinct IDs in the gateway
    ``models`` list follow it and act as the fallback chain.
    """
    gateways = _read_gateway_config(config_path)
    cfg = gateways.get("openrouter", {})
    if not cfg.get("enabled", False):
        raise RuntimeError("OpenRouter gateway is disabled")
    if not cfg.get("dispatch_active", False):
        raise RuntimeError("OpenRouter dispatch is not active; use 'synlynk gateway probe' to check connectivity")

    api_key_env = cfg.get("api_key_env", "")
    api_key = os.environ.get(api_key_env) if api_key_env else None
    if not api_key:
        raise RuntimeError(f"{api_key_env or 'OpenRouter API key'} not set in environment")
    base_url = cfg.get("base_url")
    if not base_url:
        raise RuntimeError("OpenRouter base_url is not configured")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty JSON array")

    models = [model]
    for fallback in cfg.get("models", []):
        if isinstance(fallback, str) and fallback and fallback not in models:
            models.append(fallback)

    errors = []
    for candidate in models:
        payload = json.dumps({"model": candidate, "messages": messages}).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://synlynk.com",
                "X-Title": "synlynk",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("OpenRouter returned a non-object response")
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            errors.append(f"{candidate}: {exc}")

    raise RuntimeError("OpenRouter dispatch failed for all configured models: " + "; ".join(errors))


def cmd_gateway_dispatch(
    model: str,
    prompt: str,
    config_path: str = ".synlynk/registry.json",
) -> int:
    """Dispatch a user prompt to OpenRouter and print the JSON response."""
    try:
        response = dispatch_openrouter(
            model,
            [{"role": "user", "content": prompt}],
            config_path=config_path,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"  ✗ openrouter: {exc}")
        return 1
    print(json.dumps(response, indent=2))
    return 0


def cmd_configure_openrouter(
    key: str = None,
    models: str = None,
    base_url: str = None,
    disable: bool = False,
    probe: bool = False,
    config_path: str = ".synlynk/registry.json",
) -> int:
    """Configure OpenRouter BYOK model gateway settings."""
    from synlynk.registry import configure_openrouter

    parsed_models = None
    if isinstance(models, str) and models.strip():
        parsed_models = [m.strip() for m in models.split(",") if m.strip()]

    if key:
        os.environ["OPENROUTER_API_KEY"] = key
        env_path = ".env"
        if os.path.exists(env_path):
            try:
                lines = []
                replaced = False
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("OPENROUTER_API_KEY="):
                            lines.append(f"OPENROUTER_API_KEY={key}\n")
                            replaced = True
                        else:
                            lines.append(line)
                if not replaced:
                    lines.append(f"OPENROUTER_API_KEY={key}\n")
                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            except OSError:
                pass

    registry = configure_openrouter(
        api_key=key,
        models=parsed_models,
        base_url=base_url,
        disable=disable,
        config_path=config_path,
    )

    cfg = registry.get("gateways", {}).get("openrouter", {})
    enabled = cfg.get("enabled", False)
    dispatch_active = cfg.get("dispatch_active", False)
    active_models = cfg.get("models", [])
    active_base_url = cfg.get("base_url", "https://openrouter.ai/api/v1")
    api_key_env = cfg.get("api_key_env", "OPENROUTER_API_KEY")
    has_key = bool(os.environ.get(api_key_env))

    status_str = "enabled, dispatch active" if (enabled and dispatch_active) else ("disabled" if not enabled else "enabled (dispatch inactive)")
    print(f"  ✓ OpenRouter gateway configured ({config_path})")
    print(f"    Status: {status_str}")
    print(f"    Base URL: {active_base_url}")
    print(f"    Models: {', '.join(active_models) if active_models else 'none'}")
    print(f"    Key ({api_key_env}): {'set' if has_key else 'not set in environment'}")

    if probe:
        print("\n  Probing gateway connectivity...")
        return cmd_gateway_probe(gateway="openrouter", config_path=config_path)
    return 0
