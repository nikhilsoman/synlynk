"""Seeds a starter capability_ratings bucket for a newly activated role,
per spec §3a.2 ('every activated role gets a capability_ratings task-type
bucket at activation, not after the fact'). Mirrors local_agent_seed.py's
pattern: one synthetic calibration story + one capability_ratings row per
starter coordinate, idempotent, signal_source='seed'.
"""

MODEL_VERSION = "role-activation-seed-1.0"

# (discipline, org_domain, stage, engg_domain, industry, phase, estimated_tokens)
# per role — a narrow starter envelope matching each role's §2 mandate, not
# a claim of measured capability. Real job completions widen it over time
# via the normal capability-rating write path, same as local_agent_seed.py.
ROLE_STARTER_COORDINATES = {
    "secops": [
        ("security", "platform", "execute", "security", "unknown", "build", 1000),
    ],
    "infra-devops": [
        ("infra", "platform", "execute", "infra", "unknown", "build", 1200),
    ],
    "maintainer": [
        ("platform", "platform", "execute", "platform", "unknown", "build", 600),
    ],
}

SEED_QUALITY = 0.6


def seed_role_capability_envelope(conn, role: str) -> None:
    """Idempotently seed capability_ratings for `role`. No-op if role is unknown."""
    coordinates = ROLE_STARTER_COORDINATES.get(role)
    if not coordinates:
        return
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for i, (discipline, org_domain, stage, engg_domain, industry, phase,
                est_tokens) in enumerate(coordinates):
            story_id = f"{role}-activation-seed-{i:02d}"
            conn.execute(
                "INSERT OR IGNORE INTO stories "
                "(story_id, engg_domain, org_domain, industry, phase, estimated_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (story_id, engg_domain, org_domain, industry, phase, est_tokens),
            )
            conn.execute(
                "INSERT INTO capability_ratings (story_id, agent, model_version, "
                "split_model, engg_domain, discipline, org_domain, role, stage, "
                "industry, phase, signal_source, quality) "
                "SELECT ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, 'seed', ? "
                "WHERE NOT EXISTS (SELECT 1 FROM capability_ratings "
                "WHERE story_id=? AND agent=? AND signal_source='seed')",
                (story_id, role, MODEL_VERSION, engg_domain, discipline, org_domain,
                 role, stage, industry, phase, SEED_QUALITY, story_id, role),
            )
        if owns_transaction:
            conn.commit()
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
