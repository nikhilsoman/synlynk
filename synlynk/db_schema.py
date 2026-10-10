"""SQLite schema DDL for the synlynk state database.

Extracted from synlynk/__init__.py (R12, 2026-09-29) — pure SQL strings,
no logic. Consumed by synlynk/db.py and synlynk/__init__.py's own DB
connection helpers via a re-export in __init__.py.
"""

ONBOARDING_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    session_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    current_stage TEXT NOT NULL DEFAULT 'S1_Orientation',
    topology_status TEXT NOT NULL DEFAULT 'pending',
    topology_candidate TEXT,
    topology_confirmed TEXT,
    harness_probes TEXT,
    dependency_checks TEXT,
    first_win_meta TEXT,
    completed_at TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_onboarding_product ON onboarding_sessions(product_id);
"""

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
    estimated_tokens INTEGER,
    actual_tokens INTEGER,
    engg_domain   TEXT NOT NULL DEFAULT 'backend',
    discipline    TEXT NOT NULL DEFAULT 'backend',
    org_domain    TEXT NOT NULL DEFAULT 'platform',
    role          TEXT NOT NULL DEFAULT 'dev',
    stage         TEXT NOT NULL DEFAULT 'open',
    org_domain_tags TEXT DEFAULT '[]',
    stack_tags    TEXT DEFAULT '[]',
    industry      TEXT DEFAULT 'unknown',
    phase         TEXT DEFAULT 'build',
    legacy_unmapped INTEGER NOT NULL DEFAULT 0,
    priority      INTEGER NOT NULL DEFAULT 5,
    readiness     TEXT NOT NULL DEFAULT 'draft',
    fingerprint   TEXT UNIQUE,
    source_type   TEXT,
    source_ref    TEXT,
    governs_stage TEXT DEFAULT 'open',
    gh_issue      TEXT,
    archived_at   TIMESTAMP,
    superseded_by TEXT DEFAULT NULL,
    repo_id       TEXT,
    type_id       TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backlog_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id             TEXT UNIQUE,
    title               TEXT NOT NULL,
    body                TEXT,
    issue_number        INTEGER,
    gh_issue            TEXT,
    author              TEXT,
    labels              TEXT DEFAULT '[]',
    fingerprint         TEXT UNIQUE,
    role                TEXT NOT NULL DEFAULT 'dev',
    stage               TEXT NOT NULL DEFAULT 'open',
    governs_stage       TEXT NOT NULL DEFAULT 'open',
    complexity_tier     INTEGER DEFAULT 2,
    goal_id             TEXT,
    acceptance_criteria TEXT DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'staged',
    story_id            TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_families (
    family_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    context_geometry TEXT NOT NULL DEFAULT '{}',
    native_features TEXT NOT NULL DEFAULT '[]',
    prompt_adapter TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL REFERENCES model_families(family_id),
    harness_binding TEXT NOT NULL,
    locality TEXT NOT NULL DEFAULT 'remote_api',
    quantization TEXT,
    rates TEXT NOT NULL DEFAULT '{}',
    entitlement_tier TEXT NOT NULL,
    context_geometry TEXT,
    native_features TEXT NOT NULL DEFAULT '[]',
    discovered INTEGER NOT NULL DEFAULT 0,
    discovery_source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_models_family ON models(family_id);
CREATE INDEX IF NOT EXISTS idx_models_harness ON models(harness_binding);

CREATE TABLE IF NOT EXISTS capability_ratings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id              TEXT NOT NULL REFERENCES stories(story_id),
    agent                 TEXT NOT NULL,
    model_version         TEXT NOT NULL DEFAULT 'unknown',
    model_at_dispatch     TEXT,
    model_at_completion   TEXT,
    split_model           INTEGER DEFAULT 0,
    engg_domain           TEXT NOT NULL DEFAULT 'backend',
    discipline            TEXT NOT NULL DEFAULT 'backend',
    org_domain            TEXT NOT NULL DEFAULT 'platform',
    role                  TEXT NOT NULL DEFAULT 'dev',
    stage                 TEXT NOT NULL DEFAULT 'open',
    org_domain_tags       TEXT DEFAULT '[]',
    stack_tags            TEXT DEFAULT '[]',
    industry              TEXT NOT NULL DEFAULT 'unknown',
    phase                 TEXT NOT NULL DEFAULT 'build',
    legacy_unmapped       INTEGER NOT NULL DEFAULT 0,
    signal_source         TEXT NOT NULL DEFAULT 'auto',
    quality               REAL NOT NULL DEFAULT 0.0,
    quality_auto          REAL,
    verifier_agent        TEXT,
    verifier_model        TEXT,
    test_pass_rate        REAL,
    build_success         INTEGER,
    dispatch_rework       INTEGER DEFAULT 0,
    micro_rework          INTEGER DEFAULT 0,
    pr_review_cycles      INTEGER DEFAULT 0,
    duration_vs_estimate  REAL,
    verified_by_ci        INTEGER,
    correct               INTEGER DEFAULT 1,
    note                  TEXT,
    pr_number             INTEGER,
    ed25519_sig           TEXT,
    ts                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pr_multiplier_applied (
    pr_number  INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha    TEXT NOT NULL,
    file        TEXT NOT NULL,
    language    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line        INTEGER,
    scanned_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_symbols_head ON source_symbols(head_sha);
CREATE INDEX IF NOT EXISTS idx_source_symbols_file ON source_symbols(file);

CREATE TABLE IF NOT EXISTS autopilot_runs (
    id            TEXT PRIMARY KEY,
    harness_name    TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    signal_hash   TEXT NOT NULL,
    severity      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    gh_issue_url  TEXT,
    pr_url        TEXT,
    story_id      TEXT,
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_hash ON autopilot_runs(signal_hash, ts);

CREATE TABLE IF NOT EXISTS daemon_jobs (
    job_id       TEXT PRIMARY KEY,
    agent        TEXT NOT NULL,
    harness      TEXT,
    role         TEXT,
    task         TEXT NOT NULL,
    story_id     TEXT,
    type_id      TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    priority     INTEGER NOT NULL DEFAULT 5,
    depends_on   TEXT NOT NULL DEFAULT '[]',
    pid          INTEGER,
    pid_identity TEXT,
    enqueued_at  TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    exit_code    INTEGER,
    log_path     TEXT,
    worktree_path TEXT,
    worktree_branch TEXT,
    terminal_claim_token TEXT,
    handoff_count INTEGER NOT NULL DEFAULT 0,
    previous_agents TEXT,
    dispatch_context TEXT,
    blocked_reason TEXT,
    context_mode TEXT,
    context_bytes INTEGER,
    model_tier TEXT,
    impact_score INTEGER DEFAULT 0,
    requested_model TEXT,
    resolved_model TEXT,
    task_type TEXT,
    task_type_explicit INTEGER,
    purpose TEXT CHECK (purpose IS NULL OR purpose IN ('implementation', 'review', 'other')),
    requested_harness TEXT,
    actual_harness TEXT,
    fallback_reason TEXT,
    session_id TEXT REFERENCES sessions(session_id),
    superseded_by TEXT DEFAULT NULL,
    lineage_root TEXT DEFAULT NULL,
    gh_write_evidence TEXT,
    gh_write_verification_attempts INTEGER NOT NULL DEFAULT 0,
    cost_missing_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_daemon_jobs_status ON daemon_jobs(status);

CREATE TABLE IF NOT EXISTS job_effect_contract (
    contract_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    target TEXT,
    expect TEXT NOT NULL,
    local_change_policy TEXT NOT NULL,
    receipt_policy TEXT NOT NULL,
    verification_deadline_at TEXT,
    contract_version INTEGER NOT NULL,
    started_at TEXT,
    expected_actor TEXT,
    required_predicates_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS job_evidence (
    evidence_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    result TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    confidence TEXT NOT NULL DEFAULT 'medium',
    attempt INTEGER NOT NULL DEFAULT 1,
    event_id TEXT NOT NULL,
    UNIQUE(job_id, source, attempt, event_id)
);
CREATE INDEX IF NOT EXISTS idx_job_evidence_job ON job_evidence(job_id, observed_at);
CREATE TABLE IF NOT EXISTS job_terminal_decision (
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER,
    verification_state TEXT NOT NULL,
    primary_evidence_id TEXT,
    evidence_snapshot_json TEXT NOT NULL DEFAULT '[]',
    decision_reason TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    revision INTEGER NOT NULL,
    contract_version INTEGER NOT NULL,
    follow_up TEXT NOT NULL DEFAULT 'none',
    PRIMARY KEY(job_id, revision),
    UNIQUE(job_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_job_terminal_decision_latest
    ON job_terminal_decision(job_id, revision DESC);
CREATE TABLE IF NOT EXISTS job_terminal_outbox (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    decision_revision INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(job_id, decision_revision)
);
CREATE INDEX IF NOT EXISTS idx_job_terminal_outbox_pending
    ON job_terminal_outbox(created_at);
CREATE TABLE IF NOT EXISTS cost_audit_source_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_kind TEXT NOT NULL,
    source_account TEXT NOT NULL DEFAULT '',
    source_record_id TEXT NOT NULL,
    job_id TEXT,
    decision_revision INTEGER,
    request_id TEXT,
    measure TEXT NOT NULL DEFAULT 'estimated',
    provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    amount_decimal TEXT,
    currency TEXT,
    usage_start TEXT,
    usage_end TEXT,
    confidence TEXT NOT NULL DEFAULT 'medium',
    payload_digest TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    imported_at TEXT NOT NULL,
    UNIQUE(source_kind, source_account, source_record_id)
);
CREATE INDEX IF NOT EXISTS idx_cost_audit_source_job
    ON cost_audit_source_record(job_id, decision_revision);
CREATE INDEX IF NOT EXISTS idx_cost_audit_source_request
    ON cost_audit_source_record(request_id);
CREATE TABLE IF NOT EXISTS cost_audit_source_supersession (
    source_kind TEXT NOT NULL,
    source_account TEXT NOT NULL DEFAULT '',
    superseded_record_id TEXT NOT NULL,
    replacement_record_id TEXT NOT NULL,
    correction_event_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(source_kind, source_account, superseded_record_id),
    UNIQUE(source_kind, source_account, replacement_record_id)
);
CREATE TABLE IF NOT EXISTS cost_audit_event (
    event_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    decision_revision INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    source_kind TEXT,
    source_id TEXT,
    payload_digest TEXT NOT NULL,
    supersedes_event_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cost_audit_event_revision
    ON cost_audit_event(job_id, decision_revision, recorded_at);
CREATE TABLE IF NOT EXISTS cost_audit_link (
    job_id TEXT NOT NULL,
    decision_revision INTEGER NOT NULL,
    state TEXT NOT NULL,
    reason_code TEXT,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    estimated_amount_decimal TEXT,
    billed_amount_decimal TEXT,
    paid_amount_decimal TEXT,
    currency TEXT,
    confidence TEXT NOT NULL DEFAULT 'unknown',
    pricing_basis_json TEXT NOT NULL DEFAULT '{}',
    reconciled_at TEXT NOT NULL,
    latest_event_id TEXT NOT NULL,
    PRIMARY KEY(job_id, decision_revision),
    CHECK(state IN ('linked', 'missing', 'pending', 'conflict'))
);
CREATE TABLE IF NOT EXISTS cost_audit_run (
    run_id TEXT PRIMARY KEY,
    run_kind TEXT NOT NULL,
    source_kind TEXT,
    input_digest TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    outcome TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS job_status_shadow (
    job_id TEXT PRIMARY KEY,
    legacy_status TEXT,
    oracle_status TEXT,
    reason_code TEXT NOT NULL,
    disagreement INTEGER NOT NULL DEFAULT 0,
    harness TEXT,
    effect_kind TEXT,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_status_shadow_reason ON job_status_shadow(reason_code);

CREATE TABLE IF NOT EXISTS job_lifecycle_event (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    harness TEXT NOT NULL,
    role TEXT NOT NULL,
    process_result_json TEXT NOT NULL DEFAULT '{}',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    occurred_at TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    compatibility INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 1,
    rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_lifecycle_job_sequence
    ON job_lifecycle_event(job_id, sequence);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     TEXT NOT NULL UNIQUE,
    product_id  TEXT,
    outcome     TEXT NOT NULL,
    criterion   TEXT NOT NULL,
    deadline    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    kind        TEXT NOT NULL DEFAULT 'feature',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_contributions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id            TEXT NOT NULL REFERENCES goals(goal_id),
    story_id           TEXT NOT NULL REFERENCES stories(story_id),
    resolution_reason  TEXT,
    resolved_at        TIMESTAMP,
    UNIQUE(goal_id, story_id)
);

CREATE TABLE IF NOT EXISTS goal_aliases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id    TEXT NOT NULL REFERENCES goals(goal_id),
    pattern    TEXT NOT NULL,
    product_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(goal_id, pattern)
);
CREATE INDEX IF NOT EXISTS idx_goal_aliases_product ON goal_aliases(product_id);

CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    goal_id          TEXT REFERENCES goals(goal_id),
    status           TEXT NOT NULL DEFAULT 'open',
    disposition      TEXT,
    opened_at        TEXT NOT NULL,
    closed_at        TEXT,
    last_checkpoint_at TEXT,
    closing_summary  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    emitted_by      TEXT NOT NULL,
    parent_event_id INTEGER,
    authority_scope TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, id);

CREATE TABLE IF NOT EXISTS approval_tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL,
    action        TEXT NOT NULL,
    issue_url     TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL DEFAULT 'open',
    opened_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at   TIMESTAMP,
    consumed_at   TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_approval_tickets_story_action ON approval_tickets(story_id, action, status);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    harness_name         TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    UNIQUE(harness_name, event_type)
);

-- Per-harness plan quotas (tokens or requests). quota_type is plan-driven:
-- different harnesses reset on different windows (5h Claude plan, hourly,
-- daily, weekly, monthly). headroom is computed as limit_tokens - used_tokens
-- (columns named *_tokens historically; unit column disambiguates).
CREATE TABLE IF NOT EXISTS harness_quotas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    harness      TEXT NOT NULL,
    track        TEXT NOT NULL DEFAULT 'default',
    model        TEXT NOT NULL DEFAULT 'unknown',
    quota_type   TEXT NOT NULL,
    unit         TEXT NOT NULL DEFAULT 'tokens',
    limit_tokens INTEGER NOT NULL,
    used_tokens  INTEGER NOT NULL DEFAULT 0,
    reset_at     TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(harness, track, model, quota_type, unit)
);
CREATE INDEX IF NOT EXISTS idx_harness_quotas_harness ON harness_quotas(harness);

-- Reservation ledger: an open row represents tokens committed against a
-- harness before real usage lands in harness_quotas via telemetry (#XXX
-- quota-aware dispatch reservation). Released once the matching daemon_jobs
-- row settles (done/failed/timed_out) and real usage has been recorded.
-- Reservations older than 24h are treated as expired at READ time (lazy
-- expiry, see _open_reservations_sum) rather than physically deleted.
CREATE TABLE IF NOT EXISTS harness_reservations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    harness        TEXT NOT NULL,
    tokens         INTEGER NOT NULL,
    scope          TEXT NOT NULL,
    scope_id       TEXT,
    job_id         TEXT,
    status         TEXT NOT NULL DEFAULT 'open',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_harness_reservations_harness ON harness_reservations(harness, status);

CREATE TABLE IF NOT EXISTS credit_grants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent           TEXT NOT NULL,
    face_value_usd  REAL NOT NULL,
    remaining_usd   REAL NOT NULL,
    granted_at      TEXT NOT NULL,
    expires_at      TEXT,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS remediation_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    agent       TEXT NOT NULL,
    target_file TEXT NOT NULL,
    exact_diff  TEXT NOT NULL,
    operator    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_remediation_actions_timestamp
    ON remediation_actions(timestamp);

CREATE TABLE IF NOT EXISTS fleet_matrix_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tier INTEGER NOT NULL,
    home TEXT NOT NULL,
    cell TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fleet_matrix_runs_lookup
    ON fleet_matrix_runs(home, cell, tier, ts);

CREATE TABLE IF NOT EXISTS task_leases (
    lease_id           TEXT PRIMARY KEY,
    story_id           TEXT NOT NULL,
    leased_by          TEXT NOT NULL,
    acquired_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heartbeat_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at         TIMESTAMP NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_task_leases_story ON task_leases(story_id, status);

CREATE TABLE IF NOT EXISTS worktree_leases (
    worktree_id    TEXT PRIMARY KEY,
    job_id         TEXT,
    worktree_path  TEXT NOT NULL,
    leased_by      TEXT NOT NULL,
    pid            INTEGER NOT NULL,
    acquired_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heartbeat_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at     TIMESTAMP NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_worktree_leases_status ON worktree_leases(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_worktree_leases_path ON worktree_leases(worktree_path, status);
"""

_DB_SCORES_VIEW = """
CREATE VIEW IF NOT EXISTS capability_scores AS
SELECT
    agent,
    model_version,
    discipline,
    engg_domain,
    org_domain,
    role,
    stage,
    industry,
    phase,
    SUM(quality * pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
      SUM(pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
      AS weighted_score,
    COUNT(*) AS sample_count,
    MAX(ts) AS last_seen
FROM capability_ratings
WHERE split_model = 0
GROUP BY agent, model_version, discipline, engg_domain, org_domain, role, stage, industry, phase;
"""
