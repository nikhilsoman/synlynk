"""synklynk costs: token extraction, cost estimation, and budget checks."""

import json
import os
import re
import sys
import time

from dataclasses import dataclass
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


def _extract_agy_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses agy -p --output-format json's single JSON object response.

    Unlike Codex/Claude, agy emits exactly one JSON object per invocation,
    not a newline-delimited event stream, so only the last non-empty line
    needs parsing. thinking_tokens is folded into output_tokens (billable
    output, mirrors Codex's reasoning_output_tokens treatment). No
    cache-read concept exists in agy's usage shape, so cache_read_tokens
    is always 0. A non-"SUCCESS" status is treated as extraction failure
    (falls back to the regex chain) since no failure-mode schema has been
    observed live.
    """
    lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        event = json.loads(lines[-1])
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict) or event.get("status") != "SUCCESS":
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("thinking_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, 0, "structured_output")


def _log_has_permission_denied_signature(output_text: str) -> bool:
    """Detect the headless permission auto-denial signature in agent output."""
    text = output_text or ""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    signature_phrases = (
        "no output produced",
        "permission that headless mode cannot prompt for",
        "auto-denied",
    )
    signature_window = lines[-80:]
    lowered_window = "\n".join(
        line.lower() for line in signature_window if line == line.lstrip()
    )
    if lowered_window and any(phrase in lowered_window for phrase in signature_phrases):
        return True

    # Some logs append a short trailer after the structured result. Scan the
    # tail backwards so the signal stays deterministic when the JSON line is
    # not literally the final non-empty line.
    for line in reversed(signature_window):
        try:
            event = json.loads(line.strip())
        except (ValueError, TypeError):
            continue

        if not isinstance(event, dict) or event.get("status") != "SUCCESS":
            continue
        if event.get("response", None) != "":
            continue
        try:
            num_turns = int(event.get("num_turns", 0))
        except (TypeError, ValueError):
            continue
        if num_turns <= 1:
            return True

    return False


def _extract_grok_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses grok -p --output-format json's single, pretty-printed JSON object.

    Unlike Codex/Claude (newline-delimited event streams) or Agy (single-line
    JSON), grok emits one multi-line pretty-printed JSON object per invocation,
    so the entire captured text is parsed as one document rather than scanned
    line by line. reasoning_tokens is folded into output_tokens (mirrors
    Codex's reasoning_output_tokens and Agy's thinking_tokens treatment).
    cache_read_input_tokens is kept as its own tier rather than folded into
    input_tokens: live testing confirmed total_tokens == input_tokens +
    cache_read_input_tokens + output_tokens across three separate runs, so
    it is a genuine additive pool (like Claude's cache_read_input_tokens),
    not a subset of input_tokens (unlike Codex's cached_input_tokens). A
    failure response (`{"type": "error", ...}`) has no "usage" key, so a
    missing or malformed usage object is the extraction-failure signal —
    there is no explicit status field to check on success.
    """
    try:
        event = json.loads(output_text.strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        in_tokens = int(usage["input_tokens"])
        out_tokens = int(usage["output_tokens"]) + int(usage.get("reasoning_tokens", 0))
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
    if agent == "agy":
        structured = _extract_agy_structured(output_text)
        if structured is not None:
            return structured
    if agent == "grok":
        structured = _extract_grok_structured(output_text)
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
        "gpt-5-codex": {"input": 0.00125, "output": 0.01, "cache_read": 0.000000125},
        "gpt-5.4-mini": {"input": 0.00075, "output": 0.0045, "cache_read": 0.000000075},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01, "cache_read": 0.000125},
        "grok-build": {"input": 0.001, "output": 0.002, "cache_read": 0.0000001},
        "grok-composer-2.5-fast": {"input": 0.002, "output": 0.01, "cache_read": 0.0000002},
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


@dataclass
class PaymentValue:
    api_equivalent_usd: float
    actual_usd: float
    mode: str
    quota_pct_used: Optional[float] = None
    credit_remaining_usd: Optional[float] = None


def _payment_model_config_for_agent(agent: str) -> dict:
    """Return the configured payment model block for an agent."""
    config = _pkg("load_config")() or {}
    payment_models = config.get("payment_models", {})
    if not isinstance(payment_models, dict):
        return {"mode": "pay_as_you_go"}
    agent_cfg = payment_models.get(agent, {})
    return agent_cfg if isinstance(agent_cfg, dict) else {"mode": "pay_as_you_go"}


def _subscription_actual_usd(
    agent: str,
    tokens_in: int,
    tokens_out: int,
    pm_config: dict,
) -> tuple:
    """Return (actual_usd, quota_pct_used) for subscription mode."""
    from synlynk.quota import _upsert_agent_quota

    get_db = _pkg("_get_db")
    conn = get_db()
    try:
        row_in = conn.execute(
            "SELECT used_tokens FROM agent_quotas WHERE agent=? "
            "AND quota_type='monthly' AND unit='tokens' AND model='unknown'",
            (agent,),
        ).fetchone()
        row_out = conn.execute(
            "SELECT used_tokens FROM agent_quotas WHERE agent=? "
            "AND quota_type='monthly' AND unit='tokens' AND model='out'",
            (agent,),
        ).fetchone()
    finally:
        conn.close()

    prior_used_in = int(row_in[0]) if row_in else 0
    prior_used_out = int(row_out[0]) if row_out else 0

    tier_quota_in = int(pm_config.get("tier_quota_tokens_in") or 0)
    tier_quota_out = int(pm_config.get("tier_quota_tokens_out") or 0)
    overage_rate_in = float(pm_config.get("overage_rate_per_1k_in") or 0.0)
    overage_rate_out = float(pm_config.get("overage_rate_per_1k_out") or 0.0)

    cumulative_in = prior_used_in + int(tokens_in or 0)
    cumulative_out = prior_used_out + int(tokens_out or 0)

    prior_over_in = max(0, prior_used_in - tier_quota_in)
    prior_over_out = max(0, prior_used_out - tier_quota_out)
    new_over_in = max(0, cumulative_in - tier_quota_in)
    new_over_out = max(0, cumulative_out - tier_quota_out)
    marginal_over_in = new_over_in - prior_over_in
    marginal_over_out = new_over_out - prior_over_out
    actual_usd = (marginal_over_in / 1000 * overage_rate_in) + (
        marginal_over_out / 1000 * overage_rate_out
    )

    pct_in = (cumulative_in / tier_quota_in) if tier_quota_in else 0.0
    pct_out = (cumulative_out / tier_quota_out) if tier_quota_out else 0.0
    quota_pct_used = min(max(pct_in, pct_out), 1.0)

    conn = get_db()
    try:
        _upsert_agent_quota(
            agent,
            "monthly",
            limit_tokens=tier_quota_in,
            used_tokens=cumulative_in,
            model="unknown",
            unit="tokens",
            conn=conn,
        )
        _upsert_agent_quota(
            agent,
            "monthly",
            limit_tokens=tier_quota_out,
            used_tokens=cumulative_out,
            model="out",
            unit="tokens",
            conn=conn,
        )
        conn.commit()
    finally:
        conn.close()

    return actual_usd, quota_pct_used


def _credit_grant_actual_usd(agent: str, api_equivalent_usd: float) -> tuple:
    """Return (actual_usd, remaining_credit_usd) for credit-grant mode."""
    conn = _pkg("_get_db")()
    try:
        rows = conn.execute(
            "SELECT id, remaining_usd FROM credit_grants "
            "WHERE agent=? AND remaining_usd > 0 "
            "AND (expires_at IS NULL OR expires_at > datetime('now')) "
            "ORDER BY granted_at ASC, id ASC",
            (agent,),
        ).fetchall()
        if not rows:
            return api_equivalent_usd, 0.0

        remaining_cost = float(api_equivalent_usd)
        for row_id, remaining in rows:
            if remaining_cost <= 0:
                break
            remaining = float(remaining)
            consume = min(remaining_cost, remaining)
            new_remaining = remaining - consume
            conn.execute(
                "UPDATE credit_grants SET remaining_usd=? WHERE id=?",
                (new_remaining, row_id),
            )
            remaining_cost -= consume

        conn.commit()
        total_remaining = conn.execute(
            "SELECT COALESCE(SUM(remaining_usd), 0) FROM credit_grants "
            "WHERE agent=? AND remaining_usd > 0 "
            "AND (expires_at IS NULL OR expires_at > datetime('now'))",
            (agent,),
        ).fetchone()[0]
        return remaining_cost, float(total_remaining)
    finally:
        conn.close()


def resolve_payment_value(agent: str, tokens_in: int, tokens_out: int) -> PaymentValue:
    """Resolve API-equivalent and actual payment values for an agent call."""
    pm_config = _payment_model_config_for_agent(agent)
    mode = pm_config.get("mode", "pay_as_you_go")

    model_version = extract_model_version("", agent=agent)
    rates = _model_rate_for_version(model_version, agent=agent)
    api_equivalent_usd = (tokens_in / 1000 * rates["input"]) + (tokens_out / 1000 * rates["output"])

    if mode == "subscription":
        actual_usd, quota_pct_used = _subscription_actual_usd(agent, tokens_in, tokens_out, pm_config)
        return PaymentValue(
            api_equivalent_usd=api_equivalent_usd,
            actual_usd=actual_usd,
            mode=mode,
            quota_pct_used=quota_pct_used,
        )

    if mode == "credit_grant":
        actual_usd, credit_remaining_usd = _credit_grant_actual_usd(agent, api_equivalent_usd)
        return PaymentValue(
            api_equivalent_usd=api_equivalent_usd,
            actual_usd=actual_usd,
            mode=mode,
            credit_remaining_usd=credit_remaining_usd,
        )

    return PaymentValue(
        api_equivalent_usd=api_equivalent_usd,
        actual_usd=api_equivalent_usd,
        mode="pay_as_you_go",
    )


_FIXED_DEFAULT_TOKENS_IN = 5000
_FIXED_DEFAULT_TOKENS_OUT = 2000
_HISTORICAL_AVG_MIN_SAMPLES = 3
_HISTORICAL_AVG_LOOKBACK = 20
_SUSPICIOUS_TOKEN_COUNT_CEILING = 2_000_000


def _is_suspicious_token_count(in_tokens: int, out_tokens: int) -> bool:
    """Returns True when a parsed token count looks implausibly large for one exec."""
    return max(in_tokens or 0, out_tokens or 0) > _SUSPICIOUS_TOKEN_COUNT_CEILING


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

    suspicious_token_count = _is_suspicious_token_count(in_tokens, out_tokens)
    if suspicious_token_count:
        print(
            "WARNING: extracted token count "
            f"{in_tokens:,}/{out_tokens:,} exceeds the "
            f"{_SUSPICIOUS_TOKEN_COUNT_CEILING:,} ceiling; logging as [est?]"
        )
        if cost_source == "actual":
            cost_source = "estimated_token_rate"
            estimate_basis = basis if basis != "none" else "suspicious_token_ceiling"

    rates = _model_rate_for_version(model_version, agent=agent_name)
    cache_read_tokens = 0 if cache_read_tokens is None else cache_read_tokens
    payment_value = resolve_payment_value(agent_name, in_tokens, out_tokens)
    est_cost = payment_value.api_equivalent_usd + (cache_read_tokens / 1000 * rates["cache_read"])
    actual_usd = payment_value.actual_usd + (
        cache_read_tokens / 1000 * rates["cache_read"]
        if payment_value.mode == "pay_as_you_go"
        else 0.0
    )
    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    if suspicious_token_count:
        flag = "[est?] "
    else:
        flag = "" if cost_source == "actual" else ("[legacy] " if cost_source == "legacy_unknown" else "[est] ")
    if payment_value.mode == "subscription":
        mode_tag = "[in-quota]" if actual_usd == 0.0 else "[overage]"
    elif payment_value.mode == "credit_grant":
        mode_tag = "[credit]"
    else:
        mode_tag = ""
    actual_display = f"${actual_usd:.4f} {mode_tag}".strip()
    entry = (f"| {ts} | {agent_name} | 1 | {in_tokens}/{out_tokens} "
             f"| {flag}${est_cost:.4f} | {actual_display} | exec: {short_cmd} |\n")

    from synlynk.db import _insert_cost_row

    if _pkg("_is_migrated")():
        _insert_cost_row(
            session_date=ts, agent=agent_name, model=model_version,
            input_tokens=in_tokens, output_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
            cost_source=cost_source, estimate_basis=estimate_basis, total_cost_usd=est_cost,
            notes=f"exec: {short_cmd}", story_id=story_id, epic_id=epic_id, phase_id=phase_id,
            job_id=job_id,
            api_equivalent_usd=payment_value.api_equivalent_usd,
            actual_usd=actual_usd,
            payment_mode=payment_value.mode,
        )
        _pkg("_generate_costs_md")()
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
    conn = _pkg("_get_db")()
    try:
        total_usd = conn.execute(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries"
        ).fetchone()[0]
    finally:
        conn.close()

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

    conn = _pkg("_get_db")()
    try:
        payment_rows = conn.execute(
            "SELECT agent, payment_mode, actual_usd FROM cost_entries "
            "WHERE payment_mode IS NOT NULL ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if payment_rows:
        seen_agents = {}
        for agent, mode, actual in payment_rows:
            seen_agents[agent] = (mode, actual)

        print("\n  Payment Models")
        for agent, (mode, actual) in seen_agents.items():
            if mode == "subscription":
                conn = _pkg("_get_db")()
                try:
                    row = conn.execute(
                        "SELECT limit_tokens, used_tokens FROM agent_quotas "
                        "WHERE agent=? AND quota_type='monthly' AND unit='tokens' AND model='unknown'",
                        (agent,),
                    ).fetchone()
                finally:
                    conn.close()
                pct = int(100 * row[1] / row[0]) if row and row[0] else 0
                print(f"    {agent:<8}[subscription]  quota: {pct}% used this cycle (${actual:.2f} marginal)")
            elif mode == "credit_grant":
                conn = _pkg("_get_db")()
                try:
                    grant_row = conn.execute(
                        "SELECT remaining_usd, face_value_usd FROM credit_grants "
                        "WHERE agent=? ORDER BY granted_at DESC LIMIT 1",
                        (agent,),
                    ).fetchone()
                finally:
                    conn.close()
                if grant_row:
                    remaining, face_value = grant_row
                    print(f"    {agent:<8}[credit_grant]  balance: ${remaining:.2f} remaining of ${face_value:.2f} granted")
            else:
                print(f"    {agent:<8}[pay_as_you_go] ${actual:.2f} this run")


def parse_costs_md() -> tuple:
    """Returns (total_usd, total_requests) by parsing costs.md's real-dollar column."""
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
            if len(parts) >= 9:
                cost_str = parts[6].split(" ", 1)[0]
            else:
                cost_str = parts[5]
            for prefix in ("[est] ", "[est?] ", "[legacy] ", "~"):
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
