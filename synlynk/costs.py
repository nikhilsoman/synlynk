"""synklynk costs: token extraction, cost estimation, and budget checks."""

import json
import os
import re
import sys
import time

from typing import Optional


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


class _TokenCounts(object):
    __slots__ = ("input_tokens", "output_tokens", "cache_read_tokens")

    def __init__(self, input_tokens, output_tokens, cache_read_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens

    def __iter__(self):
        yield self.input_tokens
        yield self.output_tokens

    def __len__(self):
        return 2


def extract_tokens(output_text: str) -> tuple:
    """Regex-scrapes token counts from AI CLI stdout.

    Returns a pair-compatible object with .cache_read_tokens for cache-aware output.
    """
    patterns = [
        (r'Input tokens:\s*(\d+).*?Output tokens:\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'"usage"\s*:\s*\{[^}]*"input_tokens"\s*:\s*(\d+)[^}]*"output_tokens"\s*:\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'"input_tokens":\s*(\d+).*?"output_tokens":\s*(\d+)', re.DOTALL | re.IGNORECASE),
        (r'Tokens used:\s*(\d+)\s+input,\s*(\d+)\s+output', re.IGNORECASE),
        (r'prompt_tokens:\s*(\d+).*?completion_tokens:\s*(\d+)', re.DOTALL | re.IGNORECASE),
    ]
    in_tokens = 0
    out_tokens = 0
    for pat, flags in patterns:
        m = re.search(pat, output_text, flags)
        if m:
            in_tokens = int(m.group(1))
            out_tokens = int(m.group(2))
            break
    if not in_tokens and not out_tokens:
        m = re.search(r'Total tokens:\s*(\d+)', output_text, re.IGNORECASE)
        if m:
            total = int(m.group(1))
            in_tokens = int(total * 0.8)
            out_tokens = int(total * 0.2)

    cache_read_tokens = 0
    cache_patterns = [
        r'"(?:cached_tokens|cache_read_tokens)"\s*:\s*(\d+)',
        r'Cache read tokens:\s*(\d+)',
        r'Cached tokens:\s*(\d+)',
    ]
    for pat in cache_patterns:
        m = re.search(pat, output_text, re.IGNORECASE)
        if m:
            cache_read_tokens = int(m.group(1))
            break

    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens)


def extract_model_version(output_text: str, agent: str = None) -> str:
    """
    Tier 1: Parse model_version from # synlynk-meta block in agent output.
    Tier 2: read model from the agent profile.
    Tier 3 fallback: read default_model from .synlynk/config.json for the agent.
    Returns 'unknown' if neither source provides a value.
    """
    # Tier 1: structured header
    m = re.search(r"#\s*synlynk-meta.*?model_version\s*=\s*(\S+)", output_text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Tier 2: agent profile override
    if agent:
        profile = _pkg("_load_agent_profile")(agent)
        model = profile.get("model")
        if model and model != "unknown":
            return model

    # Tier 3: config default
    if agent:
        config = _pkg("load_config")()
        agents_cfg = config.get("agents", {})
        default = agents_cfg.get(agent, {}).get("default_model")
        if default:
            return default

    return "unknown"


def extract_verifier_meta(output_text: str) -> Optional[dict]:
    """Parses the # synlynk-meta block from a verifier agent's output.

    Returns dict with quality, correct, rework_needed, verifier_model — or None if absent.
    """
    m = re.search(r"#\s*synlynk-meta\s*\n((?:[^\n]+\n?)+)", output_text, re.IGNORECASE)
    if not m:
        return None
    block = m.group(1)
    meta = {}
    for line in block.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "quality":
                try:
                    meta["quality"] = float(v)
                except ValueError:
                    pass
            elif k == "correct":
                meta["correct"] = v.lower() in ("true", "yes", "1")
            elif k == "rework_needed":
                meta["rework_needed"] = v.lower() in ("true", "yes", "1")
            elif k == "verifier_model":
                meta["verifier_model"] = v
    return meta if "quality" in meta else None


_DEFAULT_MODEL_RATE = {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
_MODEL_RATE_TABLE = {
    "claude-opus-4-8": {"input": 0.015, "output": 0.075, "cache_read": 0.0000015},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5-codex": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gpt-5.4-mini": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
    "grok-build": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    "grok-composer-2.5-fast": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
}


def _model_rate_for_version(model_version, agent=None):
    normalized_agent = os.path.basename(agent or "")
    if normalized_agent == "local":
        return {"input": 0.0, "output": 0.0, "cache_read": 0.0}
    return _MODEL_RATE_TABLE.get(model_version, _DEFAULT_MODEL_RATE)


def update_costs(command: str, in_tokens: int, out_tokens: int, duration: float,
                 cache_read_tokens=None, model_version=None, story_id=None,
                 epic_id=None, phase_id=None, agent=None) -> None:
    """Appends a cost row. Post-migration: writes to state.db + .synlynk/project-docs/costs.md.
    Pre-migration: writes to project-docs/costs.md. Rates are model-aware, with a flat fallback."""
    agent_name = agent or (command.split()[0] if command else "")
    if not model_version:
        model_version = extract_model_version("", agent=agent_name) if agent_name else "unknown"
    rates = _model_rate_for_version(model_version, agent=agent_name)
    cache_read_tokens = 0 if cache_read_tokens is None else cache_read_tokens
    est_cost = (
        (in_tokens / 1000 * rates["input"]) +
        (out_tokens / 1000 * rates["output"]) +
        (cache_read_tokens / 1000 * rates["cache_read"])
    )
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    user = _pkg("get_username")()
    entry = (f"| {ts} | {user} | 1 | {in_tokens}/{out_tokens} "
             f"| ${est_cost:.4f} | exec: {short_cmd} |\n")

    if _pkg("_is_migrated")():
        conn = _pkg("_get_db")()
        try:
            conn.execute(
                """INSERT INTO cost_entries
                   (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                    total_cost_usd, notes, story_id, epic_id, phase_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ts, user, model_version, in_tokens, out_tokens, cache_read_tokens,
                 est_cost, f"exec: {short_cmd}", story_id, epic_id, phase_id)
            )
            conn.commit()
        finally:
            conn.close()
        costs_file = os.path.join(_pkg("_synlynk_project_docs_dir")(), "costs.md")
        os.makedirs(os.path.dirname(costs_file), exist_ok=True)
        with open(costs_file, "a") as f:
            f.write(entry)
        _pkg("_dr_sync")("costs.md")
    else:
        _pkg("_check_upstream_divergence")()
        costs_file = os.path.join(_pkg("_docs_dir")(), "costs.md")
        if not os.path.exists(costs_file):
            return
        with open(costs_file, "a") as f:
            f.write(entry)


def _compute_burn_rate() -> tuple:
    """Returns (avg_usd_per_exec, estimated_execs_remaining) from telemetry.
    Returns (0.0, None) if fewer than 3 costed events."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(telemetry_file):
        return 0.0, None
    try:
        with open(telemetry_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return 0.0, None

    costed = [
        e for e in data
        if e.get("type") == "exec" and e.get("in_tokens", 0) > 0
    ][-10:]

    if len(costed) < 3:
        return 0.0, None

    costs = [
        (e["in_tokens"] / 1000 * 0.003) + (e["out_tokens"] / 1000 * 0.015)
        for e in costed
    ]
    avg = sum(costs) / len(costs)

    total_usd, _ = _pkg("parse_costs_md")()
    config = _pkg("load_config")()
    limit_usd = config["budget"]["limit_usd"]
    remaining_usd = limit_usd - total_usd
    remaining_execs = int(remaining_usd / avg) if avg > 0 else None

    return avg, remaining_execs


def check_budgets() -> None:
    """Warns if cumulative spend from costs.md approaches config limits."""
    config = _pkg("load_config")()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]
    total_usd, _ = _pkg("parse_costs_md")()

    # Request count from telemetry exec events
    total_reqs = 0
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
            total_reqs = sum(1 for e in data if e.get("type") == "exec")
        except (json.JSONDecodeError, IOError):
            pass

    if total_usd >= limit_usd:
        print(f"\n🛑 [Budget Alert] CRITICAL: Spent ${total_usd:.2f} / ${limit_usd:.2f}.")
    elif total_usd >= limit_usd * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of cost budget (${total_usd:.2f} / ${limit_usd:.2f}).")

    if total_reqs >= limit_reqs:
        print(f"\n🛑 [Budget Alert] CRITICAL: {total_reqs} / {limit_reqs} request limit.")
    elif total_reqs >= limit_reqs * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of request limit ({total_reqs} / {limit_reqs}).")


def parse_costs_md() -> tuple:
    """Returns (total_usd, total_requests) by parsing costs.md column 6."""
    costs_file = os.path.join(_pkg("_docs_dir")(), "costs.md")
    total_usd = 0.0
    total_requests = 0
    if not os.path.exists(costs_file):
        return total_usd, total_requests
    with open(costs_file) as f:
        for line in f:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8:
                continue
            cost_str = parts[5].lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
    return total_usd, total_requests
