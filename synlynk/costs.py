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
    __slots__ = ("input_tokens", "output_tokens", "cache_read_tokens", "basis")

    def __init__(self, input_tokens, output_tokens, cache_read_tokens, basis="none"):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens
        self.basis = basis

    def __iter__(self):
        yield self.input_tokens
        yield self.output_tokens

    def __len__(self):
        return 2


def _extract_codex_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses codex exec --json's newline-delimited event stream.

    Returns the cumulative turn_completed usage object, or None on any failure.
    """
    usage = None
    for line in output_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            candidate = event.get("usage")
            if isinstance(candidate, dict):
                usage = candidate
    if usage is None:
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("reasoning_output_tokens", 0))
        cache_read_tokens = int(usage.get("cached_input_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")


def _extract_claude_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses claude -p --output-format stream-json --verbose's event stream.

    Returns the cumulative result-event usage object, or None on any failure.
    cache_creation_input_tokens is folded into input_tokens (both are
    non-cache-read, billable token pools in the CLI's own accounting; the
    rate table has no separate cache-write tier).
    """
    usage = None
    for line in output_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            candidate = event.get("usage")
            if isinstance(candidate, dict):
                usage = candidate
    if usage is None:
        return None
    try:
        in_tokens = int(usage["input_tokens"]) + int(usage.get("cache_creation_input_tokens", 0))
        out_tokens = int(usage["output_tokens"])
        cache_read_tokens = int(usage.get("cache_read_input_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")


def extract_tokens(output_text: str, agent: str = None) -> tuple:
    """Regex-scrapes token counts from AI CLI stdout, or delegates to a
    per-agent structured-output adapter when one exists.

    Returns a pair-compatible object with .cache_read_tokens for cache-aware output.
    """
    if agent == "codex":
        structured = _extract_codex_structured(output_text)
        if structured is not None:
            return structured
    if agent == "claude":
        structured = _extract_claude_structured(output_text)
        if structured is not None:
            return structured

    def _parse_count(value: str) -> int:
        return int(value.replace(",", ""))

    patterns = [
        (r'Input tokens:\s*([\d,]+).*?Output tokens:\s*([\d,]+)', re.DOTALL | re.IGNORECASE),
        (r'"usage"\s*:\s*\{[^}]*"input_tokens"\s*:\s*([\d,]+)[^}]*"output_tokens"\s*:\s*([\d,]+)', re.DOTALL | re.IGNORECASE),
        (r'"input_tokens":\s*([\d,]+).*?"output_tokens":\s*([\d,]+)', re.DOTALL | re.IGNORECASE),
        (r'Tokens used:\s*([\d,]+)\s+input,\s*([\d,]+)\s+output', re.IGNORECASE),
        (r'prompt_tokens:\s*([\d,]+).*?completion_tokens:\s*([\d,]+)', re.DOTALL | re.IGNORECASE),
    ]
    in_tokens = 0
    out_tokens = 0
    basis = "none"
    for pat, flags in patterns:
        m = re.search(pat, output_text, flags)
        if m:
            in_tokens = _parse_count(m.group(1))
            out_tokens = _parse_count(m.group(2))
            basis = "regex_pair"
            break
    if not in_tokens and not out_tokens:
        m = re.search(r'(?:Tokens used|Total tokens)\s*[:\n]\s*([\d,]+)', output_text, re.IGNORECASE)
        if m:
            total = _parse_count(m.group(1))
            in_tokens = int(total * 0.8)
            out_tokens = total - in_tokens
            basis = "total_split"

    cache_read_tokens = 0
    cache_patterns = [
        r'"(?:cached_tokens|cache_read_tokens)"\s*:\s*([\d,]+)',
        r'Cache read tokens:\s*([\d,]+)',
        r'Cached tokens:\s*([\d,]+)',
    ]
    for pat in cache_patterns:
        m = re.search(pat, output_text, re.IGNORECASE)
        if m:
            cache_read_tokens = _parse_count(m.group(1))
            break

    return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, basis)


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
_EXPECTED_RATE_UNIT = "usd_per_1k_tokens"
_HARDCODED_FALLBACK_RATES = {
    "rates_updated_at": None,
    "unit": _EXPECTED_RATE_UNIT,
    "models": {
        "claude-opus-4-8": {"input": 0.015, "output": 0.075, "cache_read": 0.0000015},
        "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gpt-5-codex": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gpt-5.4-mini": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
        "grok-build": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
        "grok-composer-2.5-fast": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    },
    "default": _DEFAULT_MODEL_RATE,
    "billing_mode": {"default": "subscription", "local": "actual"},
}
_RATES_PATH = ".synlynk/model_rates.json"


def _load_model_rates() -> dict:
    """Loads .synlynk/model_rates.json and falls back to hardcoded rates when needed."""
    if not os.path.exists(_RATES_PATH):
        return _HARDCODED_FALLBACK_RATES
    try:
        with open(_RATES_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"WARNING: {_RATES_PATH} is unreadable; falling back to hardcoded default rates")
        return _HARDCODED_FALLBACK_RATES
    if data.get("unit") != _EXPECTED_RATE_UNIT:
        print(
            f"WARNING: {_RATES_PATH} has missing or unexpected 'unit' "
            f"(expected {_EXPECTED_RATE_UNIT!r}, got {data.get('unit')!r}); "
            "falling back to hardcoded default rates to avoid a pricing unit mismatch"
        )
        return _HARDCODED_FALLBACK_RATES
    data.setdefault("default", _DEFAULT_MODEL_RATE)
    data.setdefault("models", {})
    data.setdefault("billing_mode", {"default": "subscription", "local": "actual"})
    return data


def _resolve_billing_mode(agent: str) -> str:
    """Resolves billing mode for an agent; local is always actual."""
    normalized_agent = os.path.basename(agent or "")
    if normalized_agent == "local":
        return "actual"
    rates = _load_model_rates()
    billing_mode = rates.get("billing_mode", {})
    return billing_mode.get(normalized_agent, billing_mode.get("default", "subscription"))


def _model_rate_for_version(model_version, agent=None):
    normalized_agent = os.path.basename(agent or "")
    if normalized_agent == "local":
        return {"input": 0.0, "output": 0.0, "cache_read": 0.0}
    rates = _load_model_rates()
    return rates["models"].get(model_version, rates["default"])


_FIXED_DEFAULT_TOKENS_IN = 5000
_FIXED_DEFAULT_TOKENS_OUT = 2000
_HISTORICAL_AVG_MIN_SAMPLES = 3
_HISTORICAL_AVG_LOOKBACK = 20


def _estimate_tshirt_tokens(story_id: str = None, discipline: str = None, phase: str = None) -> tuple:
    """Fallback chain for estimated_tshirt token counts.

    Returns (in_tokens, out_tokens, estimate_basis).
    Tier 1: story's estimated_tokens column, split evenly in/out.
    Tier 2: historical average from cost_entries actual/estimated_token_rate rows,
            same discipline+phase, with at least 3 samples.
    Tier 3: fixed conservative default.
    """
    conn = _pkg("_get_db")()
    try:
        if story_id:
            row = conn.execute(
                "SELECT estimated_tokens FROM stories WHERE story_id=?",
                (story_id,),
            ).fetchone()
            if row and row[0]:
                total_tokens = int(row[0])
                half = total_tokens // 2
                return half, total_tokens - half, "story_estimate"

        if discipline and phase:
            rows = conn.execute(
                """SELECT cost_entries.input_tokens, cost_entries.output_tokens
                   FROM cost_entries
                   JOIN stories ON cost_entries.story_id = stories.story_id
                   WHERE stories.discipline = ?
                     AND stories.phase = ?
                     AND cost_entries.cost_source IN ('actual', 'estimated_token_rate')
                   ORDER BY cost_entries.id DESC
                   LIMIT ?""",
                (discipline, phase, _HISTORICAL_AVG_LOOKBACK),
            ).fetchall()
            if len(rows) >= _HISTORICAL_AVG_MIN_SAMPLES:
                avg_in = sum((row[0] or 0) for row in rows) // len(rows)
                avg_out = sum((row[1] or 0) for row in rows) // len(rows)
                return avg_in, avg_out, "historical_avg"

        return _FIXED_DEFAULT_TOKENS_IN, _FIXED_DEFAULT_TOKENS_OUT, "fixed_default"
    finally:
        conn.close()


def _resolve_cost_tier(agent: str, basis: str) -> tuple:
    """Maps an extraction basis + billing mode to (cost_source, estimate_basis).

    Returns (None, None) for basis == 'none' - caller must run the t-shirt
    fallback chain (_estimate_tshirt_tokens) instead.
    """
    if basis in ("regex_pair", "structured_output"):
        billing_mode = _resolve_billing_mode(agent)
        if billing_mode == "actual":
            return "actual", None
        return "estimated_token_rate", basis
    if basis == "total_split":
        return "estimated_tshirt", "total_split"
    return None, None


def update_costs(command: str, in_tokens: int, out_tokens: int, duration: float,
                 cache_read_tokens=None, model_version=None, story_id=None,
                 epic_id=None, phase_id=None, agent=None, basis="none",
                 job_id=None, discipline=None, phase=None) -> None:
    """Resolves a provenance tier and writes exactly one cost_entries row via
    the _insert_cost_row chokepoint.

    Never skips a write - a zero-token or unextractable result falls through to
    the estimated_tshirt chain.
    """
    agent_name = agent or (command.split()[0] if command else "")
    if not model_version:
        model_version = extract_model_version("", agent=agent_name) if agent_name else "unknown"

    cost_source, estimate_basis = _resolve_cost_tier(agent_name, basis)
    if cost_source is None:
        if in_tokens > 0 or out_tokens > 0:
            cost_source = "estimated_token_rate"
            estimate_basis = None
        else:
            in_tokens, out_tokens, estimate_basis = _estimate_tshirt_tokens(
                story_id=story_id, discipline=discipline, phase=phase
            )
            cost_source = "estimated_tshirt"

    rates = _model_rate_for_version(model_version, agent=agent_name)
    cache_read_tokens = 0 if cache_read_tokens is None else cache_read_tokens
    est_cost = (
        (in_tokens / 1000 * rates["input"]) +
        (out_tokens / 1000 * rates["output"]) +
        (cache_read_tokens / 1000 * rates["cache_read"])
    )
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    flag = "" if cost_source == "actual" else ("[legacy] " if cost_source == "legacy_unknown" else "[est] ")
    entry = (f"| {ts} | {agent_name} | 1 | {in_tokens}/{out_tokens} "
             f"| {flag}${est_cost:.4f} | exec: {short_cmd} |\n")

    from synlynk.db import _insert_cost_row

    if _pkg("_is_migrated")():
        _insert_cost_row(
            session_date=ts, agent=agent_name, model=model_version,
            input_tokens=in_tokens, output_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
            cost_source=cost_source, estimate_basis=estimate_basis, total_cost_usd=est_cost,
            notes=f"exec: {short_cmd}", story_id=story_id, epic_id=epic_id, phase_id=phase_id,
            job_id=job_id,
        )
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

    conn = _pkg("_get_db")()
    try:
        failed_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_cost_usd), 0) FROM cost_entries "
            "WHERE cost_source = 'estimated_tshirt' AND estimate_basis = 'fixed_default' "
            "AND notes LIKE '%failed job%'"
        ).fetchone()
    finally:
        conn.close()
    failed_count, failed_usd = failed_row
    if failed_count:
        print(
            f"  ℹ️  {failed_count} failed-job placeholder estimates, ${failed_usd:.2f} "
            "(not blended into the spend total above)"
        )


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
            cost_str = parts[5]
            for prefix in ("[est] ", "[legacy] ", "~"):
                if cost_str.startswith(prefix):
                    cost_str = cost_str[len(prefix):]
                    break
            cost_str = cost_str.lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
    return total_usd, total_requests
