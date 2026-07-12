"""Seeds a conservative starter capability envelope for the 'local' agent.

capability_scores (synlynk/__init__.py's _DB_SCORES_VIEW) is a VIEW computed
from capability_ratings — there's no table to seed directly. To make the
existing _best_agent_for_story() router surface 'local' for a narrow set of
granular task coordinates (and stay cold/absent everywhere else), this inserts
one synthetic calibration story + capability_ratings row per starter
coordinate. Real job completions layer on top via the normal
_write_capability_rating() path — the envelope widens itself with no
local-specific code."""

MODEL_VERSION = "ornith-1.0-9b"

# (discipline, org_domain, role, stage, engg_domain, industry, phase, estimated_tokens)
STARTER_WHITELIST = [
    ("docs", "content", "dev", "execute", "docs", "unknown", "build", 800),
    ("testing", "platform", "dev", "execute", "testing", "unknown", "build", 1200),
]

# Moderate, not maxed — proves capability without out-competing paid agents
# on tasks it hasn't actually done yet.
SEED_QUALITY = 0.6


def seed_local_capability_envelope(conn) -> None:
    """Idempotent: re-running does not duplicate rows (checks by story_id)."""
    for i, (discipline, org_domain, role, stage, engg_domain, industry, phase,
            est_tokens) in enumerate(STARTER_WHITELIST):
        story_id = f"local-seed-{i:02d}"
        exists = conn.execute(
            "SELECT 1 FROM stories WHERE story_id=?", (story_id,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO stories (story_id, engg_domain, org_domain, industry, "
            "phase, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?)",
            (story_id, engg_domain, org_domain, industry, phase, est_tokens),
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, "
            "split_model, engg_domain, discipline, org_domain, role, stage, "
            "industry, phase, signal_source, quality) VALUES "
            "(?, 'local', ?, 0, ?, ?, ?, ?, ?, ?, ?, 'seed', ?)",
            (story_id, MODEL_VERSION, engg_domain, discipline, org_domain, role,
             stage, industry, phase, SEED_QUALITY),
        )
    conn.commit()
