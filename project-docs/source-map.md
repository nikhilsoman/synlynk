# Source Map
_Generated: 2026-09-25T00:02:59 · HEAD: 936689c · 408 files_

## [root]/  [python · 1, shell · 1]
`conftest.py` · 3 symbols
  ensure_curses_initialized() [function:6], pytest_sessionstart() [function:15], pytest_sessionfinish() [function:19]

`install.sh` · 0 symbols

## bin/  [python · 4]
`bin/attest_capability.py` · 2 symbols
  DB_PATH [constant:23], main() [function:146]

`bin/backfill_api_equivalent_usd.py` · 5 symbols
  ROOT [constant:21], _BACKFILL_SQL [constant:28], _compute_api_equivalent_usd() [function:46], backfill_api_equivalent_usd() [function:55], main() [function:88]

`bin/backfill_capability.py` · 12 symbols
  DB_PATH [constant:29], _TITLE_PREFIX_DOMAIN [constant:35], _FILE_DOMAIN_RULES [constant:41], infer_engg_domain() [function:48], infer_phase() [function:63], count_review_cycles() [function:70], get_db() [function:79], story_exists() [function:89], insert_story() [function:94], insert_rating() [function:103], fetch_prs() [function:121], main() [function:133]

`bin/synlynk.py` · 0 symbols

## docs/archive/1203-backlog-automation-codex-alt/  [python · 3]
`docs/archive/1203-backlog-automation-codex-alt/__init__.py` · 0 symbols

`docs/archive/1203-backlog-automation-codex-alt/backlog_automation.py` · 11 symbols
  compute_signal_hash() [function:11], has_ledger_duplicate() [function:17], record_proposal() [function:25], search_similar_issues() [function:37], resolve_goal() [function:55], _repo_slug() [function:79], _create_github_issue() [function:87], file_backlog_item() [function:122], collect_session_material() [function:163], cmd_backlog_note() [function:196], cmd_backlog_scan_session() [function:222]

`docs/archive/1203-backlog-automation-codex-alt/test_backlog_automation.py` · 16 symbols
  db_conn() [function:8], test_backlog_proposals_table_exists() [function:17], test_compute_signal_hash_is_stable_and_source_sensitive() [function:29], test_has_ledger_duplicate_true_after_insert() [function:38], test_search_similar_issues_parses_gh_output() [function:50], test_search_similar_issues_empty_on_gh_failure() [function:60], test_resolve_goal_uses_explicit_goal_id() [function:67], test_resolve_goal_creates_new_goal_when_requested() [function:76], test_resolve_goal_returns_none_when_nothing_given() [function:87], test_file_backlog_item_happy_path() [function:94], test_file_backlog_item_skips_ledger_duplicate() [function:127], test_file_backlog_item_skips_gh_title_duplicate() [function:139], test_collect_session_material_reads_closing_summary() [function:155], test_collect_session_material_missing_session() [function:168], test_cli_backlog_note_invokes_file_backlog_item() [function:174], test_cli_backlog_scan_session_prints_material() [function:189]

## scripts/  [python · 3, shell · 1]
`scripts/apply_qa_gate_branch_protection.sh` · 0 symbols

`scripts/convert_roadmap_table.py` · 4 symbols
  _strip_markdown_formatting() [function:9], _parse_roadmap_version_arc_table() [function:13], _read_roadmap() [function:62], main() [function:66]

`scripts/generate_command_docs.py` · 6 symbols
  TIER_LABELS [constant:14], README_START [constant:22], README_END [constant:23], render_reference_doc() [function:26], render_readme_section() [function:51], main() [function:65]

`scripts/local_agent_ab_test.py` · 11 symbols
  _CONFIG_PATH [constant:22], _RESULTS_PATH [constant:23], _build_temp_config() [function:28], _load_config() [function:44], _write_config() [function:49], _git_diff_stat() [function:55], _build_result_row() [function:62], _default_dispatch_runner() [function:76], run_ab_case() [function:84], append_result() [function:112], main() [function:120]

## synlynk/  [python · 127]
`synlynk/__init__.py` · 13 symbols
  _IS_TESTING [constant:31], _FAST_CLI [constant:32], _LEGACY_MODULES [constant:38], _load_legacy_imports() [function:47], main() [function:79], CYCLE_COLORS [constant:83], CYCLE_DESCRIPTIONS [constant:92], CYCLE_DEFAULT_AGENTS [constant:101], CORE_TEMPLATE_IDS [constant:110], _CAPABILITY_COST_TIE_GAP [constant:113], _launch_visible_template_ids() [function:115], _launch_visible_templates() [function:124], LAUNCH_TASK_TEMPLATES [constant:129]

`synlynk/__main__.py` · 0 symbols

`synlynk/_constants.py` · 16 symbols
  VERSION [constant:3], _INSTALL_SCRIPT_URL [constant:7], QUOTA_PATTERNS [constant:11], HARNESS_TIMEOUT_PATTERNS [constant:17], _ROLE_PERMISSION_DEFAULTS [constant:21], _PERMISSION_TO_TOOL_MAP [constant:36], _CODEX_NETWORK_PERMISSION [constant:45], HARNESS_CAPABILITY_BASELINES [constant:50], CORE_FLEET [constant:289], EXPERIMENTAL_FLEET [constant:290], NEXT_GEN_FLEET [constant:291], EXTENDED_FLEET [constant:292], PROVEN_FRESHNESS_DAYS [constant:293], MATRIX_LIVE_BUDGET_USD [constant:294], AGENT_BUILDER_ONLY [constant:295], CORE_INSTRUCTION_FILES [constant:296]

`synlynk/advisory.py` · 6 symbols
  _HARNESS_RECOMMENDATIONS [constant:13], _TIME_BLOCKS [constant:20], get_current_capacity_factor() [function:52], get_utilization_advisory() [function:80], format_advisory_text() [function:96], export_advisory_json() [function:129]

`synlynk/agent_cli.py` · 7 symbols
  SEED_CHARTERS [constant:13], ROLES [constant:227], _resolve_or_exit() [function:230], cmd_agent_init() [function:242], cmd_agent_list() [function:262], cmd_agent_show() [function:276], cmd_agent_edit() [function:296]

`synlynk/agent_store.py` · 27 symbols
  _CONFIG_PATH [constant:13], _FALLBACK_WORKSPACE_ROOTS [constant:14], _now_iso() [function:17], _load_raw_config() [function:21], get_workspace_id() [function:31], _workspace_root() [function:47], _local_workspace_root() [function:54], _write_registry_with_fallback() [function:58], agent_store_path() [function:75], _registry_path() [function:81], _load_registry() [function:86], register_agent() [function:97], resolve_agent_id() [function:124], list_agents() [function:138], set_agent_disabled() [function:143], RevisionConflictError [class:158], _content_hash() [function:162], _read_versioned_file() [function:166], _write_versioned_file() [function:179], read_charter() [function:216], propose_charter_revision() [function:225], sync_dispatch_routing() [function:243], _ENTRY_CATEGORIES [constant:264], _entry_file_path() [function:267], _entry_revisions_path() [function:272], _current_entry_revision() [function:277], _latest_entry_content_hash() [function:291]

`synlynk/approval_gate.py` · 1 symbols
  raise_approval_ticket() [function:7]

`synlynk/attribution.py` · 7 symbols
  SUPPORTED_HARNESSES [constant:15], HARNESS_METADATA [constant:17], _TRIPLET_TAG_RE [constant:26], _COLON_TAG_RE [constant:27], IdentityTriplet [class:31], resolve_identity_triplet() [function:129], cmd_whoami() [function:199]

`synlynk/backlog.py` · 11 symbols
  DEFAULT_ACTIVE_GOALS [constant:17], DEFAULT_BACKLOG_GOAL_ID [constant:45], compute_fingerprint() [function:48], _get_connection() [function:56], _query_github_open_issues() [function:70], fetch_open_github_issues() [function:75], _check_github_duplicate() [function:117], is_duplicate_issue() [function:131], check_duplicate() [function:227], _load_active_goals() [function:254], _classify_role_and_stage() [function:276]

`synlynk/backlog_extractor.py` · 3 symbols
  extract_from_devlog_content() [function:11], extract_from_job_summary() [function:78], extract_from_doctor_failures() [function:110]

`synlynk/backup.py` · 13 symbols
  _sha256() [function:16], _default_source() [function:24], _default_output_dir() [function:33], _row_counts() [function:37], create_snapshot() [function:46], verify_snapshot() [function:110], _require_gpg() [function:132], _keychain_passphrase() [function:139], encrypt_snapshot() [function:155], create_dr_package() [function:199], verify_encrypted_snapshot() [function:232], cmd_backup_create() [function:289], cmd_backup_verify() [function:297]

`synlynk/board.py` · 12 symbols
  BOARD_STATUSES [constant:20], GOVERNS_STAGES [constant:21], _NWO_RE [constant:22], _ID_RE [constant:23], _columns() [function:26], _json_object() [function:33], _repo_names() [function:45], _pointer() [function:57], _open_product_db() [function:80], board_data() [function:92], update_status() [function:156], update_stage() [function:180]

`synlynk/canon.py` · 14 symbols
  _CANON_FILENAME [constant:13], _DOC_INDEX_DIRS [constant:15], _SKELETON_SECTIONS [constant:17], _SKELETON_NOTE [constant:27], _PROVENANCE_RE [constant:32], _build_documentation_index() [function:38], _build_claim_receipt() [function:65], _render_canon() [function:104], _write_canon() [function:137], _head_sha() [function:144], _parse_canon_provenance() [function:163], _check_canon_staleness() [function:178], _offer_deep_scan_consent() [function:196], run_canon_baseline() [function:204]

`synlynk/capability.py` · 8 symbols
  _ensure_table() [function:17], _as_success() [function:37], _now() [function:43], _connection() [function:54], update_capability_score() [function:61], capability_score() [function:140], expected_value() [function:157], route_expected_value() [function:166]

`synlynk/capability_classifier.py` · 2 symbols
  _path_changed_since() [function:14], classify_failure() [function:37]

`synlynk/capability_roles.py` · 1 symbols
  _load_capability_roles() [function:8]

`synlynk/capability_sweep.py` · 17 symbols
  _ESTIMATED_TOKENS_PER_CALL [constant:12], _CALLS_PER_COMBINATION [constant:13], _DEFAULT_SWEEP_COST_CAP_USD [constant:14], _CALIBRATION_SKILLS [constant:15], _SKILL_TO_DISCIPLINE [constant:16], _discover_models() [function:19], _fallback_models_for_harness() [function:46], _estimate_sweep_cost() [function:62], cmd_capability_sweep() [function:76], _pick_verifier_harness() [function:109], _get_db() [function:122], _extract_task_cost_usd() [function:127], cmd_capability_sweep_for_harness_model() [function:139], _pick_verifier_agent() [function:194], _dispatch_calibration_task() [function:207], _verify_calibration_result() [function:217], _run_sweep() [function:246]

`synlynk/capability_watch.py` · 21 symbols
  CAPABILITY_SWEEP_JOB_THRESHOLD [constant:21], CAPABILITY_SWEEP_MAX_AGE_DAYS [constant:22], _now_iso() [function:25], _parse_iso() [function:29], is_probe_stale() [function:38], is_smoke_test_stale() [function:46], _dispatched_job_count() [function:54], capability_sweep_status() [function:62], is_capability_sweep_overdue() [function:85], mark_capability_sweep_run() [function:93], mark_probe_run() [function:101], mark_smoke_test_run() [function:113], _sentinel_path_for_db() [function:125], _record_check_failure() [function:133], _run_free_probe() [function:148], _last_commit_before() [function:186], _run_paid_smoke_test() [function:199], maybe_trigger_staleness_checks() [function:233], _db_path_for_conn() [function:253], _maybe_trigger_staleness_checks_in_thread() [function:263], spawn_staleness_check_thread() [function:275]

`synlynk/charter_injection.py` · 4 symbols
  CharterInjectionError [class:4], _find_agent_for_role() [function:8], resolve_role_charter() [function:19], render_charter_section() [function:46]

`synlynk/charter_schema.py` · 11 symbols
  KNOWN_ROLES [constant:11], VALID_DURABILITY [constant:14], REQUIRED_SECTIONS [constant:15], REQUIRED_FRONTMATTER_KEYS [constant:16], CharterValidationError [class:21], split_frontmatter() [function:27], parse_frontmatter() [function:48], validate_charter() [function:94], _render_task_allocation() [function:146], render_dispatch_routing_block() [function:156], set_frontmatter_block() [function:161]

`synlynk/charters.py` · 6 symbols
  _static_capabilities() [function:11], detect_charter_divergence() [function:22], _proposal_text() [function:51], cmd_charters_adapt() [function:70], ALL_ADAPT_ROLES [constant:114], adapt_charters_for_installed_tools() [function:128]

`synlynk/cli.py` · 5 symbols
  _SYNLYNK_DIR [constant:8], _synlynk_repo_root() [function:11], _warn_stale_repo_version() [function:30], cmd_watch() [function:54], build_parser() [function:184]

`synlynk/coldstart.py` · 12 symbols
  _MANIFEST_FILES [constant:13], _README_FILES [constant:17], _commit_count() [function:20], _detect_cold_start_mode() [function:33], _resolve_cold_start_mode() [function:89], _prompt_new_project_questions() [function:109], _run_new_project_flow() [function:127], _run_existing_project_flow() [function:153], cmd_start() [function:191], run_ftue_journey() [function:214], get_onboarding_recommendations() [function:268], _detect_brownfield_stack() [function:299]

`synlynk/completion_tracker.py` · 7 symbols
  _SPEC_PATH_RE [constant:12], _CLOSES_ISSUE_RE [constant:13], _GH_HASH_RE [constant:14], _VALID_VERDICTS [constant:16], parse_spec_reference() [function:19], _load_reference_content() [function:43], compute_completion_verdict() [function:70]

`synlynk/connectors.py` · 9 symbols
  SUPPORTED_PROTOCOLS [constant:13], REACH_VALUES [constant:14], ConnectorInvalid [class:17], _normalize_reach() [function:21], validate_connector_spec() [function:35], connector_metadata_path() [function:60], connector_secret_path() [function:64], add_connector() [function:68], connector_is_dispatchable() [function:95]

`synlynk/context.py` · 9 symbols
  detect_active_home_harness() [function:14], render_runtime_authority_banner() [function:62], _pkg() [function:78], _get_last_devlog_date() [function:85], _write_recent_devlog_entries() [function:98], _write_last_devlog_section() [function:121], _generate_task_context() [function:140], _generate_context_from_db() [function:225], _append_vizor_notes() [function:290]

`synlynk/context_validator.py` · 3 symbols
  render_chips_summary() [function:4], validate_context_interactive() [function:17], validate_context() [function:27]

`synlynk/costs.py` · 11 symbols
  _pkg() [function:13], _TokenCounts [class:20], _extract_codex_structured() [function:37], _extract_claude_structured() [function:66], _extract_agy_structured() [function:98], _extract_muse_structured() [function:131], _event_shows_real_activity() [function:164], _log_has_prior_activity_evidence() [function:180], _log_has_permission_denied_signature() [function:195], _extract_grok_structured() [function:246], extract_tokens() [function:281]

`synlynk/daemon.py` · 12 symbols
  _pkg() [function:25], _repo_common_dir() [function:32], _daemon_state_path() [function:63], _current_repo_revision() [function:67], _daemon_lock_path() [function:84], _try_acquire_daemon_lock() [function:89], _daemon_lock_owner_pid() [function:119], _pid_is_alive() [function:128], _release_daemon_lock() [function:138], _find_pid_listening_on_port() [function:152], _daemonize_via_reexec() [function:170], WatchDaemon [class:192]

`synlynk/db.py` · 26 symbols
  detect_remote_owner_repo() [function:17], qa_gate_verdict() [function:23], _qa_gate_mode() [function:29], _gh_pr_changed_files() [function:35], _is_github_remote() [function:41], _current_pr_number() [function:47], _extract_pr_review_cycles() [function:53], _apply_review_cycle_multiplier() [function:59], _ORG_DOMAINS [constant:64], _DISCIPLINES [constant:76], _ROLES [constant:88], _STAGES [constant:89], _ORG_DOMAIN_DRIFT_MAP [constant:90], _PROJECT_DOC_KEEP_N [constant:95], _DB_MIGRATION_VERSION [constant:104], _GENERATORS_BY_FILENAME [constant:106], _validate_enum_value() [function:114], _normalize_capability_tags() [function:122], _resolve_workspace_root() [function:149], _normalize_stack_tags() [function:160], _detect_stack_tags() [function:173], MigrationImportError [class:180], _parse_memory_md() [function:183], _parse_roadmap_md() [function:206], detect_roadmap_doc_drift() [function:236], _parse_costs_md() [function:289]

`synlynk/discovery.py` · 4 symbols
  _is_graphify_installed() [function:12], _get_head_commit() [function:20], _read_graphify_manifest() [function:31], scan_workspace_static() [function:41]

`synlynk/discovery_semantic.py` · 1 symbols
  enrich_with_semantic_overlay() [function:4]

`synlynk/dispatch.py` · 20 symbols
  _ORG_ROLE_TO_BASELINE_ROLE [constant:22], _GH_WRITE_HARNESS_PRIORITY [constant:33], _STARTUP_FAILOVER_ORDER [constant:34], _CODEX_REVIEW_WRITABLE_ROOTS [constant:35], MODEL_TIER_FAST [constant:39], MODEL_TIER_PRO [constant:40], MODEL_TIER_REASONING [constant:41], MODEL_TIERS [constant:42], _DEFAULT_MODELS_BY_TIER [constant:44], ast_blast_radius_score() [function:69], _impact_targets() [function:79], calculate_dispatch_impact() [function:89], resolve_model_tier() [function:111], resolve_dispatch_model() [function:135], _codex_network_flags() [function:178], _secondary_harness() [function:186], task_requires_write() [function:203], check_grok_sandbox_write_capability() [function:223], _harness_for_org_role() [function:250], expected_dispatch_value() [function:298]

`synlynk/doctor.py` · 17 symbols
  _pkg() [function:42], _BOLD [constant:49], _GREEN [constant:50], _YELLOW [constant:51], _DIM [constant:52], _RESET [constant:53], HealthCheck [class:57], FixPlan [class:65], _hc_python_version() [function:75], _hc_project_init() [function:90], _hc_identity_slug() [function:101], _hc_model_registry() [function:116], _hc_codex_model_catalog() [function:131], _hc_docs_dir() [function:205], _hc_todo_drift() [function:230], _hc_identity_key() [function:272], _hc_identity_roles() [function:292]

`synlynk/events.py` · 12 symbols
  RELAY_EVENT_TYPES [constant:18], ActorIdentifier [class:29], EventEnvelope [class:47], _ROLE_LOGIN_RE [constant:99], _ROLE_EXPANSIONS [constant:101], _reviewer_role_from_login() [function:107], _existing_review_submitted_keys() [function:118], _scan_pr_reviews() [function:137], _existing_spec_verified_pr_numbers() [function:179], _scan_pr_completion() [function:199], _existing_approval_resolved_keys() [function:229], _scan_approval_tickets() [function:249]

`synlynk/examples.py` · 2 symbols
  greet() [function:6], active_items() [function:11]

`synlynk/fencing.py` · 5 symbols
  FenceData [class:8], NudgeData [class:20], render_task_fence() [function:27], render_nudge_fence() [function:43], is_fenced_command() [function:53]

`synlynk/first_win.py` · 1 symbols
  dispatch_first_win_task() [function:6]

`synlynk/fleet.py` · 17 symbols
  _LIVE_SMOKE_PROMPT [constant:27], _LIVE_SMOKE_TIMEOUT_S [constant:31], _LIVE_SMOKE_COST_USD [constant:33], check_core_instruction_files() [function:36], find_nested_product_state_dbs() [function:54], sandbox_fallback_db_path() [function:69], purge_nested_product_state_under() [function:86], is_nested_worktree_state_path() [function:111], assert_not_nested_product_ledger() [function:117], doctor_hard_fail() [function:126], terminal_status_for_unknown_exit() [function:145], MatrixCellResult [class:155], new_run_id() [function:164], run_matrix_dry() [function:169], repo_has_any_core_instruction_file() [function:261], preflight_blocks_dispatch() [function:274], tier_for_agent() [function:295]

`synlynk/gap_scanner.py` · 2 symbols
  scan_workspace_gaps() [function:5], generate_governs_goal() [function:40]

`synlynk/gh_role.py` · 1 symbols
  cmd_gh() [function:17]

`synlynk/gh_shim.py` · 11 symbols
  HARNESS_ENV_KEYS [constant:19], KNOWN_ROLES [constant:28], REFUSAL [constant:31], _is_harness_session() [function:34], _truthy() [function:40], _real_gh_path() [function:44], write_shim() [function:54], install_shim() [function:73], shim_env() [function:79], run_shim() [function:83], main() [function:107]

`synlynk/gh_verify.py` · 13 symbols
  _TARGET_RE [constant:11], _EXPECT_FIELD [constant:12], _LIST_EXPECT_FIELD [constant:17], _LIST_VERIFY_ATTEMPTS [constant:21], _LIST_VERIFY_BACKOFF_SECONDS [constant:22], _naive_local_tz() [function:25], _parse_iso8601() [function:30], _compare_dt_lt() [function:60], _normalize_gh_login() [function:72], _gh_logins_match() [function:79], _author_login() [function:87], _verify_pr_opened_for_issue() [function:96], gh_write_verified() [function:149]

`synlynk/git_ref_lock.py` · 2 symbols
  _common_git_dir() [function:8], git_ref_operation_lock() [function:31]

`synlynk/github_app_auth.py` · 15 symbols
  GITHUB_API [constant:16], _redaction_cache_path() [function:20], _default_apps_dir() [function:24], _role_token_cache_path() [function:37], _persist_token_for_redaction() [function:42], _load_redaction_tokens() [function:67], _resolve_openssl_path() [function:87], _b64url() [function:112], _b64url_decode() [function:116], _build_jwt_signing_input() [function:121], _resolve_private_key_path() [function:132], _sign_jwt() [function:203], _mint_installation_token() [function:223], refresh_installation_token() [function:247], read_cached_installation_token() [function:268]

`synlynk/handover.py` · 10 symbols
  SUPPORTED_HARNESSES [constant:16], HANDOVER_FILE [constant:19], ACTIVE_SESSION_FILE [constant:20], get_active_story_for_harness() [function:23], calculate_drain_horizon() [function:48], record_handover_state() [function:89], load_handover_state() [function:113], is_harness_draining() [function:126], complete_harness_drain() [function:137], execute_home_handover() [function:149]

`synlynk/heal.py` · 10 symbols
  _merged_pr_branch() [function:9], _diagnostics() [function:23], _verify_story() [function:40], _auto_merge() [function:50], _discover_ast_gaps() [function:77], _generate_magic_test_content() [function:119], test_magic_module_importable() [function:131], test_magic_module_structure() [function:141], run_magic_heal() [function:155], cmd_heal() [function:255]

`synlynk/heal_cycles.py` · 5 symbols
  _normalize_cycle() [function:8], detect_import_cycles() [function:17], _create_story_safe() [function:80], heal_import_cycles() [function:117], cmd_heal_cycles() [function:157]

`synlynk/hud.py` · 20 symbols
  CYCLES [constant:13], CYCLE_COLOURS [constant:15], RESET [constant:25], DIM [constant:26], BOLD [constant:27], SIDEBAR_WIDTH [constant:29], _ANSI_RE [constant:31], _parse_dt() [function:34], _elapsed_s() [function:43], _humanize_seconds() [function:50], _humanize_currency() [function:63], _humanize_tokens() [function:69], _get_terminal_size() [function:76], _cursor_to() [function:81], _strip_ansi() [function:85], _truncate_visible() [function:89], JobSnapshot [class:113], HarnessSnapshot [class:163], FrameBuffer [class:183], HUDRenderer [class:212]

`synlynk/identity_roles.py` · 4 symbols
  DEFAULT_ROLES [constant:10], ROLES_YAML_PATH [constant:12], load_declared_roles() [function:15], write_declared_roles() [function:47]

`synlynk/impact.py` · 3 symbols
  _is_test_node() [function:10], calculate_impact() [function:26], cmd_impact() [function:152]

`synlynk/install.py` · 2 symbols
  check_install_prerequisites() [function:7], run_install_preflight() [function:33]

`synlynk/instructions.py` · 13 symbols
  extract_instruction_version() [function:21], get_instruction_file_for_agent() [function:39], _pkg() [function:44], _current_trigger_registry_tier() [function:51], render_trigger_phrase_section() [function:60], render_lifecycle_checkpoint_section() [function:73], _generate_ai_context_files() [function:99], _strip_synlynk_section() [function:117], _extract_synlynk_section() [function:139], _compute_section_sha() [function:155], _write_instruction_file() [function:160], _find_existing_doc() [function:215], _write_informed_skeleton() [function:246]

`synlynk/jobs.py` · 27 symbols
  _BOLD [constant:24], _GREEN [constant:25], _YELLOW [constant:26], _DIM [constant:27], _RESET [constant:28], _HARNESS_INTERNAL_TIMEOUT_RETRY_CAP [constant:29], _AUTOCOMMIT_EXCLUDED_PATHS [constant:30], _AUTOCOMMIT_TRAILER [constant:39], _pkg() [function:42], _worktree_path_is_available() [function:49], _load_jobs() [function:69], _save_jobs() [function:80], _reconciliation_lock() [function:89], _job_retry_count() [function:111], _cost_inflation_is_critical() [function:119], _exit_code_from_wait_status() [function:153], _job_has_real_work_landed() [function:162], _git_state_files_touched() [function:169], _read_job_log() [function:179], _check_scope_compliance() [function:199], _log_has_permission_denied_signature() [function:212], _TASK_RECEIPT_MARKER_PREFIX [constant:217], _INSTRUCTION_RECEIPT_MARKER_PREFIX [constant:218], _check_task_receipt() [function:221], _check_instruction_receipt() [function:242], _instruction_receipt_is_trusted() [function:264], _classify_task_delivery() [function:285]

`synlynk/launch.py` · 9 symbols
  _BOLD [constant:10], _GREEN [constant:11], _YELLOW [constant:12], _CYAN [constant:13], _DIM [constant:14], _RESET [constant:15], find_top_scan_finding() [function:18], dispatch_first_win_remediation() [function:109], prompt_first_win_remediation() [function:157]

`synlynk/launch_dag.py` · 11 symbols
  _RESET [constant:23], _BOLD [constant:24], _GREEN [constant:25], _YELLOW [constant:26], _CYAN [constant:27], _RED [constant:28], _DIM [constant:29], raise_escalation_ticket() [function:32], DAGNode [class:70], LaunchDAG [class:88], cmd_run_dag() [function:281]

`synlynk/lineage.py` · 8 symbols
  _LINEAGE_LOCK [constant:16], _resolve_db_path() [function:19], ensure_lineage_schema() [function:27], _connect_lineage_db() [function:60], _lineage_write_lock() [function:72], record_job_superseded() [function:96], record_story_superseded() [function:150], get_job_lineage() [function:189]

`synlynk/local_agent.py` · 8 symbols
  _DEFAULT_CONFIG_PATH [constant:16], _DEFAULT_LOCAL_CONFIG [constant:17], _load_local_config() [function:29], _pinned_model() [function:41], _health_check() [function:49], _STARTER_TIER_GUARDRAIL_FLAGS [constant:64], _local_dispatch_model_flags() [function:71], cmd_local_doctor() [function:97]

`synlynk/local_agent_seed.py` · 4 symbols
  MODEL_VERSION [constant:12], STARTER_WHITELIST [constant:15], SEED_QUALITY [constant:22], seed_local_capability_envelope() [function:25]

`synlynk/local_http_auth.py` · 8 symbols
  TOKEN_HEADER [constant:15], _LOCAL_HOSTNAMES [constant:16], http_token_path() [function:21], ensure_local_token() [function:25], header_value() [function:55], _is_local_url() [function:71], local_browser_origin_ok() [function:83], authorize_local_request() [function:94]

`synlynk/logs.py` · 7 symbols
  _pkg() [function:8], _render_codex_log_line() [function:13], _render_claude_log_line() [function:37], _redact_active_tokens() [function:70], _SECRET_PATTERNS [constant:77], _redact_secret_patterns() [function:84], cmd_logs() [function:90]

`synlynk/marketing.py` · 7 symbols
  REQUIRED_BLOG_FRONTMATTER_KEYS [constant:16], BlogValidationError [class:26], split_frontmatter() [function:37], parse_yaml_frontmatter() [function:57], validate_blog_post_frontmatter() [function:131], extract_social_changelog_snippets() [function:191], update_blog_index() [function:296]

`synlynk/media.py` · 3 symbols
  generate_svg_diagram() [function:14], generate_og_card() [function:113], cmd_media_generate() [function:186]

`synlynk/merge_class.py` · 2 symbols
  _DOCS_ONLY_EXCLUDE [constant:11], is_docs_only_change() [function:14]

`synlynk/merge_oracle.py` · 3 symbols
  _run_pr_check() [function:13], _run_qa_gate() [function:26], require_merge_oracle() [function:36]

`synlynk/mesh.py` · 9 symbols
  merge_fleet_graphs() [function:17], infer_cross_repo_edges() [function:64], write_global_graph() [function:109], _HUNK_RE [constant:128], AstSymbolInfo [class:132], extract_file_ast_symbols() [function:141], parse_diff_line_ranges() [function:215], map_diff_to_ast_symbols() [function:239], get_worktree_modified_symbols() [function:283]

`synlynk/models.py` · 24 symbols
  EntitlementTier [class:23], RateCard [class:31], ContextGeometry [class:39], ModelFamily [class:46], ModelSpec [class:55], _remote() [function:77], BUILTIN_FAMILIES [constant:81], BUILTIN_MODEL_CATALOG [constant:91], MODEL_FAMILIES [constant:111], BUILTIN_MODELS [constant:112], load_model_catalog() [function:115], resolve_tier_model() [function:157], get_models_from_catalog() [function:182], _jsonable() [function:206], model_to_dict() [function:218], family_to_dict() [function:222], _parse_model_names() [function:226], probe_cli_harness() [function:243], _probe_http() [function:256], probe_local_runtimes() [function:266], probe_ollama() [function:285], probe_omlx() [function:290], discover_environment() [function:295], discover_models() [function:300]

`synlynk/multirepo_graph.py` · 4 symbols
  merge_fleet_graphs() [function:10], infer_cross_repo_edges() [function:57], write_global_graph() [function:102], cmd_multirepo_mesh() [function:117]

`synlynk/observatory.py` · 19 symbols
  OBSERVATORY_SNAPSHOT_PATH [constant:13], OBSERVATORY_CACHE_PATH [constant:14], JOBS_FILE [constant:15], TELEMETRY_FILE [constant:16], _load_json() [function:19], _safe_float() [function:28], _safe_int() [function:37], _parse_dt() [function:46], _age_seconds() [function:67], _humanize_age() [function:75], _job_repo_fallback() [function:87], _normalize_stage() [function:116], _format_repo() [function:140], _coalesce_number() [function:147], _coalesce_int() [function:155], _merge_telemetry() [function:163], _summarize_jobs() [function:197], write_observatory_snapshot() [function:213], build_job_observatory_snapshot() [function:229]

`synlynk/pack.py` · 4 symbols
  _cut_to_token_budget() [function:10], _extract_keywords() [function:19], synthesize_context_pack() [function:30], cmd_pack() [function:145]

`synlynk/parity.py` · 8 symbols
  START_FENCE_REGEX [constant:13], HARNESS_FENCE_REGEX [constant:18], detect_project_stack() [function:24], parse_directive_fences() [function:98], inject_sop_fences() [function:137], ensure_recursive_gitignore() [function:168], generate_stack_policy() [function:194], run_parity_remediation() [function:274]

`synlynk/platform_ops.py` · 13 symbols
  _SENTINEL_CRIT_KEYS [constant:33], _SENTINEL_TS_RE [constant:35], _utc_now() [function:40], _parse_ts() [function:44], _parse_sentinel_line_ts() [function:63], _normalize_dispatch_context() [function:84], aggregate_dispatch_context() [function:94], _is_sentinel_critical_line() [function:131], count_sentinel_critical_lines() [function:144], _dev_roots() [function:186], _project_dbs() [function:199], PlatformReport [class:213], collect_platform_report() [function:232]

`synlynk/platform_status.py` · 9 symbols
  _pkg() [function:16], _load_telemetry_events() [function:21], _parse_status_timestamp() [function:33], _humanize_ago() [function:49], _load_platform_harness_rows() [function:63], _load_platform_drift_agents() [function:106], _load_platform_budget_pulse() [function:123], _print_platform_table() [function:146], _print_platform_health() [function:162]

`synlynk/pm_agent.py` · 11 symbols
  CONFIG_PATH [constant:15], DOC_PATH [constant:16], RADAR_OUTPUT_PATH [constant:17], PM_RADAR_DOC_PATH [constant:18], extract_radar_opportunities() [function:21], save_radar_opportunities() [function:102], _load_config() [function:143], _resolve_decide_panel() [function:148], _compose_prompt() [function:154], _invoke_headless_claude() [function:195], cmd_pm_sweep() [function:210]

`synlynk/policy.py` · 11 symbols
  _read_json() [function:64], _workspace_policy_path() [function:71], _repo_policy_path() [function:75], load_policy() [function:79], get_human_authority_role() [function:112], AuthorityResult [class:125], _ACTION_PREFIXES [constant:131], _matches_approval_rule() [function:134], check_authority() [function:145], _merge_role_allowed() [function:179], verify_testbed_receipt() [function:195]

`synlynk/policy_cli.py` · 5 symbols
  REQUIRED_STATUS_CHECKS [constant:10], _current_repo_slug() [function:13], cmd_policy_check_merge() [function:21], cmd_policy_show() [function:39], cmd_policy_sync_branch_protection() [function:45]

`synlynk/pr_check.py` · 2 symbols
  _get_modified_symbols_from_diff() [function:11], check_pr_impact_attestation() [function:37]

`synlynk/pr_multiplier.py` · 8 symbols
  _MULTIPLIER_BASE [constant:7], _MULTIPLIER_DECAY [constant:8], _MULTIPLIER_FLOOR [constant:9], _review_cycle_multiplier() [function:12], _apply_review_cycle_multiplier() [function:24], _current_pr_number() [function:52], _current_pr_number_from_head_sha() [function:86], _is_github_remote() [function:139]

`synlynk/pr_rebase.py` · 1 symbols
  rebase_pr_if_behind() [function:9]

`synlynk/probe.py` · 18 symbols
  SOP_SECTION_HEADERS [constant:17], REPAIR_HARNESS_VERSION [constant:27], _PR_REVIEW_SOP [constant:29], _BRAINSTORM_SOP [constant:42], _DESIGN_SEQUENCE_SOP [constant:49], _CAPABILITY_ALLOCATION_SOP [constant:58], _COST_VISIBILITY_SOP [constant:80], _REPO_HYGIENE_SOP [constant:88], _HERDR_WORKSPACE_SOP [constant:97], _TPM_GITHUB_SYNC_SOP [constant:113], SOP_BLOCKS [constant:123], _VERSION_TOKEN_PATTERN [constant:134], _compute_capability_hash() [function:137], _baseline_schema_issues() [function:145], _run_tc0() [function:203], _scan_command_palette() [function:213], _now_iso() [function:272], _diff_and_queue_new_models() [function:277]

`synlynk/product_store.py` · 15 symbols
  _slugify() [function:19], identity_slug_from_config() [function:24], configured_identity_slug() [function:61], product_root() [function:72], github_apps_dir() [function:76], repos_path() [function:80], types_yaml_path() [function:84], types_dir() [function:88], connectors_dir() [function:92], state_db_path() [function:97], migrate_state_db_if_needed() [function:102], ensure_product_dirs() [function:210], resolve_github_apps_dir() [function:221], write_apps_dir_for_init() [function:253], migrate_repo_apps_if_needed() [function:259]

`synlynk/qa_gate.py` · 8 symbols
  _qa_gate_mode() [function:18], _gh_pr_changed_files() [function:27], _qa_gate_ci_status() [function:42], _HIGH_SEVERITY_MARKERS [constant:51], _ANSI_ESCAPE [constant:52], _qa_gate_sentinel_health() [function:55], qa_gate_verdict() [function:103], cmd_pr_gate_status() [function:132]

`synlynk/quota.py` · 15 symbols
  _pkg() [function:17], QUOTA_TYPES [constant:26], QUOTA_UNITS [constant:27], _CAPABILITY_COST_TIE_GAP [constant:29], _QUOTA_WINDOW_SECONDS [constant:33], _DEFAULT_QUOTA_LIMITS [constant:45], _KNOWN_AGENT_BINARIES [constant:54], _quota_headroom() [function:59], _load_telemetry_events() [function:67], _event_epoch() [function:80], _agent_from_telemetry_event() [function:105], _quota_limits_from_config() [function:127], _window_reset_at_iso() [function:161], _aggregate_usage_from_telemetry() [function:171], refresh_agent_quotas_from_telemetry() [function:232]

`synlynk/readiness.py` · 14 symbols
  _BOLD [constant:12], _GREEN [constant:13], _YELLOW [constant:14], _RED [constant:15], _CYAN [constant:16], _DIM [constant:17], _RESET [constant:18], _policy_requires_gh_write() [function:21], _declared_durable_roles() [function:42], check_durable_role_app_material() [function:70], _with_durable_role_app_material() [function:134], check_point_1_role_tokens() [function:155], check_point_2_sandbox_egress() [function:261], check_point_3_policy_authority() [function:287]

`synlynk/rebase.py` · 10 symbols
  MARKDOWN_INDEX_PATHS [constant:11], _CONFLICT [constant:16], _PR_NUMBER [constant:17], _merge_markdown_conflict() [function:20], auto_rebase_markdown_conflicts() [function:55], SpeculativeRebaseNode [class:85], BranchInterference [class:98], compute_branch_interference() [function:109], extract_python_ast_symbols() [function:161], _MinimalAstUnparser [class:210]

`synlynk/relay.py` · 9 symbols
  encode_websocket_frame() [function:19], decode_websocket_frame() [function:35], format_nats_pub() [function:69], parse_nats_frame() [function:76], _db() [function:88], _recipient_key() [function:93], RelayBroker [class:101], RelayHandler [class:247], RelayServer [class:297]

`synlynk/release_marketing.py` · 9 symbols
  CANONICAL_DOC_HTML_NAMES [constant:25], ReleaseCeremonyResult [class:33], sync_docs_bundles() [function:46], find_chrome_binary() [function:121], find_pandoc_binary() [function:138], compile_html_to_pdf() [function:155], compile_docs_pdfs() [function:186], compile_book_epub() [function:224], mirror_docs_pdfs_to_website() [function:273]

`synlynk/release_readme.py` · 29 symbols
  WAIVABLE_CHECKS [constant:14], ALL_CHECKS [constant:17], PLANNED_MARKERS [constant:18], COMMANDS_START [constant:25], COMMANDS_END [constant:26], _VERSION_BADGE_RE [constant:27], _TEST_BADGE_RE [constant:28], _TEST_PROSE_RE [constant:31], _HERO_RE [constant:34], _MD_LINK_RE [constant:35], _INLINE_CODE_RE [constant:36], _FENCE_RE [constant:37], _SYNLYNK_CMD_RE [constant:38], _COLLECTED_RE [constant:42], _GITHUB_RELATIVE_ROUTE_RE [constant:43], ReadmeFinding [class:51], parse_waivers() [function:57], collect_pytest_test_count() [function:80], _taxonomy_commands() [function:121], _generated_command_section() [function:125], _relative_link_target() [function:134], _is_github_relative_route() [function:144], _path_is_inside_root() [function:150], _line_is_planned() [function:159], _extract_command_candidates() [function:164], _command_is_shipped() [function:188], _split_test_count_claims() [function:201], _unique_claim() [function:211], validate_readme_for_release() [function:218]

`synlynk/release_signals.py` · 11 symbols
  _TAG_FORMAT [constant:11], _git_tags_with_dates() [function:14], _SEMVER_RE [constant:41], _CALVER_RE [constant:42], _MONOREPO_RE [constant:43], _classify_single_tag() [function:46], _detect_tag_pattern() [function:56], _latest_tag() [function:75], _commits_since() [function:81], _release_status() [function:98], _fetch_github_releases() [function:137]

`synlynk/rollback.py` · 20 symbols
  ROLLBACK_DIR [constant:20], MANIFEST_PATH [constant:21], ARCHIVE_DIR [constant:22], _new_op_id() [function:25], _dest_for() [function:29], _backup_paths() [function:37], _restore_paths() [function:53], _write_manifest() [function:73], _read_manifest() [function:79], _archive_manifest() [function:87], _git_head_sha() [function:96], _git_dirty() [function:103], _stash_paths() [function:110], _pop_stash() [function:142], restore_leg1() [function:158], rollback_checkpoint() [function:171], _SCRIPT_INSTALL_PATHS [constant:228], restore_leg2() [function:231], rollback_checkpoint_upgrade() [function:252], cmd_rollback() [function:282]

`synlynk/sandbox.py` · 4 symbols
  scaffold_greenfield_sandbox() [function:7], ping_endpoint() [function:19], test_ping_endpoint_success() [function:39], build_artifact_tour() [function:57]

`synlynk/scan.py` · 13 symbols
  _pkg() [function:16], _HARNESS_PATH_NAMES [constant:23], _detect_harnesses_on_path() [function:26], cmd_scan() [function:56], _BOLD [constant:237], _GREEN [constant:239], _YELLOW [constant:241], _CYAN [constant:243], _DIM [constant:245], _RESET [constant:247], _RED [constant:249], _MAGENTA [constant:251], _static_scan() [function:253]

`synlynk/scheduler.py` · 6 symbols
  MAX_STORY_RETRIES [constant:13], _story_failed_agents() [function:16], _story_retry_count() [function:25], _compute_schedule_plan() [function:34], _enqueue_plan() [function:156], cmd_schedule() [function:200]

`synlynk/selftest.py` · 12 symbols
  ScenarioContext [class:28], ScenarioResult [class:43], _chdir() [function:51], _workspace_dir() [function:60], _ensure_workspace_scaffold() [function:68], _provision_probe_metadata_for_mode() [function:116], _provision_probe_metadata() [function:129], _copy_probe_metadata_rows() [function:170], _provision_synthetic_probe_metadata() [function:198], _capture_call() [function:217], _scenario_init() [function:235], _scenario_init_existing_files() [function:239]

`synlynk/sentinel.py` · 18 symbols
  _REAL_POPEN_TYPE [constant:14], _SENTINEL_ALERT_RE [constant:18], _SENTINEL_ALERT_LEGACY_RE [constant:22], _SENTINEL_ALERT_NO_TIMESTAMP_RE [constant:25], _SENTINEL_VERSION_DRIFT_AGENT_RE [constant:28], DEFAULT_SENTINEL_DEDUP_WINDOW_SECONDS [constant:32], DEFAULT_SENTINEL_ACTIVE_TTL_SECONDS [constant:33], _sentinel_policy() [function:42], _normalize_sentinel_severity() [function:77], _parse_sentinel_timestamp() [function:82], _parse_sentinel_alert() [function:95], _alert_identity() [function:124], _alert_is_active() [function:133], _iter_sentinel_alerts() [function:155], _sentinel_file_lock() [function:198], log_telemetry_event() [function:220], _check_costs_freshness() [function:238], _write_sentinel_alert() [function:249]

`synlynk/session.py` · 4 symbols
  _active_session_path() [function:13], _read_active_session() [function:17], _write_active_session() [function:30], _clear_active_session() [function:36]

`synlynk/spike.py` · 3 symbols
  generate_spike_receipt() [function:9], run_spike_eval() [function:61], cmd_spike() [function:102]

`synlynk/state_inventory.py` · 5 symbols
  _sha256() [function:11], _classify() [function:19], _metadata() [function:34], inventory() [function:60], cmd_state_inventory() [function:89]

`synlynk/state_registry.py` · 16 symbols
  REGISTRY_VERSION [constant:19], _PRODUCT_NAMESPACE [constant:20], StateRegistryError [class:23], registry_path() [function:27], _lock_path() [function:34], registry_lock() [function:39], _read_unlocked() [function:62], _fsync_directory() [function:77], _write_unlocked() [function:88], _legacy_product_id() [function:106], product_identity() [function:111], canonical_path() [function:129], registered_canonical_path() [function:164], ensure_registered_product() [function:179], update_registered_product() [function:223], identity_metadata() [function:237]

`synlynk/state_repair.py` · 8 symbols
  _sha256() [function:24], _fsync_file() [function:32], _fsync_dir() [function:37], _normalized_copy() [function:48], register_existing_state() [function:73], promote_state_db() [function:99], quarantine_state_db() [function:164], restore_state_db() [function:205]

`synlynk/status.py` · 16 symbols
  TOOL_DEF_OVERHEAD [constant:21], TASK_TYPE_OUTPUT [constant:22], SYSTEM_OVERHEAD [constant:23], LEGACY_CYCLE_ALIASES [constant:24], _CATEGORY_TO_CYCLE [constant:34], _classify_task_type() [function:43], _get_avg_tool_calls() [function:52], estimate_dispatch_tokens() [function:84], _cycle_from_row() [function:98], _compute_cycle_capability() [function:123], _headless_efficiency_ratio() [function:196], _load_harness_status_rows() [function:209], _load_cycle_capability_rows() [function:261], _load_exec_jobs_from_telemetry() [function:274], _format_rates_line() [function:294], _format_status_terminal() [function:300]

`synlynk/story_provisioning.py` · 9 symbols
  _ISSUE_NUMBER_RE [constant:10], _DISCIPLINE_KEYWORDS [constant:12], _ORG_DOMAIN_LABEL_MAP [constant:24], _pkg() [function:29], _detect_issue_number() [function:36], _classify_heuristic() [function:46], classify_story() [function:95], resolve_or_create_story_id() [function:106], cmd_backfill_capability_ratings() [function:183]

`synlynk/support_engineer.py` · 9 symbols
  _pkg() [function:13], cmd_agent_run() [function:20], _install_cron_entry() [function:133], cmd_harness_list() [function:158], _collect_test_suite() [function:184], _collect_platform_ops() [function:202], _collect_sentinel_alerts() [function:229], _collect_telemetry_anomaly() [function:254], _collect_capability_drop() [function:283]

`synlynk/surface.py` · 2 symbols
  detect_developer_surfaces() [function:7], bind_surface_rules() [function:32]

`synlynk/swarm.py` · 5 symbols
  _manager() [function:11], _publish_progress() [function:15], cmd_swarm_dispatch() [function:23], cmd_swarm_status() [function:36], cmd_swarm_destroy() [function:40]

`synlynk/taxonomy.py` · 2 symbols
  iter_leaf_commands() [function:6], COMMAND_TAXONOMY [constant:33]

`synlynk/taxonomy_standards.py` · 8 symbols
  NAICS_CODES [constant:12], APQC_CODES [constant:36], SFIA_CODES [constant:60], _AXIS_TABLES [constant:84], LEGACY_DISCIPLINE_CROSSWALK [constant:92], LEGACY_ORG_DOMAIN_CROSSWALK [constant:103], LEGACY_INDUSTRY_CROSSWALK [constant:111], _taxonomy_label() [function:121]

`synlynk/team.py` · 21 symbols
  _pkg() [function:31], _BOLD [constant:38], _GREEN [constant:39], _YELLOW [constant:40], _CYAN [constant:41], _DIM [constant:42], _RESET [constant:43], _PANEL_IDENTITY_ENV_KEYS [constant:46], _panel_execution_identity() [function:55], _panel_text() [function:71], _panel_failure() [function:76], _resolve_panel_model() [function:88], _panel_preflight() [function:103], get_username() [function:215], get_mode() [function:238], _ensure_identity_key() [function:250], _role_slug() [function:265], _role_app_dir() [function:270], _write_role_app_paths() [function:275], _role_app_paths() [function:285], _resolve_project_slug() [function:291]

`synlynk/tool_installer.py` · 2 symbols
  is_tool_available() [function:26], install_tool() [function:33]

`synlynk/tpm_hooks.py` · 3 symbols
  tpm_observe_reservations() [function:10], tpm_reorder_queue() [function:47], tpm_reallocate() [function:60]

`synlynk/tpm_sweep.py` · 4 symbols
  _FALLBACK_HARNESS [constant:13], _ready_stories() [function:16], _resolve_harness() [function:35], run_sweep_pass() [function:49]

`synlynk/tui.py` · 12 symbols
  render_fleet_panel() [function:9], render_jobs_panel() [function:25], render_costs_panel() [function:39], render_review_panel() [function:48], PANELS [constant:60], _job_status() [function:68], _job_pr_number() [function:73], _is_pending_approval() [function:81], _is_in_flight() [function:85], _message() [function:89], _main() [function:94], main() [function:161]

`synlynk/types_registry.py` · 17 symbols
  TypeExists [class:10], UnknownKind [class:11], UnknownType [class:12], PACK_DIR [constant:14], PACK_IDS [constant:15], _load_pack() [function:40], _pack_types() [function:52], PACK_TYPES [constant:60], _load() [function:63], load_types() [function:70], resolve_type() [function:74], effective_skills() [function:82], _save() [function:95], _charter() [function:102], seed_canonical_types() [function:111], type_create() [function:122], relabel_type() [function:140]

`synlynk/uninstall.py` · 1 symbols
  execute_uninstall() [function:8]

`synlynk/upgrade.py` · 8 symbols
  _detect_install_type() [function:12], _ver_tuple() [function:34], _run_upgrade() [function:41], _get_pipx_source() [function:75], _warn_stale_script_install() [function:89], _ensure_vizor_daemon_installed() [function:105], upgrade() [function:117], execute_upgrade() [function:177]

`synlynk/ux_nudges.py` · 2 symbols
  TUI_TIP_ID [constant:3], pending_ux_tip() [function:6]

`synlynk/uxcore.py` · 18 symbols
  Role [class:20], Actor [class:27], LocalActor [class:32], DEFAULT_ACTOR [constant:39], UxCoreError [class:42], Event [class:51], WriteResult [class:60], Costs [class:71], Task [class:79], Stage [class:90], Dream [class:102], _KNOWN_AGENTS [constant:115], _looks_like_stage_label() [function:118], _story_cost_est() [function:122], _dream_cost_breakdown() [function:131], _fetch_cost_rows() [function:150], get_costs() [function:159], get_gantt_data() [function:195]

`synlynk/viz.py` · 11 symbols
  VIZ_CACHE_DIR [constant:26], VIZ_NOTES_PATH [constant:27], VIZ_META_PATH [constant:28], VIZ_WORKSPACE_MAP_PATH [constant:29], DEFAULT_PORT [constant:30], _KNOWN_AGENTS [constant:31], _live_js() [function:34], _load_workspace_repos() [function:101], _load_workspace_map() [function:115], _repo_github_url() [function:125], generate_viz_data() [function:149]

`synlynk/viz_views.py` · 11 symbols
  _VIEWS [constant:18], _now() [function:22], _repo_name() [function:26], _head_sha() [function:30], _id() [function:41], init_workspace_view_tables() [function:46], _save_projection() [function:93], _node() [function:117], _edge() [function:127], extract_product_nodes() [function:135], extract_logical_nodes() [function:162]

`synlynk/vizor_daemon.py` · 18 symbols
  DAEMON_HOME [constant:16], PIDFILE [constant:17], PORTFILE [constant:18], LOGFILE [constant:19], CACHE_ROOT [constant:20], DEFAULT_POLL_INTERVAL [constant:21], _RENDER_LOCK [constant:23], poll_interval() [function:26], workspace_render_context() [function:38], _is_transient_test_path() [function:66], _registered_workspaces() [function:80], refresh_workspace() [function:114], poll_once() [function:133], _log() [function:148], _known_slugs() [function:156], parse_workspace_path() [function:160], _rewrite_workspace_app_route() [function:179], _workspace_index_html() [function:192]

`synlynk/wave6.py` · 6 symbols
  MembershipUnavailable [class:10], GraphUnavailable [class:14], accept_membership() [function:18], connector_dispatch_allowed() [function:29], graph_read() [function:51], hosted_vizor_placeholder() [function:61]

`synlynk/wizard.py` · 21 symbols
  _pkg() [function:22], _BOLD [constant:28], _GREEN [constant:30], _YELLOW [constant:32], _CYAN [constant:34], _DIM [constant:36], _RESET [constant:38], _RED [constant:40], _MAGENTA [constant:42], STAGE_KEYS [constant:44], BackupResult [class:47], guard_dirty_worktree() [function:76], cmd_launch_ftue() [function:172], _WIZ_SYNAPTIC_BLURB [constant:238], _WIZ_PRODUCT_BLURB [constant:246], _wiz_clear() [function:253], _wiz_read_key() [function:257], _kbhit() [function:280], _STAGE_LABELS [constant:294], _STAGE_COLORS [constant:296], _card_summary() [function:298]

`synlynk/workspace.py` · 4 symbols
  _read_json() [function:12], _write_json() [function:20], add_repo() [function:25], cmd_workspace_add_repo() [function:70]

`synlynk/workspace_agent.py` · 3 symbols
  AGENT_NAME [constant:7], _EVENT_TYPES [constant:8], cmd_workspace_agent_run() [function:11]

`synlynk/worktree.py` · 16 symbols
  WorktreeEntry [class:14], WorktreeVerdict [class:21], _parse_worktree_porcelain() [function:29], _is_subpath() [function:50], _build_worktree_entries() [function:56], _classify_worktree() [function:78], _VERDICT_RANK [constant:162], _apply_nesting_floor() [function:165], _gh_auth_available() [function:189], _git_status_dirty() [function:197], _git_is_ancestor() [function:207], _git_commits_ahead() [function:216], _git_net_diff_lines() [function:225], _git_unmerged_cherry_count() [function:239], _gh_pr_for_branch() [function:251], _gather_worktree_signals() [function:279]

`synlynk/worktree_prune.py` · 7 symbols
  _get_worktree_map() [function:16], _get_current_branch() [function:42], _is_worktree_dirty() [function:52], is_patch_equivalent() [function:64], find_patch_equivalent_sibling_branches() [function:97], prune_sibling_branches() [function:134], reap_merged_worktree() [function:176]

`synlynk/worktree_sparse.py` · 4 symbols
  MANDATORY_SPARSE_CONE_DIRS [constant:14], is_sparse_worktree() [function:17], create_sparse_cone_worktree() [function:33], ensure_path_in_sparse_cone() [function:107]

## synlynk/notifiers/  [python · 2]
`synlynk/notifiers/__init__.py` · 0 symbols

`synlynk/notifiers/slack.py` · 6 symbols
  NOTIFY_EVENT_TYPES [constant:13], _vizor_port() [function:16], format_message() [function:25], post_to_webhook() [function:34], run_once() [function:42], main() [function:47]

## synlynk/runners/  [python · 5]
`synlynk/runners/__init__.py` · 0 symbols

`synlynk/runners/base.py` · 1 symbols
  SwarmRunnerDriver [class:7]

`synlynk/runners/fly.py` · 1 symbols
  FlyRunnerDriver [class:15]

`synlynk/runners/local.py` · 1 symbols
  LocalRunnerDriver [class:14]

`synlynk/runners/manager.py` · 2 symbols
  _now() [function:13], RunnerManager [class:17]

## synlynk/testbed/  [python · 7]
`synlynk/testbed/__init__.py` · 0 symbols

`synlynk/testbed/cli.py` · 3 symbols
  get_driver() [function:20], generate_testbed_receipt() [function:26], run_testbed_cli() [function:64]

`synlynk/testbed/driver.py` · 5 symbols
  NodeHandle [class:12], ExecResult [class:21], TestbedDriver [class:32], OrbDriver [class:42], DockerDriver [class:153]

`synlynk/testbed/identities.py` · 3 symbols
  SyntheticIdentity [class:12], get_identity_for_node() [function:64], provision_node_identity() [function:76]

`synlynk/testbed/installer.py` · 4 symbols
  ResolvedTarget [class:16], TargetResolver [class:21], build_local_wheel() [function:39], install_target_on_node() [function:69]

`synlynk/testbed/invariants.py` · 2 symbols
  InvariantReport [class:12], InvariantAsserter [class:29]

`synlynk/testbed/scenarios.py` · 2 symbols
  ScenarioResult [class:13], ScenarioRunner [class:21]

## tests/  [python · 249]
`tests/conftest.py` · 6 symbols
  isolated_db() [function:11], isolate_local_http_token() [function:18], git_worktree_repo() [function:27], stub_staleness_check_thread() [function:38], stub_dispatch_worktree() [function:51], project_dir() [function:78]

`tests/test_advisory.py` · 4 symbols
  test_capacity_factor_by_utc_hour() [function:14], test_utilization_advisory_structure() [function:32], test_format_advisory_text_width_constraint() [function:42], test_export_advisory_json() [function:50]

`tests/test_agent_cli.py` · 13 symbols
  test_isolate_archived_pytest_modules() [function:15], test_fixdispatch_deduplicate_boolean_cli_flag() [function:23], test_config_add_grok_to_agent_slots_in_synlynk_and_default_config_templates() [function:34], test_codex_harness_baseline_includes_verifier_role_and_can_gh_write() [function:72], test_make_live_selftest_provision_probe_metadata() [function:80], test_test_context_uses_synthetic_probe_metadata_without_running_probe() [function:125], test_live_selftest_rejects_unknown_probe_mode_without_marking_provisioned() [function:159], test_live_selftest_probes_empty_source_before_copying_metadata() [function:176], test_live_selftest_does_not_reprobe_populated_source() [function:228], test_cli_detect_and_warn_on_stale_pipxinstall() [function:259], test_cli_does_not_warn_when_repo_version_is_not_newer() [function:273], test_claude_harness_alignment_update_baseline() [function:285], test_harden_harness_instructions_to_prohibit_direct_todo_edits() [function:293]

`tests/test_agent_quota_tracking.py` · 15 symbols
  project_dir() [function:16], _write_telemetry() [function:37], test_diagnose_codex_sandbox_invalid_gh_auth_token_even_when_gh_exits_zero() [function:41], _write_repair_config() [function:63], _seed_harness_record() [function:68], test_agent_reservations_table_exists() [function:87], test_open_release_reservation_lifecycle() [function:99], test_open_reservations_sum_ignores_expired() [function:124], test_open_reservation_with_scope_id_and_job_id() [function:146], test_quota_status_subtracts_open_reservations() [function:159], test_force_exhaust_quota_zeroes_headroom_not_running_jobs() [function:184], test_force_exhaust_quota_creates_row_when_none_exists() [function:214], test_pr_review_discipline_instructions_say_synlynk_pr_check_without_pr_number() [function:227], test_repair_sops_only_injects_synlynks_own_h_repo_specific_config() [function:243], test_repair_sops_only_injects_synlynks_own_h_generic_branch_fallback() [function:280]

`tests/test_agent_role_columns_preserved.py` · 2 symbols
  test_daemon_jobs_agent_id_column_unchanged() [function:1], test_stories_role_column_unchanged() [function:13]

`tests/test_agent_store.py` · 19 symbols
  _valid_charter() [function:6], test_get_workspace_id_mints_and_persists() [function:28], test_get_workspace_id_idempotent() [function:38], test_get_workspace_id_never_overwrites_existing_value() [function:46], test_agent_store_path_under_workspace_home() [function:58], test_register_and_resolve_agent() [function:69], test_register_agent_rejects_duplicate_agent_id() [function:88], test_register_agent_rejects_duplicate_alias_across_agents() [function:102], test_read_charter_missing_returns_empty() [function:116], test_propose_charter_revision_writes_and_reads_back() [function:127], test_propose_charter_revision_rejects_invalid_content() [function:144], test_propose_charter_revision_stale_parent_raises_conflict() [function:156], test_sync_dispatch_routing_populates_block_for_dev() [function:174], test_sync_dispatch_routing_is_noop_for_role_without_task_allocation() [function:194], test_charter_revisions_jsonl_provenance_chain() [function:214], test_read_entry_missing_returns_empty() [function:240], test_propose_entry_revision_writes_and_reads_back() [function:251], test_entries_in_same_category_have_independent_revision_counters() [function:268], test_memory_and_sor_categories_share_one_revisions_file_each() [function:286]

`tests/test_agy_dispatch_fix.py` · 13 symbols
  _job_id() [function:9], _dispatch_git_worktree_job() [function:13], _commit_worktree_files() [function:56], _fake_completed_process() [function:79], test_extract_build_parser_from_clipy_main_for_cli_introspection() [function:90], test_dispatch_real_files_touched_via_git_diff_lists_committed_files_only() [function:101], test_dispatch_real_files_touched_via_git_diff_clean_worktree_returns_empty() [function:118], test_dispatch_real_files_touched_from_different_cwd_uses_absolute_stored_path() [function:126], test_dispatch_real_files_touched_via_git_diff_missing_worktree_path_returns_empty() [function:140], test_dispatch_real_files_touched_via_git_diff_summary_lists_and_truncates_files() [function:146], test_dispatch_real_files_touched_via_git_diff_ignores_uncommitted_noise_in_summary() [function:171], test_dispatch_perjob_git_worktree_isolation_creates_branch_and_worktree() [function:192], test_dispatch_perjob_git_worktree_isolation_prefers_fresh_origin_main_over_stale_local_main() [function:247]

`tests/test_approval_gate.py` · 2 symbols
  test_raise_approval_ticket_calls_gh_issue_create_with_assignee_and_context() [function:6], test_raise_approval_ticket_returns_empty_on_gh_failure() [function:26]

`tests/test_attribution.py` · 7 symbols
  test_identity_triplet_tag_and_dict() [function:15], test_identity_triplet_commit_trailers() [function:27], test_identity_triplet_prompt_header() [function:44], test_identity_triplet_from_tag_and_dict() [function:53], test_identity_triplet_validation() [function:77], test_resolve_identity_triplet_env_and_args() [function:89], test_cmd_whoami_json_output() [function:104]

`tests/test_backlog.py` · 10 symbols
  test_db() [function:25], test_fetch_open_github_issues_parsing() [function:32], test_is_duplicate_issue_deduplication() [function:60], test_is_duplicate_against_closed_prs_and_git() [function:102], test_synthesize_story_from_issue_roles_and_tiers() [function:120], test_synthesize_story_markdown_acceptance_criteria_parsing() [function:159], test_ingest_backlog_pipeline() [function:179], test_triage_and_auto_promote_backlog() [function:223], test_triage_wires_goal_link_helper_for_live_path() [function:273], test_link_captured_backlog_item_to_explicit_or_default_goal() [function:292]

`tests/test_backlog_automation.py` · 10 symbols
  test_db() [function:20], test_compute_fingerprint_normalization() [function:44], test_stage_and_deduplication() [function:51], test_list_staged_backlog() [function:76], test_extract_from_devlog() [function:88], test_extract_from_job_summary() [function:114], test_extract_from_doctor_failures() [function:130], test_check_duplicate_github_layer() [function:142], test_sync_backlog_to_github_with_existing_issue_deduplication() [function:148], test_cli_backlog_integration() [function:168]

`tests/test_backlog_triage_triggers.py` · 5 symbols
  test_db() [function:19], test_synthesize_story_from_issue() [function:29], test_triage_backlog_e2e() [function:44], test_trigger_registry_rendering() [function:57], test_refresh_agent_instruction_triggers() [function:66]

`tests/test_backup.py` · 7 symbols
  gpg_recipient() [function:21], test_create_snapshot_uses_online_backup_and_writes_manifest() [function:59], test_verify_snapshot_rejects_corruption() [function:82], test_encrypt_and_verify_snapshot_without_leaving_plaintext() [function:94], test_encrypt_requires_recipient() [function:115], test_verify_encrypted_snapshot_can_use_keychain_passphrase() [function:122], test_verify_encrypted_snapshot_allows_gpg_agent_pinentry() [function:149]

`tests/test_backup_package.py` · 2 symbols
  test_create_dr_package_stages_plaintext_temporarily() [function:8], test_create_dr_package_requires_recipient() [function:50]

`tests/test_board.py` · 7 symbols
  _product_repo() [function:10], test_board_reads_product_graph_and_deep_links() [function:42], test_board_filters_are_composable() [function:55], test_board_status_writes_product_db_only() [function:62], test_board_status_fails_closed() [function:72], test_board_stage_updates_and_fails_closed() [function:80], test_board_view_is_local_and_uses_status_api() [function:108]

`tests/test_brownfield_init.py` · 12 symbols
  test_detect_brownfield_stack_python() [function:17], test_detect_brownfield_stack_typescript() [function:24], test_detect_brownfield_stack_rust() [function:32], test_detect_brownfield_stack_go() [function:38], test_detect_brownfield_tests_python() [function:44], test_detect_brownfield_tests_npm() [function:50], test_detect_brownfield_linters_python() [function:56], test_detect_brownfield_linters_eslint() [function:62], test_detect_brownfield_build() [function:68], test_bootstrap_4docs() [function:74], test_run_brownfield_init_dry_run() [function:107], test_run_brownfield_init_e2e() [function:117]

`tests/test_bs6_workspace_views_spec.py` · 5 symbols
  SPEC_PATH [constant:5], REQUIRED_HEADINGS [constant:13], REQUIRED_PHRASES [constant:22], test_bs6_workspace_views_spec_exists() [function:32], test_bs6_workspace_views_spec_covers_required_sections() [function:36]

`tests/test_canon.py` · 27 symbols
  test_documentation_index_lists_files_from_both_dirs() [function:7], test_documentation_index_handles_missing_dirs() [function:19], test_documentation_index_ignores_non_markdown_files() [function:24], test_claim_receipt_full_scan_yields_three_claims() [function:34], test_claim_receipt_skips_missing_fields() [function:48], test_claim_receipt_partial_scan_yields_partial_claims() [function:54], test_claim_receipt_skips_git_claim_when_no_git_dir() [function:62], test_claim_receipt_includes_git_claim_when_git_dir_present() [function:70], test_render_canon_includes_provenance_and_both_real_sections() [function:82], test_render_canon_includes_skeleton_sections_without_provenance() [function:91], test_render_canon_defaults_to_unknown_sha_when_none() [function:100], test_write_canon_writes_file() [function:105], _git_init_simple() [function:117], _current_sha() [function:126], test_parse_canon_provenance_round_trips() [function:134], test_parse_canon_provenance_missing_file_returns_none() [function:141], test_parse_canon_provenance_malformed_comment_returns_none() [function:145], test_check_canon_staleness_same_sha_not_stale() [function:150], test_check_canon_staleness_different_sha_is_stale() [function:158], test_check_canon_staleness_unknown_sha_never_stale() [function:169], test_check_canon_staleness_missing_canon_is_stale() [function:176], test_offer_deep_scan_consent_yes() [function:183], test_offer_deep_scan_consent_no() [function:188], test_run_canon_baseline_first_run_writes_file() [function:193], test_run_canon_baseline_first_run_accepts_deep_scan_consent() [function:202], test_run_canon_baseline_rerun_skips_consent_prompt() [function:210], test_run_canon_baseline_rerun_prints_staleness_banner() [function:219]

`tests/test_capability.py` · 3 symbols
  test_beta_update_records_success_and_failure() [function:12], test_beta_evidence_decays_toward_prior() [function:21], test_expected_value_and_router_choose_evidence_based_candidate() [function:33]

`tests/test_capability_classifier.py` · 5 symbols
  git_repo() [function:11], conn() [function:26], test_classify_regression_when_synlynk_path_changed_since_green() [function:32], test_classify_drift_when_only_harness_fingerprint_changed() [function:56], test_classify_unclassified_when_neither_changed() [function:71]

`tests/test_capability_scoring.py` · 28 symbols
  test_get_db_creates_state_db() [function:10], test_migrate_db_creates_tables() [function:17], test_migrate_db_is_idempotent() [function:28], test_init_writes_industry_to_config() [function:34], test_init_infers_industry_from_readme() [function:52], test_story_create_writes_to_db() [function:72], test_story_create_generates_unique_id() [function:84], test_cmd_story_create_accepts_story_id_override() [function:97], test_cmd_story_create_still_generates_id_when_not_given() [function:112], test_story_list_returns_rows() [function:120], test_infer_engg_domain_from_paths() [function:129], test_infer_engg_domain_prefers_specific_over_generic() [function:136], test_extract_model_version_from_meta_header() [function:141], test_extract_model_version_missing_returns_unknown() [function:153], test_extract_model_version_falls_back_to_config() [function:157], test_extract_model_version_parses_various_formats() [function:167], test_extract_auto_signals_test_pass_rate() [function:172], test_extract_auto_signals_build_success_on_zero_exit() [function:179], test_extract_auto_signals_build_fail_on_nonzero_exit() [function:185], test_extract_auto_signals_duration_computed() [function:192], test_extract_auto_signals_all_zeros_on_empty_log() [function:198], test_add_job_completion_summaries_to_synlynk_helper_exists() [function:205], test_extract_auto_signals_returns_test_count() [function:211], test_implement_plan_b_tasks_b1_and_b2_from_docs_superpowers_plans_2026_07_01_bs17_scan_wizard() [function:223], test_extract_auto_signals_test_count_none_when_no_tests() [function:238], test_write_capability_rating_caps_quality_for_trivial_tests() [function:247], test_write_capability_rating_no_cap_for_real_test_suite() [function:268], test_upgrade_launch_task_templates_in_synlynk() [function:289]

`tests/test_capability_sweep.py` · 12 symbols
  test_estimate_sweep_cost_multiplies_agents_models_skills() [function:8], test_estimate_sweep_cost_scales_with_more_models() [function:24], test_sweep_aborts_when_estimate_exceeds_cap() [function:33], test_seed_from_baseline_only_when_ledger_empty() [function:52], test_baseline_seed_routes_default_tagged_story() [function:79], test_capability_baseline_json_ships_inside_package() [function:97], test_run_sweep_writes_baseline_seed_rows_with_independent_verifier() [function:110], test_pick_verifier_harness_is_not_executor() [function:144], test_calibration_pool_has_all_role_difficulty_combinations() [function:156], test_sweep_for_harness_model_writes_calibration_result() [function:168], test_sweep_for_harness_model_dispatches_selected_model() [function:193], test_dispatch_calibration_task_passes_model_to_dispatch_agent() [function:219]

`tests/test_capability_watch.py` · 21 symbols
  conn() [function:20], test_capability_watch_table_exists() [function:27], test_capability_watch_singleton_row_seeded() [function:35], test_gh_write_capability_table_exists() [function:40], test_capability_incidents_table_exists() [function:47], test_is_probe_stale_true_when_never_run() [function:54], test_is_probe_stale_false_when_recent() [function:58], test_is_probe_stale_true_when_old() [function:63], test_is_smoke_test_stale_true_when_never_run() [function:70], test_capability_sweep_overdue_when_never_run() [function:74], test_capability_sweep_overdue_after_job_threshold() [function:78], test_capability_sweep_not_overdue_before_job_or_time_threshold() [function:90], test_mark_smoke_test_run_updates_timestamp() [function:103], test_maybe_trigger_staleness_checks_runs_free_probe_when_stale() [function:112], test_maybe_trigger_staleness_checks_skips_paid_smoke_when_opted_out() [function:121], test_maybe_trigger_staleness_checks_runs_paid_smoke_when_opted_in() [function:131], test_run_free_probe_classifies_failures() [function:141], test_run_paid_smoke_test_classifies_failures() [function:161], test_run_paid_smoke_test_writes_actionable_sentinel_on_failure() [function:182], test_daemon_capability_watch_tick_runs_due_checks() [function:198], test_cli_main_does_not_crash_when_staleness_check_raises() [function:217]

`tests/test_charter_graphify.py` · 6 symbols
  test_adapt_charters_injects_graphify_skills() [function:6], test_adapt_charters_injects_pm_and_verifier_skills() [function:14], test_adapt_charters_when_tool_unavailable() [function:21], test_adapt_charters_updates_living_agent() [function:30], test_cmd_charters_adapt_triggers_tool_adaptation() [function:62], test_cmd_agent_sync_skills() [function:93]

`tests/test_charter_injection.py` · 6 symbols
  _valid_charter() [function:9], _register_pm_with_charter() [function:26], test_render_charter_section_includes_resolved_role_charter() [function:38], test_render_charter_section_resolves_reassigned_role() [function:46], test_render_charter_section_is_noop_when_workspace_has_no_agents() [function:67], test_render_charter_section_raises_when_registered_agents_lack_role() [function:72]

`tests/test_charter_injection_dispatch.py` · 9 symbols
  _valid_charter() [function:13], _init_workspace_agents() [function:30], test_render_charter_section_empty_workspace() [function:45], test_render_charter_section_default_pm() [function:54], test_render_charter_section_explicit_role() [function:63], test_render_charter_section_missing_role_raises() [function:76], test_task_context_includes_charter() [function:85], test_format_prompt_for_agent_includes_live_charter_for_role() [function:101], test_dispatch_agent_populates_charter_metadata_and_context() [function:115]

`tests/test_charter_schema.py` · 22 symbols
  _valid_charter() [function:6], test_split_frontmatter_returns_frontmatter_and_body() [function:33], test_split_frontmatter_missing_returns_none() [function:40], test_split_frontmatter_unclosed_returns_none() [function:47], test_parse_frontmatter_scalars_and_quoted_strings() [function:54], test_parse_frontmatter_empty_flow_list() [function:65], test_parse_frontmatter_flow_list_with_items() [function:70], test_parse_frontmatter_block_list() [function:75], test_validate_charter_accepts_well_formed_content() [function:80], test_validate_charter_rejects_missing_frontmatter() [function:86], test_validate_charter_rejects_missing_required_keys() [function:92], test_validate_charter_rejects_unknown_role() [function:110], test_validate_charter_rejects_invalid_durability() [function:116], test_validate_charter_rejects_missing_section() [function:123], test_validate_charter_rejects_empty_section() [function:132], test_validate_charter_reports_all_missing_sections_at_once() [function:141], test_validate_charter_dispatch_routing_presence_does_not_affect_validity() [function:161], test_render_dispatch_routing_block_nested_dict() [function:169], test_set_frontmatter_block_appends_when_key_absent() [function:185], test_set_frontmatter_block_replaces_existing_key() [function:195], test_set_frontmatter_block_preserves_other_keys() [function:208], test_set_frontmatter_block_raises_without_frontmatter() [function:218]

`tests/test_checkpoint_identity.py` · 1 symbols
  test_checkpoint_writes_to_canonical_member_path() [function:1]

`tests/test_cli_parser.py` · 17 symbols
  test_build_parser_exposes_dispatch_tree_without_running_main() [function:11], test_dispatch_parser_accepts_issue_flag() [function:23], test_dispatch_parser_issue_defaults_to_none() [function:32], test_dispatch_parser_effort_defaults_to_none_and_accepts_low_or_high() [function:41], test_backfill_capability_ratings_parser_registered() [function:52], test_doctor_fix_parser_accepts_agy() [function:61], test_start_command_parses() [function:72], test_type_seed_and_identity_pack_parse() [function:79], test_w8_connector_and_relabel_parsers() [function:87], test_audit_docs_parser_accepts_json_and_fix_flags() [function:100], test_probe_agent_flag_deprecated_alias() [function:110], test_probe_harness_flag_new() [function:116], test_milestone_runs_unattended_by_default() [function:122], test_run_and_launch_help_describe_unattended_default() [function:146], test_fast_cli_import_defers_command_graph() [function:161], test_fast_cli_preserves_help_and_invalid_command_paths() [function:178], test_state_restore_cli_prints_json_result() [function:198]

`tests/test_cli_pm.py` · 1 symbols
  test_pm_sweep_dry_run_cli() [function:7]

`tests/test_cmd_watch.py` · 1 symbols
  test_cmd_watch_exits_on_db_missing() [function:10]

`tests/test_codex_baseline_flags.py` · 2 symbols
  test_codex_valid_flags_use_config_override_for_approval_policy() [function:7], test_codex_tc2_passes_against_live_cli_help() [function:17]

`tests/test_coldstart.py` · 21 symbols
  _git_init() [function:17], test_detect_confident_new_empty_dir() [function:29], test_detect_confident_new_git_zero_commits_no_content() [function:34], test_detect_ambiguous_git_zero_commits_with_readme() [function:40], test_detect_confident_existing_with_commits_and_manifest() [function:46], test_detect_ambiguous_commits_but_no_recognizable_files() [function:53], test_detect_ambiguous_no_git_but_project_files_present() [function:60], test_resolve_confident_mode_does_not_prompt() [function:66], test_resolve_ambiguous_mode_prompts_and_honors_existing_answer() [function:74], test_resolve_ambiguous_mode_prompts_and_honors_new_answer() [function:81], test_resolve_ambiguous_mode_defaults_to_existing_on_empty_answer() [function:88], test_prompt_new_project_questions_collects_four_answers() [function:95], test_prompt_new_project_questions_implementer_optional() [function:112], test_run_new_project_flow_writes_config_and_roadmap_row() [function:120], test_run_existing_project_flow_prints_summary_and_seeds_story() [function:140], test_run_existing_project_flow_warns_on_zero_functional_harnesses() [function:165], test_cmd_start_runs_new_flow_for_empty_dir() [function:188], test_cmd_start_runs_existing_flow_for_populated_repo() [function:196], test_cmd_start_rerun_declined_leaves_project_untouched() [function:214], test_run_existing_project_flow_invokes_canon_baseline() [function:224], test_cmd_start_generates_canon_then_flags_staleness_on_rerun() [function:248]

`tests/test_coldstart_graphify.py` · 7 symbols
  test_onboarding_recommends_graphify_when_missing() [function:7], test_onboarding_graphify_when_already_installed() [function:17], test_generate_onboarding_html_renders_graphify_checkbox() [function:26], test_generate_onboarding_html_when_graphify_installed() [function:37], test_run_ftue_journey_includes_recommendations() [function:46], test_viz_tool_install_request_json() [function:57], test_viz_tool_install_request_form() [function:90]

`tests/test_completion_tracker.py` · 14 symbols
  test_parse_spec_reference_finds_spec_path() [function:7], test_parse_spec_reference_finds_plan_path() [function:12], test_parse_spec_reference_finds_path_with_internal_dot() [function:17], test_parse_spec_reference_finds_closes_issue() [function:22], test_parse_spec_reference_finds_gh_hash_reference() [function:27], test_parse_spec_reference_prefers_spec_path_over_issue_ref() [function:32], test_parse_spec_reference_returns_none_when_no_match() [function:37], test_parse_spec_reference_returns_none_for_empty_body() [function:41], test_compute_completion_verdict_reads_local_spec_file() [function:46], test_compute_completion_verdict_reads_issue_body_for_hash_reference() [function:64], test_compute_completion_verdict_returns_none_when_reference_unreadable() [function:77], test_compute_completion_verdict_returns_none_when_diff_fails() [function:83], test_compute_completion_verdict_returns_none_on_unparseable_claude_output() [function:94], test_compute_completion_verdict_returns_none_for_invalid_verdict_value() [function:106]

`tests/test_completion_tracker_vizor.py` · 3 symbols
  test_generate_viz_data_includes_spec_verifications() [function:5], test_generate_viz_data_spec_verifications_empty_when_no_events() [function:29], test_generate_viz_data_spec_verifications_newest_first() [function:33]

`tests/test_config.py` · 6 symbols
  test_load_config_default_fenced_commands() [function:7], test_load_config_preserves_existing_fenced_commands() [function:14], test_load_config_defaults_story_classification_method() [function:23], test_load_config_preserves_explicit_story_classification_method() [function:31], test_load_config_fills_dispatch_defaults_when_missing() [function:46], test_load_config_preserves_partial_dispatch_block() [function:58]

`tests/test_connectors.py` · 4 symbols
  setup_product() [function:14], test_pack_type_ids_are_distinct_from_kinds_and_relabel_does_not_remint() [function:23], test_connector_requires_allowlist_and_known_protocol() [function:35], test_connector_metadata_is_product_scoped_and_secret_is_not_returned() [function:43]

`tests/test_constants.py` · 2 symbols
  test_every_agent_baseline_declares_env_passthrough() [function:4], test_agy_baseline_valid_flags_includes_print_timeout_and_mode() [function:10]

`tests/test_context.py` · 5 symbols
  _valid_charter() [function:7], _register_pm() [function:24], test_generate_context_includes_resolved_role_charter() [function:34], test_generate_context_is_noop_when_workspace_has_no_agents() [function:43], test_generate_context_stamps_dynamic_runtime_home_authority() [function:52]

`tests/test_context_validator.py` · 2 symbols
  test_validate_context_no_input_json_mode() [function:8], test_render_chips_summary() [function:17]

`tests/test_control_plane_daemon_health.py` · 8 symbols
  _git_run() [function:19], test_resolve_github_apps_dir_in_git_worktree() [function:23], test_resolve_private_key_path_daemon_root_and_project_root() [function:46], test_synlynk_daemon_stop_cleans_stale_lock_when_no_pidfile() [function:71], test_synlynk_daemon_stop_terminates_lock_owner_pid() [function:89], test_dual_ledger_sync_detection_and_write_through() [function:113], test_cli_probe_no_fence_flag() [function:186], test_cli_watch_action_argument() [function:198]

`tests/test_cost_ledger.py` · 11 symbols
  test_cost_entries_has_provenance_columns() [function:15], test_cost_source_not_null_no_default() [function:31], test_migration_backfills_existing_rows_as_legacy_unknown() [function:44], test_insert_cost_row_rejects_invalid_cost_source() [function:87], test_insert_cost_row_writes_a_row() [function:105], test_insert_cost_row_idempotent_on_job_id() [function:126], test_exec_command_passes_agent_to_extract_tokens() [function:161], test_jobs_stall_path_passes_agent_to_extract_tokens() [function:204], test_support_engineer_investigate_passes_agent_to_extract_tokens() [function:244], test_dispatch_agent_codex_flags_include_json() [function:252], test_dispatch_agent_claude_flags_include_stream_json_verbose() [function:283]

`tests/test_costs.py` · 5 symbols
  test_extract_agy_structured_captures_cache_read_tokens() [function:11], test_extract_tokens_captures_agy_cache_read_tokens() [function:34], test_zero_cost_harness_has_api_value_but_no_cash_outlay() [function:58], test_subscription_amortizes_base_fee_over_configured_projection() [function:69], test_true_up_writes_reconciliation_row() [function:88]

`tests/test_cycle_migration.py` · 1 symbols
  test_migrate_remaps_old_cycle_values_in_cycle_capability() [function:6]

`tests/test_daemon_liveness_1572.py` · 7 symbols
  test_daemon_health_ignores_own_pid_in_lockfile() [function:23], test_watch_status_cleans_dead_pid_and_start_succeeds() [function:51], test_daemon_start_does_not_self_deadlock() [function:84], test_watch_start_does_not_self_deadlock() [function:109], test_daemon_restart_when_not_running() [function:133], test_daemon_run_loop_handles_port_conflict() [function:161], test_daemon_stop_kills_orphaned_process_on_http_port() [function:190]

`tests/test_daemon_token_refresh.py` · 10 symbols
  _git_run() [function:14], test_repo_common_dir_is_shared_by_main_repo_and_worktree() [function:18], test_repo_common_dir_falls_back_to_cwd_outside_git() [function:36], test_daemon_paths_and_token_refresh_use_main_repo_from_worktree() [function:41], test_refresh_github_tokens_refreshes_each_provisioned_role() [function:75], test_refresh_github_tokens_one_role_failure_does_not_block_others() [function:98], test_refresh_github_tokens_skips_token_cache_files() [function:125], test_synlynk_daemon_run_loop_refreshes_tokens_on_interval() [function:146], test_synlynk_daemon_run_loop_survives_job_tick_exception() [function:204], test_watch_daemon_run_loop_refreshes_tokens_before_first_sleep() [function:272]

`tests/test_db.py` · 15 symbols
  test_subscriptions_harness_rename_migration_preserves_data_and_constraint() [function:16], test_member_registry_tables_and_seed() [function:56], test_devlog_entries_has_member_id_column() [function:69], test_audit_docs_report_detects_fork_and_unregistered() [function:78], test_audit_docs_report_json_output() [function:112], test_pr_check_soft_warns_on_devlog_fork() [function:132], test_audit_docs_fix_merges_fork() [function:152], _seed_arc() [function:197], test_generate_roadmap_md_creates_file_pre_migration() [function:205], test_generate_roadmap_md_writes_post_migration_path() [function:228], test_cmd_roadmap_add_inserts_arc_and_regenerates_md() [function:244], test_cmd_roadmap_add_refuses_when_role_not_authorized() [function:260], test_cmd_goal_create_refuses_when_role_not_authorized() [function:267], test_cmd_roadmap_add_phase_links_to_existing_arc() [function:274], test_cmd_roadmap_add_phase_without_arc_raises() [function:295]

`tests/test_db_isolation_hygiene.py` · 6 symbols
  _function_nodes() [function:9], _source_has_isolation() [function:15], _function_arguments() [function:38], find_unisolated_db_tests() [function:45], test_all_db_tests_are_isolated() [function:98], test_meta_test_catches_synthetic_unisolated_test() [function:107]

`tests/test_db_migration.py` · 5 symbols
  test_harness_rename_migration_preserves_data() [function:1], test_migrate_db_renames_pre_existing_agent_quotas_without_collision() [function:56], test_v10_reconciles_databases_stamped_at_v9() [function:92], _table_exists_test_helper() [function:110], test_registry_v2_tables_exist() [function:114]

`tests/test_db_pr_check_merge_restricted.py` · 5 symbols
  test_cmd_pr_check_merges_docs_only_pr_when_mode_is_merge_restricted_classes() [function:6], test_cmd_pr_check_does_not_reach_gh_merge_when_policy_blocks() [function:33], test_cmd_pr_check_does_not_merge_when_mode_is_block_only() [function:60], test_cmd_pr_check_does_not_merge_non_docs_only_pr_in_merge_restricted_mode() [function:84], test_cmd_pr_check_does_not_merge_when_gate_is_red() [function:108]

`tests/test_db_read_only.py` · 4 symbols
  test_read_only_db_connection_cannot_write_or_migrate() [function:6], test_read_only_db_connection_fails_closed_on_corruption() [function:25], test_read_only_db_connection_does_not_create_sqlite_sidecars() [function:36], test_read_only_db_connection_snapshots_unapplied_wal() [function:54]

`tests/test_decide_audit.py` · 1 symbols
  test_audit_metrics_exposes_required_dimensions() [function:4]

`tests/test_decide_preflight.py` · 11 symbols
  CORE_HARNESSES [constant:7], _result() [function:10], test_run_agent_sync_fails_closed_on_auth_probe() [function:14], test_run_agent_sync_preserves_stderr_and_exit_code() [function:36], test_run_agent_sync_records_model_and_version() [function:54], test_decide_refuses_partial_panel_before_synthesis() [function:76], _isolated_baseline() [function:94], test_core_harness_panel_preflight_and_invocation_receipt() [function:110], test_core_harness_panel_preflight_rejects_missing_required_auth_path() [function:134], test_core_harness_panel_preflight_preserves_execution_failure_identity() [function:156], test_core_harness_panel_preflight_rejects_auth_failure() [function:177]

`tests/test_devlog_session_linking.py` · 2 symbols
  test_devlog_append_links_session_and_goal() [function:1], test_devlog_append_session_id_defaults_to_active_session() [function:28]

`tests/test_discovery_graphify.py` · 3 symbols
  test_scan_workspace_static_fallback_when_graphify_absent() [function:8], test_scan_workspace_static_uses_graphify_cache_and_checks_staleness() [function:19], test_scan_workspace_static_flags_stale_when_head_advanced() [function:42]

`tests/test_discovery_semantic.py` · 1 symbols
  test_enrich_with_semantic_overlay_timeout_graceful_fallback() [function:8]

`tests/test_discovery_static.py` · 2 symbols
  test_scan_workspace_static_fastapi_and_pydantic() [function:10], health() [function:20]

`tests/test_dispatch.py` · 23 symbols
  test_dispatch_agent_raises_when_task_type_not_in_policy_allocation_table() [function:7], test_preflight_blocks_missing_instruction_file() [function:19], test_dispatch_agent_sets_instruction_receipt_fields() [function:34], test_preflight_blocks_missing_stitch_mcp_when_required() [function:52], test_preflight_blocks_unavailable_local_capability() [function:68], test_fleet_parity_agy_stitch_mcp_integration_preflight_blocks() [function:90], test_format_prompt_for_agy_injects_stitch_tool_hint() [function:94], test_fleet_parity_agy_stitch_mcp_integration_prompt_format() [function:105], test_format_job_summary_flags_cancelled_github_mcp_write() [function:109], test_format_job_summary_does_not_false_positive_on_success() [function:118], test_format_job_summary_does_not_double_flag_failed_job() [function:128], test_grok_shell_denial_is_detected_even_when_wrapper_exits_zero() [function:138], test_cli_dispatch_dry_run_prints_preview_and_creates_no_job() [function:146], test_cli_dispatch_dry_run_empty_task_fails_closed_before_preview() [function:167], test_render_dispatch_preview_includes_task_digest_and_no_context_file() [function:188], test_render_dispatch_preview_includes_context_digest_when_context_md_exists() [function:207], test_render_dispatch_preview_skips_context_when_mode_none() [function:222], test_render_task_receipt_instruction_contains_marker_and_digest() [function:235], test_format_prompt_for_agent_prepends_receipt_instruction_for_all_agents() [function:244], test_render_instruction_receipt_instruction_contains_marker_and_filename() [function:256], test_format_prompt_for_agent_includes_instruction_receipt_instruction() [function:267], test_format_prompt_for_agent_adds_codex_gh_write_guardrail() [function:282], test_format_prompt_for_agent_omits_codex_gh_write_guardrail_by_default() [function:295]

`tests/test_dispatch_context_mode_hint.py` · 6 symbols
  test_context_mode_hint_fires_for_full_task_with_code_and_commit_message() [function:9], test_context_mode_hint_full_with_code_but_no_commit_message_returns_none() [function:25], test_context_mode_hint_full_with_commit_message_but_no_code_returns_none() [function:36], test_context_mode_hint_full_with_plain_text_returns_none() [function:42], test_context_mode_hint_task_mode_never_fires() [function:48], test_context_mode_hint_none_mode_never_fires() [function:59]

`tests/test_dispatch_cycle.py` · 5 symbols
  test_dispatch_stores_cycle() [function:7], test_dispatch_agent_attaches_fence_estimate() [function:40], test_dispatch_agent_fence_uses_prompt_estimate_with_context() [function:87], test_dispatch_agent_fence_uses_fallback_without_context() [function:132], test_dispatch_cycle_defaults_to_work() [function:177]

`tests/test_dispatch_github_identity.py` · 13 symbols
  test_resolve_dispatch_gh_token_uses_role_specific_app() [function:12], test_resolve_dispatch_gh_token_falls_back_to_synlynk_bot() [function:31], test_resolve_dispatch_gh_token_returns_none_when_cache_stale() [function:50], test_resolve_dispatch_gh_token_returns_none_when_nothing_provisioned() [function:66], test_resolve_dispatch_gh_token_uses_main_repo_apps_from_worktree() [function:75], test_resolve_github_apps_dir_prefers_cwd_directory() [function:108], test_resolve_github_apps_dir_falls_back_to_cwd_path_when_unavailable() [function:122], test_resolve_dispatch_gh_bot_login_uses_role_specific_app() [function:137], test_resolve_dispatch_gh_bot_login_returns_none_when_nothing_provisioned() [function:148], _dispatch_with_fake_popen() [function:157], test_dispatch_agent_injects_gh_token_when_requires_gh_write() [function:264], test_dispatch_agent_uses_pr_target_kind() [function:278], test_dispatch_agent_defaults_to_issue_target_kind() [function:291]

`tests/test_dispatch_local_agent.py` · 2 symbols
  TestDispatchFlagsForLocalAgent [class:11], TestCodexComposedFlags [class:45]

`tests/test_dispatch_model_routing.py` · 7 symbols
  test_ast_blast_radius_score_counts_all_graphify_relationships() [function:16], test_resolve_model_tier_uses_leaf_multi_file_and_reasoning_paths() [function:26], test_calculate_dispatch_impact_reads_graphify_reports() [function:32], test_tripartite_resolution_keeps_role_and_harness_separate() [function:51], test_explicit_model_and_tier_override_automatic_routing() [function:65], test_unknown_model_tier_fails_closed() [function:79], test_codex_dispatch_probes_config_toml_when_unspecified() [function:84]

`tests/test_dispatch_nudges.py` · 3 symbols
  test_print_pending_nudges_reads_config_gate() [function:6], test_print_pending_nudges_invokes_workspace_agent_when_enabled() [function:19], test_exec_command_calls_pending_nudge_hook() [function:26]

`tests/test_dispatch_session_threading.py` · 3 symbols
  test_insert_cost_row_inherits_session_id_from_job() [function:1], test_dispatch_agent_writes_session_id_to_daemon_jobs() [function:34], test_dispatch_cli_session_flag_overrides_active_marker() [function:82]

`tests/test_docs_sync.py` · 2 symbols
  test_generated_reference_doc_matches_taxonomy() [function:5], test_generated_readme_section_matches_taxonomy() [function:16]

`tests/test_doctor_identity_roles.py` · 5 symbols
  test_hc_identity_roles_warns_on_missing_provisioning() [function:7], test_hc_identity_roles_ok_when_all_provisioned() [function:20], _durable_agent() [function:34], test_hc_identity_roles_fails_durable_role_without_app_material() [function:49], test_hc_identity_roles_accepts_nested_app_material() [function:63]

`tests/test_doctor_product_store.py` · 3 symbols
  test_doctor_reads_product_store() [function:8], test_doctor_codex_catalog_matches_authenticated_config() [function:24], test_doctor_codex_catalog_warns_on_model_drift() [function:50]

`tests/test_doctor_todo_drift.py` · 4 symbols
  test_hc_todo_drift_in_health_checks_list() [function:10], test_hc_todo_drift_ok_when_synchronized() [function:14], test_hc_todo_drift_warns_on_split_path_divergence() [function:38], test_hc_todo_drift_warns_on_state_db_drift() [function:66]

`tests/test_e2e.py` · 23 symbols
  SYNLYNK_BIN [constant:25], PYTHON [constant:26], _seed_probe_row() [function:31], Cli [class:76], cli() [function:117], uninit_cli() [function:131], test_version_shows_synlynk() [function:140], test_help_exits_zero_and_lists_commands() [function:146], test_init_creates_project_structure() [function:153], test_init_force_reruns_without_error() [function:160], test_exec_echo_exits_zero() [function:169], test_exec_propagates_non_zero_exit_code() [function:175], test_exec_missing_command_returns_127() [function:180], test_exec_writes_telemetry_event() [function:185], test_sentinel_list_empty_on_fresh_project() [function:202], test_sentinel_list_shows_alert_after_write() [function:208], test_sentinel_clear_removes_all_alerts() [function:219], test_sentinel_clear_severity_removes_only_matching() [function:232], test_sentinel_clear_code_removes_only_matching() [function:245], test_exec_blocked_by_critical_alert() [function:262], test_exec_force_bypasses_critical_alert() [function:274], test_status_exits_zero_on_initialized_project() [function:288], test_status_output_contains_expected_sections() [function:293]

`tests/test_ecosystem_status.py` · 24 symbols
  db() [function:15], _write_config() [function:24], _seed_probe_row() [function:31], test_harness_status_table_exists() [function:52], test_cycle_capability_table_exists() [function:59], test_harness_status_columns() [function:66], test_cycle_capability_columns() [function:79], test_load_config_defaults_dispatch_mode() [function:85], test_config_set_dispatch_mode() [function:93], test_classify_task_type() [function:104], test_estimate_dispatch_tokens() [function:112], test_get_avg_tool_calls_default() [function:125], test_compute_cycle_capability_upserts() [function:131], test_harness_snapshot_empty() [function:151], test_harness_snapshot_loads_rows() [function:158], test_format_status_terminal_structure() [function:172], test_format_status_terminal_shows_rates_updated_date() [function:186], test_format_status_terminal_shows_rates_never_updated_warning() [function:195], test_format_status_json_valid() [function:204], test_format_status_json_includes_rates_updated_at() [function:215], test_cmd_status_outputs_sections() [function:224], test_cmd_status_json_output() [function:243], test_cmd_status_json_output_reads_rates_from_file() [function:261], test_cmd_status_json_output_rates_null_when_no_file() [function:288]

`tests/test_events.py` · 18 symbols
  test_approval_tickets_table_exists() [function:7], test_emit_event_writes_row_and_returns_id() [function:18], test_emit_awaiting_approval_event_recorded() [function:39], test_record_goal_suggestion_writes_telemetry_event() [function:58], test_pending_events_returns_only_events_after_checkpoint() [function:75], test_pending_events_ignores_other_event_types() [function:86], test_advance_checkpoint_never_moves_backward() [function:95], test_migration_adds_link_status_and_skip_reason_columns() [function:106], test_scan_local_events_always_emits_cron_heartbeat() [function:115], test_scan_local_events_emits_pr_merged_from_gh_output() [function:125], test_scan_local_events_advances_own_checkpoint() [function:141], test_scan_local_events_emits_review_submitted_with_role_derived_from_bot_login() [function:151], test_scan_local_events_review_submitted_role_null_for_non_matching_login() [function:180], test_scan_local_events_review_submitted_no_duplicate_on_rescan() [function:203], test_cmd_events_tail_filters_by_type() [function:233], test_cmd_events_tail_respects_limit_and_orders_newest_first() [function:248], test_cmd_events_tail_with_no_type_shows_all_types() [function:263], test_scan_local_events_emits_spec_verified_when_pr_references_spec() [function:276]

`tests/test_examples.py` · 15 symbols
  test_greet_returns_a_friendly_message() [function:4], test_write_3_test_cases_for_a_general_scenario_happy_path() [function:8], test_write_3_test_cases_for_a_general_scenario_empty_input() [function:20], test_write_3_test_cases_for_a_general_scenario_missing_active_key() [function:24], test_active_items_handles_mixed_truthy_and_falsy_flag_values() [function:28], test_active_items_preserves_order_and_duplicate_ids_with_extra_metadata() [function:43], test_active_items_returns_a_single_active_item_unchanged() [function:56], test_active_items_returns_no_items_when_every_item_is_inactive() [function:62], test_active_items_preserves_metadata_on_selected_items() [function:72], test_active_items_returns_all_items_when_every_item_is_active() [function:82], test_active_items_returns_only_the_active_item_from_a_two_item_list() [function:88], test_active_items_keeps_the_input_order_of_active_items() [function:95], test_greet_handles_a_name_with_spaces() [function:105], test_greet_handles_an_empty_name() [function:109], test_greet_preserves_punctuation_in_a_name() [function:113]

`tests/test_fencing.py` · 7 symbols
  test_render_nudge_fence_includes_message_and_id() [function:10], test_render_nudge_fence_has_bordered_box_shape() [function:23], test_render_task_fence_estimate() [function:31], test_render_task_fence_actual_with_hints() [function:48], test_render_task_fence_no_label_defaults_to_command() [function:67], test_is_fenced_command_allowlisted() [function:80], test_is_fenced_command_missing_key_defaults_empty() [function:86]

`tests/test_first_win.py` · 2 symbols
  test_dispatch_first_win_task_creates_isolated_worktree() [function:9], test_dispatch_first_win_task_handles_git_failure() [function:19]

`tests/test_fleet_operability.py` · 21 symbols
  test_core_fleet_is_four() [function:17], test_proven_and_budget_defaults() [function:23], test_codex_builder_only_flag() [function:28], test_open_parser_rejects_local() [function:32], test_open_parser_accepts_core_fleet() [function:40], test_check_core_instruction_files_missing_codex() [function:50], test_find_nested_product_state_dbs() [function:62], test_doctor_hard_fail_ignores_tc5() [function:77], test_assert_not_nested_product_ledger_raises() [function:97], test_is_nested_worktree_state_path() [function:107], test_get_db_refuses_nested_primary_path() [function:118], test_no_unknown_terminal_label() [function:131], test_fleet_matrix_runs_table() [function:138], test_run_matrix_dry_marks_missing_instruction_red() [function:147], test_run_matrix_dry_codex_gh_write_na() [function:159], test_record_matrix_run() [function:171], test_selftest_matrix_flag_parsed() [function:189], test_selftest_matrix_budget_flag_parsed() [function:197], test_preflight_blocks_dispatch_helper() [function:206], test_tier_for_agent_experimental_and_supported() [function:244], test_live_matrix_budget_abort() [function:289]

`tests/test_fleet_scheduler.py` · 19 symbols
  scheduler_db() [function:12], test_stories_table_has_priority_and_readiness_columns() [function:32], test_priority_defaults_to_5_and_readiness_defaults_to_draft() [function:40], test_cmd_story_ready_sets_readiness_to_ready() [function:52], test_cmd_story_ready_all_marks_every_draft_story_ready() [function:66], test_cmd_story_draft_reverts_readiness_to_draft() [function:81], test_story_failed_agents_returns_empty_set_with_no_history() [function:95], test_story_failed_agents_returns_agents_from_failed_daemon_jobs() [function:104], test_story_retry_count_matches_failed_job_rows() [function:122], _seed_capability() [function:136], _seed_story() [function:152], test_plan_skips_draft_stories() [function:161], test_plan_assigns_ready_story_to_best_capability_agent() [function:176], test_plan_blocks_story_with_no_capability_candidates() [function:197], test_plan_blocks_story_when_all_candidates_quota_exhausted() [function:212], test_plan_respects_max_stories() [function:232], test_plan_decrements_fleet_headroom_across_batch_and_blocks_second_story() [function:251], test_plan_excludes_agent_that_previously_failed_this_story() [function:273], test_plan_blocks_story_past_retry_cap() [function:300]

`tests/test_ftue_e2e.py` · 1 symbols
  test_run_ftue_journey_e2e() [function:8]

`tests/test_gap_scanner.py` · 3 symbols
  test_scan_workspace_gaps_missing_tests() [function:8], test_generate_governs_goal_compliance() [function:18], test_scan_workspace_gaps_missing_health_check() [function:26]

`tests/test_get_db_sandbox_fallback.py` · 13 symbols
  test_get_db_falls_back_on_erofs_oserror() [function:20], test_get_db_falls_back_on_permissionerror() [function:56], test_get_db_falls_back_on_sqlite_operational_error() [function:87], test_get_db_reraise_when_fallback_also_fails() [function:121], test_get_db_fails_closed_without_implicit_fallback() [function:138], test_get_db_never_reuses_malformed_fallback_when_explicitly_enabled() [function:157], test_get_db_override_env_var_used_verbatim() [function:181], test_get_db_override_wins_even_when_primary_would_succeed() [function:199], test_get_db_override_failure_propagates_without_fallback() [function:217], test_get_db_override_bypasses_nested_worktree_guard() [function:237], test_get_db_unset_override_preserves_existing_behavior() [function:253], test_get_db_rejects_readonly_primary_before_returning_connection() [function:269], test_get_db_failed_primary_probe_preserves_db_and_sidecars() [function:295]

`tests/test_gh_role.py` · 4 symbols
  test_cmd_gh_runs_gh_with_role_token() [function:6], test_cmd_gh_strips_leading_double_dash() [function:29], test_cmd_gh_fails_closed_without_token() [function:47], test_cmd_gh_rejects_unknown_role() [function:62]

`tests/test_gh_shim.py` · 9 symbols
  _fake_gh() [function:7], _run_shim() [function:14], test_shim_non_harness_execs_real_gh() [function:27], test_shim_harness_without_token_refuses_real_gh() [function:35], test_shim_harness_with_allow_host_execs_real_gh() [function:44], test_shim_harness_with_token_execs_real_gh() [function:57], test_shim_does_not_classify_ci_as_harness() [function:70], test_shim_routes_known_role_to_synlynk() [function:76], test_gh_shim_cli_prints_installable_environment() [function:95]

`tests/test_gh_verify.py` · 25 symbols
  test_gh_write_verified_true_when_issue_closed() [function:9], test_gh_write_verified_false_when_issue_still_open() [function:18], test_gh_write_verified_true_when_pr_merged() [function:26], test_gh_write_verified_merged_retries_delayed_state() [function:35], test_gh_write_verified_true_when_pr_open_or_created() [function:56], test_gh_write_verified_unknown_when_target_none() [function:65], test_gh_write_verified_unknown_when_gh_cli_errors() [function:69], test_gh_write_verified_unknown_when_gh_cli_times_out() [function:77], test_gh_write_verified_rejects_malformed_target() [function:85], test_parse_iso8601_handles_z_suffix() [function:89], test_parse_iso8601_handles_offset_suffix() [function:97], test_parse_iso8601_coerces_naive_timestamp_to_utc() [function:104], test_parse_iso8601_returns_none_for_garbage() [function:110], test_parse_iso8601_returns_none_for_none() [function:114], test_parse_iso8601_converts_positive_offset_to_utc() [function:118], test_parse_iso8601_returns_none_for_invalid_date() [function:124], test_gh_write_verified_returns_none_for_unknown_expectation() [function:128], test_gh_write_verified_review_posted_true_after_since_no_author_filter() [function:136], test_gh_write_verified_handles_aware_entry_and_naive_since() [function:154], test_gh_write_verified_handles_naive_entry_and_aware_since() [function:169], test_gh_write_verified_review_posted_false_when_only_stale_entry() [function:184], test_gh_write_verified_review_posted_true_with_matching_author() [function:201], test_gh_write_verified_review_posted_true_when_author_omits_bot_suffix() [function:221], test_gh_write_verified_review_posted_true_when_naive_since_is_local() [function:242], test_gh_write_verified_pr_open_resolves_issue_number_to_created_pr() [function:271]

`tests/test_gh_write_call_site_threading.py` · 3 symbols
  test_check_job_stall_passes_since_and_expect_author_and_expect() [function:9], test_apply_gh_write_verification_uses_data_driven_expect() [function:49], test_apply_gh_write_verification_defaults_expect_to_closed() [function:76]

`tests/test_gh_write_guard.py` · 5 symbols
  _TERMINAL_STATUS_FUNCTIONS [constant:20], _DOCUMENTED_EXCEPTIONS [constant:28], _source_calls_name() [function:35], test_all_terminal_status_functions_consult_gh_write_verified() [function:46], test_guard_itself_fails_when_a_function_skips_the_check() [function:66]

`tests/test_github_app_auth.py` · 16 symbols
  test_build_jwt_signing_input_has_correct_header_and_claims() [function:15], test_resolve_openssl_path_raises_clear_error_when_missing() [function:26], test_resolve_openssl_path_caches_after_first_resolution() [function:35], test_read_cached_installation_token_returns_fresh_token() [function:47], test_token_cache_defaults_to_repo_common_apps_dir_from_worktree() [function:60], test_refresh_installation_token_defaults_to_repo_common_apps_dir_from_worktree() [function:80], test_read_cached_installation_token_returns_none_when_stale() [function:106], test_read_cached_installation_token_returns_none_when_missing() [function:119], test_read_cached_installation_token_returns_none_when_corrupt() [function:128], test_refresh_installation_token_writes_cache_file_with_0600() [function:139], test_refresh_installation_token_persists_redaction_cache() [function:161], test_refresh_installation_token_round_trips_into_read_cache() [function:180], test_load_redaction_tokens_omits_expired_entries() [function:196], test_refresh_installation_token_writes_to_explicit_apps_dir() [function:212], test_resolve_private_key_path_from_worktree() [function:231], test_refresh_installation_token_resolves_relative_pem_path_to_absolute() [function:259]

`tests/test_goal_tag_parsing.py` · 2 symbols
  test_parse_roadmap_md_extracts_goal_tag() [function:4], test_parse_roadmap_md_goal_id_none_when_untagged() [function:10]

`tests/test_goals.py` · 10 symbols
  test_goals_table_created() [function:5], test_goal_contributions_table_created() [function:12], test_stories_and_arcs_have_goal_id_column() [function:19], test_goal_create_returns_goal_id_and_persists() [function:28], test_goal_list_prints_active_goals() [function:50], test_goal_link_sets_primary_goal_id_on_story() [function:58], test_goal_link_secondary_writes_contribution_not_primary() [function:69], test_goal_status_reports_story_counts() [function:86], test_cli_goal_create_and_list() [function:104], test_context_from_db_includes_active_goal() [function:121]

`tests/test_graphify_skills.py` · 2 symbols
  test_all_four_graphify_skills_exist_and_have_valid_frontmatter() [function:5], test_skill_roles_and_tools_documented() [function:47]

`tests/test_grok_write_guard.py` · 5 symbols
  test_task_requires_write_variations() [function:12], test_check_grok_sandbox_write_capability_env_override() [function:21], test_check_grok_sandbox_write_capability_disk_probe() [function:30], test_grok_write_guard_failover_when_denied() [function:43], test_grok_write_guard_raises_when_forced() [function:72]

`tests/test_handoff_cycle_map.py` · 1 symbols
  test_task_to_cycle_uses_governs_keys() [function:4]

`tests/test_handover.py` · 4 symbols
  test_calculate_drain_horizon_no_active_story() [function:20], test_calculate_drain_horizon_with_active_story() [function:33], test_execute_home_handover_drain_flow() [function:59], test_worktree_identity_slug_resolution() [function:97]

`tests/test_harness_compatibility.py` · 16 symbols
  _make_stub_cli() [function:5], test_probe_fastpath_skips_deep_probe_when_hash_matches() [function:20], test_probe_writes_harness_records_on_new_version() [function:45], test_probe_appends_history_on_version_change() [function:60], test_tc1_detects_pipe_hang_and_records_pty_required() [function:82], test_tc2_flags_invalid_flag_as_noncompliant() [function:99], test_tc3_marks_unreachable_endpoint() [function:114], test_palette_scan_populates_commands() [function:126], test_palette_marks_removed_commands() [function:149], test_fence_upsert_replaces_existing_fence() [function:172], test_fence_upsert_appends_when_missing() [function:185], test_fence_upsert_skips_missing_file() [function:197], test_fence_preserves_surrounding_bytes() [function:203], test_fence_upsert_is_noop_when_content_unchanged() [function:217], test_fence_upsert_rewrites_when_version_changes_but_body_same() [function:236], test_preflight_fires_drift_sentinel_on_version_change() [function:254]

`tests/test_heal.py` · 5 symbols
  test_diagnostics_normalizes_scan_findings() [function:9], test_auto_merge_is_fail_closed_when_qa_is_red() [function:15], test_auto_merge_reaps_worktree_after_successful_merge() [function:19], test_auto_merge_marks_linked_story_done() [function:30], test_auto_merge_does_not_reach_gh_merge_when_role_is_unauthorized() [function:50]

`tests/test_heal_cycles.py` · 5 symbols
  test_detect_import_cycles_identifies_circular_dependencies() [function:8], test_detect_import_cycles_returns_empty_when_no_cycles() [function:28], test_detect_import_cycles_handles_missing_graph() [function:46], test_heal_import_cycles_creates_stories() [function:51], test_cmd_heal_cycles_cli() [function:81]

`tests/test_home_cmd.py` · 2 symbols
  test_cmd_home_displays_status() [function:8], test_cmd_home_switches_harness() [function:24]

`tests/test_housekeeping.py` · 5 symbols
  _write_config() [function:10], _write_stub() [function:37], test_daily_housekeeping_triggers_on_new_day_and_updates_date() [function:52], test_daily_housekeeping_does_not_rerun_same_day() [function:79], test_daily_housekeeping_is_silent_when_nothing_to_do() [function:102]

`tests/test_hud_buffer.py` · 4 symbols
  test_initial_render_emits_full_frame() [function:9], test_unchanged_lines_not_re_emitted() [function:18], test_clear_resets_previous_frame() [function:29], test_line_truncated_to_col_width() [function:39]

`tests/test_hud_cycles.py` · 3 symbols
  test_cycles_is_governs_seven_stages() [function:6], test_cycle_colours_covers_every_cycle() [function:10], test_cycle_summary_defaults_unset_job_to_execute() [function:14]

`tests/test_hud_errors.py` · 2 symbols
  test_render_error_shows_message() [function:9], test_narrow_terminal_shows_warning() [function:17]

`tests/test_hud_integration.py` · 5 symbols
  REALISTIC_JOBS [constant:11], test_full_ambient_hud_renders_without_exception() [function:29], test_live_renderer_all_cycles() [function:52], test_platform_expanded_header() [function:67], test_no_jobs_renders_idle_state() [function:82]

`tests/test_hud_live.py` · 6 symbols
  ACTIVE_JOBS [constant:5], make_live() [function:10], test_live_renders_job_cards() [function:14], test_live_shows_empty_state_when_no_jobs() [function:21], test_live_header_shows_live_indicator() [function:27], test_live_footer_shows_count_and_hint() [function:32]

`tests/test_hud_renderer.py` · 11 symbols
  CYCLE_SUMMARY [constant:5], make_renderer() [function:15], test_render_header_collapsed_fits_one_line() [function:19], test_render_header_expanded_takes_multiple_rows() [function:26], test_render_sidebar_marks_active_cycle() [function:31], test_render_sidebar_contains_all_cycles() [function:38], ACTIVE_JOBS [constant:47], RECENT_JOBS [constant:54], test_render_right_panel_shows_agent_names() [function:60], test_render_right_panel_idle_shows_placeholder() [function:73], test_render_right_panel_shows_recent_jobs() [function:85]

`tests/test_hud_snapshot.py` · 8 symbols
  SAMPLE_JOBS [constant:7], make_snapshot() [function:41], test_active_jobs_returns_running() [function:49], test_active_jobs_for_cycle() [function:56], test_recent_jobs() [function:64], test_cycle_summary() [function:71], test_missing_jobs_file() [function:80], test_elapsed_seconds() [function:88]

`tests/test_identity_file_permissions.py` · 4 symbols
  test_gitignore_excludes_github_apps_directory() [function:9], test_hc_identity_file_perms_warns_on_loose_permissions() [function:31], test_hc_identity_file_perms_ok_when_0600() [function:46], test_hc_identity_file_perms_ok_when_no_apps_dir() [function:63]

`tests/test_identity_init_role.py` · 12 symbols
  test_build_app_manifest_url_encodes_role_and_project() [function:17], test_build_app_manifest_url_uses_org_or_personal_endpoint() [function:36], test_resolve_repo_owner_classifies_org_and_user() [function:49], test_resolve_repo_owner_falls_back_on_gh_failure() [function:62], test_cmd_identity_init_role_retries_taken_app_name() [function:72], test_manifest_callback_server_captures_code() [function:118], test_manifest_callback_server_times_out_without_code() [function:131], test_build_app_manifest_url_resolves_project_from_git_root_and_caps_name_length() [function:140], test_resolve_project_slug_uses_identity_slug_override() [function:160], test_resolve_project_slug_falls_back_without_identity_slug() [function:171], test_cmd_identity_init_role_fails_closed_if_already_provisioned() [function:180], test_cmd_identity_init_role_resumes_at_confirmation_when_app_created_but_not_installed() [function:220]

`tests/test_identity_init_role_token_seed.py` · 1 symbols
  test_identity_init_role_resuming_branch_seeds_token_cache() [function:9]

`tests/test_identity_list.py` · 1 symbols
  test_cmd_identity_list_reports_provisioned_and_missing() [function:8]

`tests/test_identity_roles.py` · 4 symbols
  test_load_declared_roles_defaults_when_file_missing() [function:9], test_load_declared_roles_reads_yaml_list() [function:15], test_load_declared_roles_ignores_malformed_file() [function:24], test_load_declared_roles_reads_yaml_dict() [function:31]

`tests/test_impact.py` · 4 symbols
  test_calculate_impact_returns_callers_and_tests() [function:6], test_calculate_impact_fallback_when_no_graph() [function:28], test_calculate_impact_by_file() [function:36], test_cmd_impact_cli() [function:58]

`tests/test_init_business_goals.py` · 1 symbols
  test_fallback_roadmap_includes_business_goals_section() [function:1]

`tests/test_init_rollback.py` · 5 symbols
  _init_git_repo() [function:8], _stub_init_inputs() [function:14], test_init_preserves_existing_claude_content_on_success() [function:30], test_init_rolls_back_on_mid_operation_failure() [function:48], test_init_dry_run_writes_nothing() [function:68]

`tests/test_install.py` · 2 symbols
  test_check_install_prerequisites_all_satisfied() [function:9], test_check_install_prerequisites_git_missing() [function:20]

`tests/test_install_sh.py` · 2 symbols
  ROOT [constant:7], test_install_sh_without_pipx_prints_guidance_and_exits_nonzero() [function:10]

`tests/test_instruction_reach.py` · 27 symbols
  test_agy_baseline_replaces_gemini() [function:8], test_gemini_md_template_has_no_transition_note() [function:14], test_build_templates_includes_lifecycle_checkpoint_section() [function:23], test_extract_synlynk_section_html_markers() [function:35], test_extract_synlynk_section_hash_markers() [function:41], test_extract_synlynk_section_none_marker_returns_whole() [function:47], test_extract_synlynk_section_ignores_inline_end_marker() [function:53], test_extract_synlynk_section_returns_none_when_absent() [function:70], test_compute_section_sha_is_deterministic() [function:75], test_write_instruction_file_creates_new_file() [function:82], test_write_instruction_file_appends_to_existing_no_markers() [function:93], test_write_instruction_file_replaces_existing_section() [function:104], test_write_instruction_file_hash_markers() [function:117], test_write_instruction_file_none_marker_owns_file() [function:127], test_write_instruction_file_creates_parent_dirs() [function:137], test_build_cursor_mdc_has_frontmatter() [function:144], test_build_copilot_instructions_no_frontmatter() [function:153], test_build_windsurf_rules_is_terse() [function:161], test_write_instruction_manifest_creates_file() [function:170], test_load_instruction_manifest_returns_empty_when_absent() [function:184], test_manifest_sha_covers_only_synlynk_section() [function:191], test_init_writes_cursor_rules_when_cursor_dir_exists() [function:205], test_init_skips_cursor_when_no_cursor_dir() [function:222], test_init_appends_to_existing_copilot_instructions() [function:236], test_manifest_written_after_init() [function:255], test_check_instruction_drift_detects_section_change() [function:273], test_check_instruction_drift_ignores_user_content_change() [function:295]

`tests/test_instructions.py` · 16 symbols
  test_install_pre_commit_hook_writes_executable_hook() [function:7], test_install_pre_commit_hook_appends_to_existing_shebang_hook() [function:22], test_install_pre_commit_hook_rejects_non_shebang_hook() [function:40], test_tier0_fixture_only_gets_tier0_and_gateway_phrases() [function:53], test_tier2_fixture_gets_tier0_through_tier2_phrases() [function:62], test_render_lifecycle_checkpoint_section_returns_fixed_block() [function:71], test_instructions_status_pre_commit_exits_on_drift() [function:92], test_register_backfills_existing_fenced_file_without_rewriting_content() [function:130], test_register_is_idempotent_and_scans_known_fenced_targets() [function:159], test_register_sniffs_tool_from_marker_on_nonstandard_path() [function:183], test_extract_instruction_version_html_marker() [function:200], test_extract_instruction_version_hash_marker() [function:207], test_extract_instruction_version_harness_marker() [function:214], test_extract_instruction_version_missing() [function:224], test_instruction_templates_prohibit_direct_todo_edits() [function:231], test_instruction_templates_have_symmetric_dual_mode_protocol() [function:260]

`tests/test_jobs.py` · 26 symbols
  test_check_scope_compliance_all_files_match_single_glob() [function:11], test_check_scope_compliance_files_match_any_of_several_globs() [function:20], test_check_scope_compliance_file_matching_no_glob_is_violation() [function:29], test_check_scope_compliance_empty_scope_paths_is_always_compliant() [function:38], test_check_task_receipt_ok_when_marker_is_first_line() [function:45], test_check_task_receipt_late_when_marker_present_but_not_first() [function:52], test_check_task_receipt_mismatch_when_first_line_wrong_digest() [function:59], test_check_task_receipt_absent_when_no_marker_anywhere() [function:66], test_check_task_receipt_returns_none_for_empty_log_or_digest() [function:73], test_check_instruction_receipt_ok() [function:80], test_check_instruction_receipt_mismatch() [function:87], test_check_instruction_receipt_none_reported() [function:94], test_check_instruction_receipt_absent() [function:101], test_check_instruction_receipt_empty() [function:108], test_instruction_receipt_absent_is_not_trusted_for_unattended_merge() [function:115], test_instruction_receipt_trust_requires_expected_version_match() [function:122], test_classify_task_delivery_hard_fail_when_no_marker_and_no_activity() [function:131], test_classify_task_delivery_warn_when_no_marker_but_activity_present() [function:138], test_classify_task_delivery_clean_when_receipt_ok() [function:145], test_classify_task_delivery_clean_when_receipt_status_none() [function:152], test_task_sha256_and_preview_returns_none_for_falsy_task() [function:159], test_task_sha256_and_preview_computes_digest_and_collapses_whitespace() [function:166], test_inspect_worktree_git_state_includes_changed_files_from_diff_and_status() [function:178], test_dispatch_ready_jobs_prints_fence_when_schedule_allowlisted() [function:209], test_dispatch_ready_jobs_stays_queued_when_all_exhausted() [function:264], test_write_job_summary_creates_file() [function:297]

`tests/test_launch.py` · 30 symbols
  test_cycle_colors_constant_exists() [function:9], test_cycle_rename_migration_idempotent() [function:15], test_scan_returns_test_ratio() [function:23], test_scan_returns_has_ci_false_when_absent() [function:32], test_scan_returns_readme_word_count() [function:38], test_launch_task_templates_count() [function:45], test_launch_task_templates_have_required_fields() [function:49], test_launch_task_templates_core_ids() [function:57], test_launch_tasks_are_limited_to_core_and_tier1_primary_commands() [function:63], test_auto_launch_config_default_true() [function:74], test_cmd_launch_dry_run_prints_tasks_no_dispatch() [function:80], test_cmd_launch_list_prints_only_visible_templates() [function:90], test_wizard_calls_cmd_launch_when_auto_launch_true() [function:102], test_wizard_skips_cmd_launch_when_auto_launch_false() [function:127], _minimal_scan() [function:140], test_template_matches_core_always_eligible() [function:157], test_template_matches_add_tests_triggered() [function:164], test_template_matches_add_tests_not_triggered() [function:170], test_template_matches_setup_ci_triggered() [function:176], test_template_matches_type_safety_python_only() [function:182], test_add_tests_trigger_uses_gap_count() [function:189], test_type_safety_trigger_uses_typed_pct() [function:199], test_reduce_complexity_template_exists() [function:216], test_fix_churn_debt_template_exists() [function:228], test_refactor_module_template_exists() [function:238], test_select_tasks_returns_max_5() [function:248], test_select_tasks_core_always_first() [function:258], test_select_tasks_empty_scan_returns_core_3() [function:268], test_render_prompt_substitutes_all_variables() [function:280], test_render_prompt_missing_variable_uses_empty_string() [function:299]

`tests/test_launch_templates.py` · 2 symbols
  test_every_template_cycle_is_a_governs_key() [function:5], test_specific_template_remaps() [function:10]

`tests/test_layered_topology_dispatch.py` · 5 symbols
  test_codex_review_with_local_write_grant_uses_workspace_write() [function:18], test_nested_worktree_path_resolution_prevents_outer_deletion() [function:40], test_reap_zombie_worktree_safety_guard_rejects_parent_dir() [function:54], test_maybe_open_worktree_pr_skips_when_no_diff_or_skip_phrases() [function:66], test_resolve_default_base_branch_prefers_unstable() [function:94]

`tests/test_local_agent.py` · 9 symbols
  TestLocalAgentConfigEditFormat [class:11], TestLoadLocalConfig [class:21], TestPinnedModel [class:44], TestHealthCheck [class:60], TestLocalDispatchModelFlags [class:84], TestLocalDispatchModelFlagsProviderPrefix [class:109], TestLocalDispatchStarterTierGuardrails [class:148], TestCmdLocalDoctorAiderCheck [class:211], TestHealthCheckApiKey [class:263]

`tests/test_local_agent_ab_test.py` · 6 symbols
  TestBuildTempConfig [class:17], TestConfigReadWrite [class:52], TestBuildResultRow [class:62], _FakeCompletedProcess [class:83], TestRunAbCase [class:89], TestAppendResult [class:140]

`tests/test_local_agent_concurrency.py` · 3 symbols
  _db_with_running_jobs() [function:15], TestLocalConcurrencyGuard [class:29], TestSchedulerLocalConcurrency [class:55]

`tests/test_local_agent_hardware.py` · 5 symbols
  _LOCAL_CONFIG [constant:23], _make_local_config() [function:35], _LocalHardwareBase [class:43], TestRealOmlxHealthCheck [class:63], TestAiderSubprocessEndToEnd [class:71]

`tests/test_local_agent_seed.py` · 2 symbols
  _fresh_db() [function:13], TestSeedLocalCapabilityEnvelope [class:33]

`tests/test_local_http_auth.py` · 4 symbols
  test_ensure_local_token_creates_file_with_0600() [function:11], test_ensure_local_token_tightens_existing_permissions() [function:21], test_authorize_rejects_missing_and_wrong_token() [function:30], test_local_origin_allows_cli_and_localhost_rejects_foreign() [function:44]

`tests/test_logs_token_redaction.py` · 1 symbols
  test_cmd_logs_redacts_active_token_values() [function:7]

`tests/test_magic_heal.py` · 4 symbols
  test_discover_ast_gaps() [function:12], test_generate_magic_test_content() [function:24], test_run_magic_heal_dry_run() [function:38], test_run_magic_heal_e2e() [function:49]

`tests/test_marketing.py` · 10 symbols
  test_split_frontmatter() [function:19], test_parse_yaml_frontmatter() [function:31], test_validate_blog_post_frontmatter_valid() [function:52], test_validate_blog_post_frontmatter_missing_keys() [function:76], test_validate_blog_post_frontmatter_invalid_tags() [function:95], test_extract_social_changelog_snippets() [function:111], test_update_blog_index() [function:144], test_validate_all_blog_posts() [function:186], test_sync_pr_blog_post_creates_post() [function:211], test_cmd_marketing_sync_pr_cli() [function:247]

`tests/test_marketing_workflow.py` · 5 symbols
  WORKFLOW [constant:4], test_marketing_sync_uses_a_protected_branch_pr_flow() [function:7], test_marketing_sync_is_serialized_and_idempotent() [function:32], test_required_checks_support_automation_branch_dispatch() [function:44], test_marketing_sync_stages_blog_and_social_draft_outputs() [function:50]

`tests/test_media.py` · 5 symbols
  test_generate_svg_diagram() [function:10], test_generate_og_card() [function:24], test_cmd_media_generate_all() [function:43], test_cmd_media_generate_diagram_only() [function:51], test_cmd_media_generate_og_only() [function:59]

`tests/test_merge_class.py` · 9 symbols
  test_is_docs_only_change_true_for_docs_dir_files() [function:4], test_is_docs_only_change_true_for_root_markdown() [function:8], test_is_docs_only_change_true_for_project_docs() [function:12], test_is_docs_only_change_false_for_project_docs_config() [function:16], test_is_docs_only_change_false_when_any_code_file_present() [function:20], test_is_docs_only_change_false_for_ci_config() [function:24], test_is_docs_only_change_false_for_synlynk_config() [function:28], test_is_docs_only_change_false_for_empty_change_list() [function:32], test_is_docs_only_change_true_for_nested_markdown_outside_docs_dir() [function:36]

`tests/test_merge_oracle.py` · 4 symbols
  test_green_checks_allow_merge() [function:3], test_failed_unverified_hud_does_not_block_green_ci() [function:14], test_red_qa_gate_blocks_merge() [function:25], test_pr_check_failure_blocks_merge() [function:35]

`tests/test_mesh_conflict.py` · 12 symbols
  test_extract_file_ast_symbols() [function:20], GLOBAL_VAR [constant:25], helper_func() [function:27], async_fetch() [async_function:30], ServiceManager [class:33], test_parse_diff_line_ranges() [function:54], test_map_diff_to_ast_symbols() [function:74], func_two() [function:78], App [class:81], test_detect_worktree_ast_conflicts_disjoint_and_conflict() [function:99], test_cmd_multirepo_mesh_conflicts_json() [function:144], test_merge_fleet_graphs_and_inferred_edges() [function:161]

`tests/test_migrate.py` · 21 symbols
  test_migrate_db_creates_new_tables() [function:10], test_stories_has_gh_issue_column() [function:26], test_parse_memory_md_sections() [function:35], test_parse_roadmap_md_arcs_and_phases() [function:54], test_parse_costs_md_rows() [function:78], test_parse_devlog_file_entries() [function:91], test_parse_todo_metadata() [function:113], test_is_migrated_false_without_sentinel() [function:128], test_is_migrated_true_with_sentinel() [function:134], test_synlynk_project_docs_dir_returns_path() [function:141], test_dr_sync_copies_file() [function:147], test_dr_sync_silent_skip_if_path_missing() [function:161], _make_project_docs() [function:172], _seed_stories() [function:199], _init_git_repo() [function:210], test_migrate_dry_run_imports_nothing() [function:216], test_migrate_imports_all_tables() [function:229], test_migrate_imports_goal_id_on_roadmap_arcs() [function:246], test_migrate_copies_to_synlynk_project_docs() [function:269], test_migrate_writes_sentinel() [function:283], test_migrate_idempotent() [function:294]

`tests/test_models.py` · 6 symbols
  test_builtin_catalog_has_entitlement_and_geometry() [function:7], test_builtin_catalog_uses_current_remote_models_and_preserves_local_models() [function:20], test_model_registry_persists_and_queries() [function:40], test_cli_probe_is_safe_when_binary_is_missing() [function:55], test_ollama_response_becomes_zero_cost_local() [function:62], test_model_commands_seed_and_render_json() [function:69]

`tests/test_models_catalog.py` · 4 symbols
  test_load_model_catalog_default() [function:15], test_load_model_catalog_fallback_on_missing() [function:69], test_builtin_codex_catalog_matches_current_account_model() [function:77], test_get_models_from_catalog() [function:83]

`tests/test_modularise.py` · 5 symbols
  test_constants_importable_from_package() [function:4], test_upgrade_symbols_importable_from_package() [function:12], test_sentinel_symbols_importable_from_package() [function:23], test_probe_symbols_importable_from_package() [function:37], test_dispatch_symbols_importable_from_package() [function:57]

`tests/test_multirepo_graph.py` · 4 symbols
  test_merge_fleet_graphs_combines_multiple_repos() [function:7], test_merge_fleet_graphs_skips_missing_directories() [function:31], test_write_global_graph() [function:38], test_cmd_multirepo_mesh_cli() [function:50]

`tests/test_multitrack_quota.py` · 4 symbols
  db_conn() [function:16], test_resolve_harness_track() [function:26], test_multitrack_quota_isolation() [function:39], test_multitrack_migration_existing_db() [function:89]

`tests/test_muse_harness.py` · 5 symbols
  test_muse_baseline_schema_tc0() [function:14], test_muse_dispatch_flags_and_command_construction() [function:37], test_muse_prompt_formatting() [function:92], test_muse_structured_token_extraction() [function:114], test_muse_probe_agent() [function:150]

`tests/test_notifier_slack.py` · 3 symbols
  test_format_message_for_dispatch() [function:7], test_post_to_webhook_sends_payload() [function:19], test_run_once_posts_matching_events_only() [function:31]

`tests/test_observatory.py` · 6 symbols
  _write_json() [function:8], test_build_snapshot_returns_empty_on_missing_files() [function:13], test_build_snapshot_active_jobs_included() [function:25], test_build_snapshot_rollups_sum_cost() [function:55], test_render_observatory_panel_no_crash() [function:92], test_render_observatory_panel_shows_job_id() [function:102]

`tests/test_onboarding_safety.py` · 7 symbols
  git_repo() [function:21], test_guard_dirty_worktree_clean_tree() [function:49], test_guard_dirty_worktree_dirty_tree() [function:57], test_cmd_wizard_init_speed_and_charters() [function:92], test_find_top_scan_finding_hygiene_and_coverage() [function:129], test_first_win_auto_remediation_dispatch() [function:143], test_prompt_first_win_remediation() [function:158]

`tests/test_pack.py` · 5 symbols
  test_cut_to_token_budget() [function:7], test_synthesize_context_pack_extracts_target_symbols() [function:15], test_synthesize_context_pack_returns_empty_when_no_graph() [function:35], test_format_prompt_for_agent_injects_pack_on_turn_1() [function:40], test_cmd_pack_cli() [function:67]

`tests/test_packaging.py` · 7 symbols
  test_detect_install_type_pipx() [function:11], test_detect_install_type_pip() [function:23], test_detect_install_type_script() [function:33], test_detect_install_type_unknown() [function:53], test_run_upgrade_pipx_success() [function:67], test_run_upgrade_pipx_failure() [function:84], test_run_upgrade_script_prints_pipx_migration() [function:97]

`tests/test_parity.py` · 13 symbols
  test_detect_project_stack_node() [function:15], test_detect_project_stack_go() [function:24], test_detect_project_stack_python() [function:32], test_detect_project_stack_mixed() [function:40], test_parse_directive_fences_with_both_fences() [function:50], test_parse_directive_fences_with_no_fences() [function:82], test_inject_sop_fences_preserves_user_content() [function:93], test_ensure_recursive_gitignore() [function:123], test_generate_stack_policy_node() [function:134], test_run_parity_remediation_dry_run() [function:147], test_run_parity_remediation_live() [function:171], test_check_fleet_parity_detects_drift() [function:204], test_doctor_hc_fleet_parity_runs() [function:212]

`tests/test_payment_models.py` · 12 symbols
  test_load_config_defaults_payment_models_to_empty_dict() [function:10], test_load_config_preserves_existing_payment_models_section() [function:18], test_load_config_backfills_payment_models_into_existing_config_without_section() [function:44], test_migrate_db_creates_credit_grants_table() [function:59], test_migrate_db_credit_grants_creation_is_idempotent() [function:85], _write_config() [function:106], test_resolve_payment_value_pay_as_you_go_matches_api_equivalent() [function:115], test_resolve_payment_value_subscription_within_quota_is_free() [function:128], test_resolve_payment_value_subscription_overage_bills_only_the_excess() [function:152], test_resolve_payment_value_subscription_bills_marginal_overage_not_cumulative() [function:197], test_resolve_payment_value_credit_grant_consumes_balance() [function:250], test_resolve_payment_value_credit_grant_falls_back_when_exhausted() [function:279]

`tests/test_platform_ops.py` · 16 symbols
  test_collect_platform_report_shape() [function:19], test_format_platform_report_contains_layers() [function:29], test_ops_cli_parser() [function:39], test_cmd_ops_report_exit_1_when_ops_red() [function:48], test_cmd_ops_report_exit_0_when_ops_green() [function:65], test_format_platform_report_includes_context_mode_rollup() [function:81], test_aggregate_dispatch_context_splits_success_and_cost() [function:120], _MULTI_MONTH_SENTINEL [constant:149], test_parse_sentinel_line_ts_bracket_format() [function:167], test_is_sentinel_critical_line_requires_alert_bullet() [function:174], test_count_sentinel_stale_history_does_not_inflate_window() [function:193], test_count_sentinel_recent_window_counts_only_in_range() [function:205], test_count_sentinel_24h_window_excludes_36h_old() [function:218], test_collect_platform_report_windowed_sentinel_signals() [function:230], test_collect_only_stale_sentinel_is_ops_green_for_signals() [function:266], test_format_platform_report_includes_jobs_missing_cost() [function:293]

`tests/test_pm_agent.py` · 11 symbols
  test_load_config_reads_json() [function:17], test_resolve_decide_panel_auto_returns_all_known_harnesses() [function:36], test_resolve_decide_panel_explicit_list() [function:41], test_compose_prompt_includes_segments_competitors_panel_labels() [function:46], test_invoke_headless_claude_builds_expected_command() [function:71], test_invoke_headless_claude_nonzero_exit_reported() [function:90], _write_seed_config() [function:98], test_cmd_pm_sweep_dry_run_does_not_invoke_subprocess() [function:111], test_cmd_pm_sweep_real_run_parses_summary() [function:122], test_cmd_pm_sweep_real_run_failure_exits_nonzero() [function:138], test_cmd_pm_sweep_malformed_output_exits_nonzero() [function:148]

`tests/test_pm_sweep_watchdog.py` · 6 symbols
  test_extract_radar_opportunities_defaults() [function:21], test_save_radar_opportunities() [function:36], test_cmd_pm_sweep_radar_integration() [function:58], test_hc_spof_audit() [function:79], test_hc_memory_leak() [function:103], test_doctor_health_checks_includes_spof_and_memory() [function:109]

`tests/test_policy.py` · 19 symbols
  test_load_policy_defaults_human_authority_role_to_pm() [function:11], test_agent_roles_includes_marketing_harness_agy() [function:19], test_get_human_authority_role_reads_pointer() [function:30], test_get_human_authority_role_reads_repo_override() [function:39], test_task_allocation_covers_pm_and_architect_task_types() [function:55], test_check_authority_task_dispatch_pm_allowed() [function:66], _write_json() [function:74], test_load_policy_falls_back_to_hardcoded_defaults_when_no_files_exist() [function:79], test_load_policy_reads_workspace_defaults() [function:88], test_load_policy_repo_cannot_replace_product_merge_authority() [function:106], test_load_policy_stub_org_fields_present_but_inert() [function:132], test_check_authority_allows_role_in_can_merge() [function:142], test_check_authority_denies_role_not_in_can_merge() [function:152], test_check_authority_release_cut_requires_approval() [function:161], test_check_authority_task_dispatch_checked_against_allocation_table() [function:171], test_check_authority_unknown_action_raises_value_error() [function:179], test_load_policy_missing_repo_override_file_inherits_workspace_defaults() [function:187], test_check_authority_task_dispatch_unknown_task_type_denied() [function:201], test_repo_policy_json_authorizes_review_task_type() [function:209]

`tests/test_policy_cli.py` · 4 symbols
  test_cmd_policy_check_merge_exits_zero_for_authorized_role() [function:10], test_cmd_policy_check_merge_exits_nonzero_for_unauthorized_role() [function:20], test_cmd_policy_sync_branch_protection_calls_gh_api_with_required_checks() [function:30], test_cmd_policy_sync_branch_protection_dry_run_does_not_call_gh() [function:45]

`tests/test_pr_check.py` · 8 symbols
  test_pr_check_soft_warns_on_unlinked_story() [function:9], test_pr_check_does_not_warn_when_goal_linked() [function:27], test_pr_check_soft_warn_does_not_change_exit_code() [function:46], test_pr_check_warns_for_unlinked_pr_and_job() [function:61], test_pr_check_blocks_on_red_qa_gate() [function:83], test_cmd_pr_check_forwards_pr_number_through_db_wrapper() [function:99], test_pr_check_passes_on_green_qa_gate() [function:125], test_pr_check_skips_qa_gate_off_github_remote() [function:141]

`tests/test_pr_check_impact.py` · 3 symbols
  test_pr_check_fails_when_affected_symbol_has_no_tests() [function:5], test_pr_check_passes_when_all_symbols_have_tests() [function:20], test_pr_check_passes_when_no_modified_symbols() [function:35]

`tests/test_pr_rebase.py` · 3 symbols
  test_rebase_pr_if_behind_rebases_and_force_pushes_with_lease() [function:8], test_rebase_pr_if_behind_aborts_conflict_without_push() [function:26], test_rebase_pr_if_behind_skips_non_behind_pr() [function:40]

`tests/test_pr_review_multiplier.py` · 12 symbols
  test_maybe_open_worktree_pr_returns_pr_number() [function:7], test_review_cycle_multiplier_one_shot_is_ten_percent_bonus() [function:42], test_review_cycle_multiplier_two_shot_is_about_minus_nine_percent() [function:48], test_review_cycle_multiplier_three_shot_is_about_minus_25_percent() [function:54], test_review_cycle_multiplier_floors_at_quarter() [function:60], test_apply_review_cycle_multiplier_updates_quality_and_clamps() [function:66], test_apply_review_cycle_multiplier_is_idempotent() [function:90], test_apply_review_cycle_multiplier_different_prs_independent() [function:125], test_current_pr_number_uses_gh_pr_view() [function:156], test_current_pr_number_returns_none_when_gh_fails() [function:176], test_current_pr_number_uses_explicit_override() [function:195], test_current_pr_number_falls_back_to_head_commit_pulls() [function:207]

`tests/test_probe.py` · 18 symbols
  _DummySocket [class:7], _make_stub_agent() [function:12], _seed_probe_db() [function:28], _read_installed_version() [function:47], test_probe_clears_drift_alert_for_matching_agent() [function:60], test_probe_leaves_other_agent_drift_alert_untouched() [function:90], test_probe_no_drift_alerts_is_noop_for_sentinel_state() [function:119], test_probe_clears_all_drift_alerts_for_same_agent() [function:147], test_probe_extracts_claude_version_from_descriptive_output() [function:179], _install_fake_home() [function:202], test_probe_model_version_codex_reads_config_toml() [function:219], test_probe_model_version_grok_reads_models_default() [function:232], test_probe_model_version_agy_session_scoped() [function:245], test_probe_model_version_claude_reads_settings_model() [function:254], test_probe_model_version_claude_built_in_default_when_no_model_key() [function:267], test_probe_model_version_claude_built_in_default_when_settings_missing() [function:279], test_probe_model_version_codex_unknown_when_config_missing() [function:287], test_probe_model_version_grok_unknown_when_models_section_missing() [function:294]

`tests/test_product_store.py` · 9 symbols
  _repo() [function:14], test_identity_slug_and_product_paths() [function:19], test_resolve_prefers_product_then_repo_fallback() [function:29], test_write_and_migrate_are_product_scoped() [function:42], test_second_init_fails_closed_before_manifest() [function:54], test_state_db_migration_copies_legacy_repo_db_without_overwrite() [function:67], test_identity_slug_from_config_resolves_in_git_worktree() [function:93], test_migrate_state_db_in_unwritable_sandbox_returns_source_or_destination() [function:113], test_resolve_db_path_unregistered_non_project_directory() [function:137]

`tests/test_pytest_collection.py` · 1 symbols
  test_pytest_configuration_excludes_archived_duplicate_modules() [function:4]

`tests/test_qa_gate.py` · 35 symbols
  test_qa_gate_mode_defaults_to_block_only_when_key_absent() [function:16], test_qa_gate_mode_reads_configured_value() [function:23], test_qa_gate_mode_defaults_to_block_only_when_config_missing() [function:30], test_gh_pr_changed_files_parses_gh_output() [function:35], test_gh_pr_changed_files_returns_empty_list_on_gh_failure() [function:43], test_qa_gate_ci_status_green_when_ci_passes() [function:49], test_qa_gate_ci_status_red_when_ci_fails() [function:54], test_qa_gate_ci_status_none_when_undeterminable() [function:59], _SENTINEL_ISSUES_HIGH [constant:64], _SENTINEL_ISSUES_MEDIUM_ONLY [constant:67], _SENTINEL_ISSUES_NONE [constant:70], _SENTINEL_ISSUES_UNRELATED [constant:71], _SENTINEL_ISSUES_NONE_ANSI [constant:74], _mock_gh_issue_list() [function:77], test_qa_gate_sentinel_health_red_on_high_severity_open_issue() [function:82], test_qa_gate_sentinel_health_green_on_medium_only() [function:87], test_qa_gate_sentinel_health_green_on_no_open_issues() [function:92], test_qa_gate_sentinel_health_green_on_ansi_wrapped_empty_json() [function:97], test_qa_gate_sentinel_health_uses_supported_issue_list_flags() [function:102], test_qa_gate_sentinel_health_ignores_unrelated_support_issues() [function:108], test_qa_gate_sentinel_health_none_when_gh_errors() [function:113], test_qa_gate_sentinel_health_none_on_malformed_json() [function:118], test_qa_gate_verdict_green_when_both_signals_healthy() [function:123], test_qa_gate_verdict_red_when_ci_fails() [function:132], test_qa_gate_verdict_red_when_sentinel_unhealthy() [function:140], test_qa_gate_verdict_fails_closed_when_ci_status_undeterminable() [function:148], test_qa_gate_verdict_fails_closed_when_sentinel_status_undeterminable() [function:156], test_load_config_defaults_qa_gate_mode_to_block_only() [function:164], test_load_config_preserves_explicit_qa_gate_mode() [function:169], test_cmd_pr_gate_status_exits_zero_on_green() [function:178], test_cmd_pr_gate_status_exits_one_on_red() [function:193], test_cmd_pr_gate_status_passes_github_head_ref_as_worktree_branch() [function:208], test_cmd_pr_gate_status_worktree_branch_none_when_github_head_ref_unset() [function:225], test_cmd_pr_gate_status_exits_one_when_remote_undetectable() [function:243], test_cli_pr_gate_status_invokes_cmd() [function:251]

`tests/test_quota_calibration.py` · 7 symbols
  test_parse_cli_usage_claude() [function:14], test_parse_cli_usage_agy_multitrack() [function:26], test_parse_cli_usage_codex() [function:43], test_calibrate_quota_window_formula() [function:55], test_calibrate_quota_window_invalid_delta() [function:65], test_calculate_burn_runway() [function:75], test_calibrate_and_update_quota_writes_to_db() [function:97]

`tests/test_quota_cli.py` · 5 symbols
  test_quota_advisory_cli() [function:8], test_quota_advisory_cli_json() [function:15], test_quota_calibrate_cli_parsing() [function:21], test_quota_calibrate_execution() [function:40], test_quota_advisory_execution() [function:64]

`tests/test_quota_reservation_integration.py` · 3 symbols
  _fake_dispatch_success() [function:12], test_full_reserve_dispatch_settle_release_cycle() [function:29], test_deferred_job_survives_reset_and_resumes_without_redispatch() [function:95]

`tests/test_readiness_matrix.py` · 16 symbols
  test_point_1_role_tokens_missing() [function:21], test_point_1_role_tokens_valid() [function:28], test_point_1_role_tokens_valid_flat() [function:41], test_durable_role_app_material_fails_when_gh_write_required() [function:53], test_durable_role_app_material_passes_with_nested_app_file() [function:69], test_point_1_preserves_role_tokens_key_when_durable_material_is_missing() [function:85], test_point_2_sandbox_egress_success() [function:109], test_point_2_sandbox_egress_failure() [function:118], test_point_3_policy_authority_missing() [function:125], test_point_3_policy_authority_valid() [function:131], test_point_3_policy_authority_valid_overrides() [function:146], test_point_4_git_shim_missing() [function:168], test_point_4_git_shim_valid() [function:175], test_evaluate_readiness_matrix() [function:190], test_format_readiness_table() [function:200], test_cmd_doctor_readiness_returns_zero_when_pass() [function:240]

`tests/test_rebase.py` · 1 symbols
  test_markdown_conflict_combines_unique_rows_in_pr_order() [function:4]

`tests/test_reconciler_unattended_loop.py` · 8 symbols
  test_gh_write_expectation_comment_intent() [function:17], test_gh_write_expectation_explicit_override() [function:31], test_reconciler_reads_exit_file_even_if_no_git_activity() [function:74], test_reconciler_preserves_logs_and_updates_db_path_on_worktree_reap() [function:114], test_reconciler_initial_git_inspection_error_fails_closed() [function:158], test_daemon_revision_drift_detection() [function:201], test_launch_dag_structure_and_readiness() [function:231], test_launch_dag_unattended_escalation_on_reserved_gate() [function:264]

`tests/test_redaction.py` · 8 symbols
  test_redacts_github_pat() [function:4], test_redacts_github_oauth_token() [function:10], test_redacts_aws_access_key_id() [function:15], test_redacts_openai_style_key() [function:22], test_redacts_slack_token() [function:27], test_redacts_github_app_installation_token() [function:32], test_bug__secret_patterns_regex_doesnt_redact_ghs_installation_token() [function:44], test_normal_text_passes_through_unchanged() [function:51]

`tests/test_relay.py` · 2 symbols
  test_relay_broker_persists_and_fans_out() [function:7], test_iter_sse_events_decodes_data_lines() [function:22]

`tests/test_relay_p2p.py` · 6 symbols
  test_websocket_framing_roundtrip() [function:15], test_websocket_masked_frame_decoding() [function:24], test_nats_pub_framing_roundtrip() [function:39], test_relay_broker_peer_management() [function:51], test_relay_broker_peer_rpc() [function:67], test_relay_broker_forward_to_peers_loop_prevention() [function:81]

`tests/test_release.py` · 9 symbols
  _write_synced_readme() [function:12], test_release_install_check_requires_pipx() [function:37], test_cmd_release_refuses_when_role_not_authorized() [function:60], test_cmd_release_dry_run_no_writes() [function:67], test_cmd_release_bumps_version() [function:94], test_cmd_release_writes_changelog() [function:112], test_cmd_release_writes_blog_stub() [function:141], test_cmd_release_checklist_printed() [function:165], test_cmd_release_minor_flag() [function:190]

`tests/test_release_marketing.py` · 12 symbols
  _setup_fixture_repo() [function:19], test_sync_docs_bundles_updates_version_and_date() [function:52], test_mirror_docs_pdfs_to_website() [function:64], test_update_website_metadata() [function:74], test_execute_release_ceremony_dry_run() [function:86], test_execute_release_ceremony_live() [function:98], test_cmd_marketing_ceremony_cli() [function:114], test_cli_parser_marketing_ceremony() [function:130], test_cmd_release_invokes_marketing_ceremony() [function:141], test_compile_docs_pdfs_dry_run() [function:156], test_compile_book_epub_dry_run() [function:165], test_find_binaries() [function:174]

`tests/test_release_signals.py` · 24 symbols
  _git_init() [function:8], _commit() [function:14], _tag() [function:20], test_git_tags_with_dates_empty_repo_returns_empty() [function:27], test_git_tags_with_dates_returns_sorted_by_date() [function:33], test_git_tags_with_dates_handles_lightweight_tags() [function:45], test_git_tags_with_dates_non_git_dir_returns_empty() [function:54], test_detect_pattern_semver() [function:61], test_detect_pattern_semver_no_v_prefix() [function:66], test_detect_pattern_calver() [function:71], test_detect_pattern_monorepo() [function:76], test_detect_pattern_none_when_no_tags() [function:81], test_detect_pattern_mixed_when_inconsistent() [function:85], test_latest_tag_returns_most_recent_by_date() [function:93], test_latest_tag_none_when_no_tags() [function:104], test_commits_since_counts_commits_after_ref() [function:110], test_commits_since_zero_when_tag_is_head() [function:120], test_release_status_no_tags() [function:131], test_release_status_with_in_flight_commits() [function:145], test_release_status_at_latest_tag_has_no_in_flight_summary() [function:159], test_fetch_github_releases_parses_json_output() [function:175], test_fetch_github_releases_returns_empty_when_gh_not_installed() [function:190], test_fetch_github_releases_returns_empty_on_nonzero_exit() [function:195], test_fetch_github_releases_returns_empty_on_malformed_json() [function:201]

`tests/test_resolve_dispatch_harness.py` · 5 symbols
  _register_agent() [function:7], test_role_only_dispatch_uses_synthetic_story_capability_score() [function:20], test_role_only_dispatch_cold_start_falls_back_to_static_baseline() [function:49], test_static_baseline_forces_static_pick_over_synthetic_story_score() [function:59], test_static_baseline_forces_static_pick_even_with_real_story_id_score() [function:90]

`tests/test_roadmap_table_converter.py` · 1 symbols
  test_parse_roadmap_version_arc_table_scopes_to_version_arc_section() [function:4]

`tests/test_role_add_identity_prompt.py` · 1 symbols
  test_identity_init_role_registers_new_role_in_roles_yaml() [function:7]

`tests/test_roles.py` · 18 symbols
  _write_config() [function:14], test_load_config_roles_default_has_four_agents() [function:46], test_load_config_roles_prefers_capability_roles_file() [function:53], test_load_config_roles_falls_back_to_config_when_capability_roles_missing() [function:80], test_load_config_roles_claude_is_pm() [function:96], test_load_config_roles_codex_is_implement() [function:102], test_fence_exists_false_when_no_fence() [function:108], test_fence_exists_true_when_fence_present() [function:115], test_cmd_roles_prints_all_configured_roles() [function:127], test_cmd_roles_fix_writes_fence() [function:144], test_cmd_roles_fix_skips_missing_file() [function:156], test_cmd_roles_fix_repairs_missing_sops_in_fenced_file() [function:165], test_cmd_roles_fix_refreshes_stale_sops() [function:182], test_cmd_agent_add_onboards_agent() [function:201], test_cmd_agent_add_noop_when_fully_onboarded() [function:238], test_cmd_agent_add_errors_when_binary_missing() [function:259], test_agent_add_cli_route() [function:269], test_agent_run_cli_route_parses_dry_run() [function:284]

`tests/test_rollback.py` · 17 symbols
  test_dest_for_relative_path() [function:13], test_dest_for_absolute_path() [function:18], test_backup_and_restore_file_roundtrip() [function:24], test_backup_and_restore_dir_roundtrip() [function:34], test_restore_removes_path_that_did_not_exist_before() [function:47], test_manifest_write_read_archive_roundtrip() [function:56], _init_git_repo() [function:69], test_rollback_checkpoint_restores_on_exception() [function:75], test_cmd_migrate_rolls_back_real_db_path_on_import_failure() [function:102], test_rollback_checkpoint_restores_dirty_tree_stash() [function:148], test_rollback_checkpoint_stash_excludes_out_of_repo_untracked_path() [function:165], test_rollback_checkpoint_ignores_central_db_runtime_tree() [function:184], test_rollback_checkpoint_stash_excludes_gitignored_untracked_path() [function:207], test_stash_paths_excludes_sqlite_sidecars() [function:236], test_rollback_checkpoint_leaves_manifest_on_success() [function:255], test_rollback_checkpoint_upgrade_pipx_restore_reinstalls_old_version() [function:268], test_rollback_checkpoint_upgrade_script_restores_bin_and_lib() [function:288]

`tests/test_runners.py` · 2 symbols
  test_swarm_runner_schema_and_local_lifecycle() [function:10], test_local_driver_accepts_shell_command() [function:28]

`tests/test_sandbox.py` · 2 symbols
  test_scaffold_greenfield_sandbox_creates_ping_app() [function:9], test_build_artifact_tour_returns_core_pillars() [function:17]

`tests/test_selftest.py` · 17 symbols
  EXPECTED_LIVE_SCENARIOS [constant:8], test_selftest_core_exports() [function:27], test_selftest_registry_covers_core_lifecycle_commands() [function:51], test_run_selftest_uses_generic_help_for_all_taxonomy_commands() [function:57], test_run_selftest_sorts_latent_tier_last() [function:82], test_live_selftest_bespoke_lifecycle_scenarios_pass() [function:95], test_live_selftest_init_preserves_existing_files() [function:106], test_live_selftest_migrate_imports_real_rows() [function:118], test_live_selftest_upgrade_respects_install_location() [function:130], test_scenario_join_creates_real_devlog_file() [function:142], test_scenario_decide_surfaces_each_agent_response() [function:154], test_gh_write_scenario_records_capability_per_harness_and_mode() [function:163], test_selftest_subcommand_is_registered() [function:200], test_dispatch_scenario_skips_when_budget_exhausted() [function:214], test_dispatch_scenario_uses_fence_estimate_as_cost() [function:230], test_dispatch_scenario_does_not_increment_context_spend() [function:259], test_exec_scenario_skips_when_budget_exhausted() [function:289]

`tests/test_sentinel.py` · 18 symbols
  _run_result() [function:8], _pr_checks_output() [function:12], _patch_gh() [function:20], test_extract_verified_by_ci_ignores_pending_qa_gate_when_tests_pass() [function:31], test_extract_verified_by_ci_false_when_a_test_job_fails() [function:42], test_extract_verified_by_ci_none_when_a_test_job_is_pending() [function:53], test_extract_verified_by_ci_uses_pr_number_not_job_branch() [function:63], test_extract_verified_by_ci_falls_through_when_no_test_lines() [function:86], test_check_token_bloat_triggers_on_zero_files_with_high_tokens() [function:95], test_issue_1531_cached_input_inflation_is_actionable() [function:127], test_active_job_circuit_breaker_terminates_zero_file_job() [function:147], test_process_identity_check_rejects_recycled_pid_and_accepts_matching_process() [function:165], test_circuit_breaker_skips_kill_when_pid_identity_fails() [function:191], test_check_token_bloat_triggers_on_high_token_per_file_ratio() [function:208], test_check_token_bloat_does_not_trigger_on_normal_usage() [function:232], test_check_token_bloat_warn_cost_inflation() [function:250], test_check_token_bloat_scans_telemetry_file() [function:270], test_sentinel_write_deduplicates_recent_alerts() [function:293]

`tests/test_sentinel_quota_exhaustion.py` · 2 symbols
  test_quota_exhausted_detection_calls_force_exhaust() [function:4], test_quota_exhausted_detection_noop_when_no_match() [function:25]

`tests/test_session.py` · 9 symbols
  test_write_and_read_active_session() [function:7], test_read_active_session_returns_none_when_absent() [function:19], test_clear_active_session_removes_marker() [function:26], test_cmd_session_open_creates_row_and_marker() [function:40], test_cmd_session_close_sets_disposition_and_clears_marker() [function:60], test_cmd_session_close_rejects_invalid_disposition() [function:80], test_migrate_db_adds_session_id_to_jobs_and_devlog() [function:90], test_cmd_session_status_and_checkpoint_tolerate_unpopulated_session_id() [function:116], test_session_status_nudges_unattributed_jobs() [function:135]

`tests/test_slack_notifier.py` · 4 symbols
  test_format_message_includes_vizor_link_for_kill_job() [function:6], test_format_message_omits_link_on_unsubscribed_action() [function:20], test_format_message_uses_configured_vizor_port() [function:34], test_format_message_uses_default_vizor_port_without_config() [function:44]

`tests/test_spike.py` · 3 symbols
  test_generate_spike_receipt_computes_deltas() [function:6], test_run_spike_eval_creates_receipt_file() [function:22], test_cmd_spike_cli() [function:35]

`tests/test_sqlite_concurrency.py` · 3 symbols
  test_sqlite_pragmas_configured() [function:17], test_concurrent_multi_thread_access() [function:33], test_lineage_concurrent_writes() [function:74]

`tests/test_state_inventory.py` · 1 symbols
  test_inventory_is_read_only_and_classifies_repo_artifact() [function:6]

`tests/test_state_registry.py` · 9 symbols
  test_registry_registration_is_idempotent_and_path_bound() [function:14], test_existing_corrupt_registry_fails_closed() [function:30], test_missing_registry_entry_can_be_explicitly_recovered() [function:39], test_identity_metadata_rejects_copied_or_relocated_canonical() [function:49], test_registry_file_is_atomic_json() [function:62], test_ensure_registered_product_persists_repo_path() [function:71], test_ensure_registered_product_repo_path_optional() [function:87], test_ensure_registered_product_backfills_repo_path_on_existing_entry() [function:97], test_typed_open_requires_explicit_noncanonical_modes() [function:116]

`tests/test_state_repair.py` · 6 symbols
  _db() [function:15], test_promotion_is_idempotent_and_refuses_overwrite() [function:23], test_quarantine_defaults_to_plan_and_apply_moves_sidecars_read_only() [function:40], test_quarantine_rejects_registered_canonical() [function:55], test_restore_is_dry_run_by_default_and_assigns_new_lineage() [function:64], test_register_existing_state_validates_and_registers() [function:94]

`tests/test_static_scan.py` · 24 symbols
  test_extract_python_symbols() [function:13], test_extract_typescript_symbols() [function:38], test_extract_go_symbols() [function:62], test_extract_rust_symbols() [function:81], test_extract_shell_symbols() [function:99], test_extract_generic_returns_empty() [function:114], test_extract_max_300_lines() [function:121], test_extract_shell_function_keyword() [function:138], test_extract_missing_file_returns_empty() [function:153], test_extract_line_numbers() [function:158], test_git_head_sha_returns_string_or_none() [function:169], test_git_head_sha_no_git() [function:175], test_scan_meta_round_trip() [function:183], test_load_scan_meta_missing_returns_none() [function:196], test_load_scan_meta_corrupt_returns_none() [function:202], test_save_scan_meta_creates_synlynk_dir() [function:209], test_save_scan_meta_preserves_deep_on_resave() [function:216], _make_source_tree() [function:229], test_skeleton_returns_at_most_15_files() [function:242], test_skeleton_entry_point_scored_higher() [function:251], test_skeleton_skips_scan_skip_dirs() [function:260], test_skeleton_depth_penalty() [function:270], test_skeleton_symbols_capped_at_8() [function:286], test_skeleton_language_detected() [function:296]

`tests/test_status.py` · 8 symbols
  _utc_iso() [function:17], test_cmd_status_platform_no_harnesses() [function:21], test_cmd_status_platform_with_harness_record() [function:37], test_cmd_status_platform_drift_detected() [function:72], test_cmd_status_platform_budget_pulse() [function:89], test_cmd_status_platform_flag_wired() [function:110], test_status_flags_overdue_smoke_test() [function:131], test_status_surfaces_recent_regression_incidents() [function:147]

`tests/test_story_lifecycle.py` · 6 symbols
  test_story_done_sets_status_and_emits_event() [function:7], test_story_done_clears_readiness() [function:21], test_story_done_includes_linked_goal_ids_in_payload() [function:35], test_story_done_unknown_story_prints_error() [function:46], test_story_ready_records_skip_when_no_goal_linked() [function:52], test_story_ready_no_op_when_goal_already_linked() [function:66]

`tests/test_story_provisioning.py` · 13 symbols
  test_detect_issue_number_prefers_explicit_issue_arg() [function:7], test_detect_issue_number_falls_back_to_regex_on_task_text() [function:13], test_detect_issue_number_returns_none_when_no_match() [function:19], test_classify_heuristic_matches_docs_keyword_when_gh_unavailable() [function:25], test_classify_heuristic_uses_gh_issue_labels_when_available() [function:39], test_classify_heuristic_falls_back_to_none_fields_when_nothing_matches() [function:60], test_classify_story_raises_not_implemented_for_llm_method() [function:76], test_classify_story_raises_not_implemented_for_pm_manual_method() [function:83], test_resolve_or_create_story_id_reachable_from_top_level_package() [function:90], test_backfill_capability_ratings_skips_jobs_with_existing_story_id() [function:96], test_backfill_capability_ratings_skips_jobs_with_missing_log_file() [function:114], test_backfill_capability_ratings_resolves_story_and_writes_rating() [function:133], test_cmd_backfill_capability_ratings_reachable_from_top_level_package() [function:170]

`tests/test_story_unstranding.py` · 3 symbols
  test_db() [function:12], test_reclaim_stranded_stories_dry_run() [function:43], test_reclaim_stranded_stories_execution() [function:72]

`tests/test_surface.py` · 4 symbols
  test_detect_developer_surfaces_cursor_and_vscode() [function:10], test_detect_developer_surfaces_warp_replit_emergent() [function:18], test_bind_surface_rules_generates_cursor_mdc() [function:28], test_bind_surface_rules_generates_warp_replit_emergent_antigravity() [function:38]

`tests/test_synlynk.py` · 19 symbols
  test_agent_capability_baselines_exist() [function:13], test_can_gh_write_baselines_match_live_verified_reality() [function:38], test_sop_section_headers_defined() [function:48], test_capability_allocation_table_uses_harness_not_agent_header() [function:61], test_repair_templates_preserve_merge_authority_and_herdr_license() [function:80], test_repair_sops_removes_unfenced_duplicate_sections() [function:105], test_directive_templates_contain_sop_headers() [function:128], test_run_tc5_passes_when_all_headers_present() [function:142], test_run_tc5_reports_missing_sections() [function:152], test_run_tc5_missing_file_reports_all_headers() [function:164], test_capability_allocation_sop_routes_gh_write_to_codex_not_grok() [function:172], test_run_tc7_passes_when_all_gh_write_allow_rules_present() [function:183], test_run_tc7_reports_missing_allow_rules() [function:201], test_run_tc7_missing_settings_file_reports_all_rules_missing() [function:214], test_run_tc8_passes_when_stitch_mcp_configured() [function:222], test_run_tc8_reports_missing_when_stitch_not_configured() [function:240], test_run_tc8_reports_missing_when_stitch_disabled() [function:250], test_run_tc8_missing_file_reports_error() [function:268], test_run_tc8_reports_error_on_invalid_or_malformed_stitch_config() [function:276]

`tests/test_task_leases.py` · 6 symbols
  db_conn() [function:16], test_acquire_and_get_task_lease() [function:26], test_concurrent_lease_conflict() [function:42], test_renew_task_lease() [function:52], test_release_task_lease() [function:64], test_reclaim_stranded_story_with_lease() [function:76]

`tests/test_task_type_inference.py` · 2 symbols
  test_infer_task_type_review() [function:12], test_infer_task_type_does_not_guess() [function:27]

`tests/test_taxonomy.py` · 12 symbols
  REQUIRED_KEYS [constant:16], VALID_STAGES [constant:26], VALID_TIERS [constant:27], VALID_PROMINENCE [constant:28], VALID_AUDIENCE [constant:29], test_every_entry_has_required_keys() [function:32], test_every_entry_has_valid_field_values() [function:37], test_no_duplicate_commands() [function:48], test_get_entry_returns_matching_command() [function:53], test_entries_for_tier_filters_exact_matches() [function:59], test_entries_up_to_tier_includes_lower_tiers_only() [function:65], test_taxonomy_matches_real_cli_surface() [function:73]

`tests/test_taxonomy_standards.py` · 8 symbols
  test_naics_codes_have_label_and_parent() [function:7], test_apqc_codes_have_label_and_parent() [function:17], test_sfia_codes_have_label_and_parent() [function:26], test_taxonomy_label_looks_up_known_code() [function:39], test_taxonomy_label_falls_back_to_raw_code_for_unknown() [function:45], test_taxonomy_label_rejects_unknown_axis() [function:51], test_taxonomy_label_used_by_capability_view_helper() [function:59], test_taxonomy_axis_registry_contains_expected_tables() [function:70]

`tests/test_tc9_gh_write_probe.py` · 10 symbols
  test_tc9_auth_failure() [function:15], test_tc9_claude_dry_and_live() [function:23], test_tc9_codex_dry_and_live() [function:41], test_tc9_grok_sandbox_denied() [function:58], test_tc9_agy_allow_rules() [function:75], test_tc9_uninstalled_cli() [function:93], test_tc9_db_persistence() [function:101], test_doctor_prints_tc9_output() [function:119], test_doctor_fails_when_grok_tc9_denies_shell() [function:137], test_get_harness_gh_write_capability() [function:173]

`tests/test_team.py` · 2 symbols
  _manifest_from_url() [function:10], test_implement_1436_leftover_charter_patch_so_merge_roles_request_actions_write() [function:18]

`tests/test_testbed_cli.py` · 4 symbols
  test_charter_testbed_skill_binding() [function:16], test_generate_testbed_receipt() [function:23], test_policy_verify_testbed_receipt() [function:41], test_run_testbed_cli_status() [function:66]

`tests/test_testbed_driver.py` · 6 symbols
  test_node_handle_and_exec_result_dataclasses() [function:15], test_orb_driver_create_node() [function:35], test_orb_driver_exec_command() [function:55], test_orb_driver_fault_injection() [function:71], test_orb_driver_destroy_node() [function:89], test_docker_driver_lifecycle() [function:102]

`tests/test_testbed_identities.py` · 3 symbols
  test_synthetic_identity_attribution_tag() [function:14], test_standard_identities_matrix() [function:25], test_provision_node_identity() [function:48]

`tests/test_testbed_installer.py` · 3 symbols
  test_target_resolver_staging_unstable_and_commit() [function:15], test_install_target_git_ref_on_node() [function:34], test_install_target_local_wheel_on_node() [function:48]

`tests/test_testbed_scenarios.py` · 5 symbols
  test_invariant_asserter_clean() [function:13], test_invariant_asserter_failure() [function:27], test_scenario_runner_brownfield_init() [function:40], test_scenario_runner_p2p_mesh() [function:52], test_scenario_runner_task_lease_recovery() [function:70]

`tests/test_tool_installer.py` · 7 symbols
  test_recommended_tools_registry() [function:6], test_is_tool_available_false_when_missing() [function:14], test_is_tool_available_true_when_present() [function:19], test_install_tool_invokes_uv_or_pipx() [function:24], test_install_tool_captures_failure_diagnostics() [function:43], test_install_tool_system_package_manager_brew() [function:62], test_install_tool_missing_package_manager_reports_error() [function:81]

`tests/test_tpm_hooks.py` · 5 symbols
  test_tpm_observe_reservations_returns_open_reservations() [function:6], test_tpm_reorder_queue_updates_priorities() [function:23], test_tpm_reallocate_moves_reservation_and_agent() [function:47], test_tpm_reallocate_raises_when_not_queued() [function:75], test_cli_quota_tpm_view_prints_reservations() [function:90]

`tests/test_tpm_sweep.py` · 11 symbols
  test_cmd_story_create_accepts_marketing_role() [function:9], test_run_sweep_pass_advances_authorized_story() [function:15], test_run_sweep_pass_selects_ready_story_and_dispatches_it() [function:27], test_run_sweep_pass_routes_marketing_role_to_agy() [function:50], test_run_sweep_pass_routes_dev_role_to_codex() [function:64], test_run_sweep_pass_parks_story_requiring_approval() [function:77], test_run_sweep_pass_reuses_open_ticket_without_refiling() [function:92], test_run_sweep_pass_dispatches_and_consumes_resolved_ticket() [function:115], _story_with_job() [function:142], test_ready_stories_excludes_story_with_done_job() [function:157], test_ready_stories_includes_story_with_failed_job() [function:163]

`tests/test_tui.py` · 7 symbols
  FakeScreen [class:7], _job() [function:28], _run() [function:34], test_approve_key_calls_uxcore_for_selected_pending_job() [function:45], test_kill_requires_confirmation() [function:52], test_kill_key_calls_uxcore_after_confirmation() [function:59], test_actions_are_noops_when_selected_job_is_not_eligible() [function:66]

`tests/test_tui_panels.py` · 5 symbols
  test_render_fleet_panel_writes_agent_names() [function:6], test_render_jobs_panel_writes_recent_jobs() [function:18], test_render_costs_panel_writes_total() [function:28], test_render_review_panel_writes_capability_denied_message() [function:36], test_cli_tui_subcommand_invokes_tui_main() [function:47]

`tests/test_types_registry.py` · 7 symbols
  setup_product() [function:14], test_seed_is_idempotent_and_writes_charter() [function:20], test_type_create_and_validation() [function:28], test_specialist_inherits_kind_skills_and_applies_delta() [function:39], test_type_create_rejects_canonical_id_before_pack_seed() [function:54], test_studio_seed_and_pack_kind_creation() [function:60], test_agency_seed_and_unknown_pack() [function:69]

`tests/test_upgrade.py` · 18 symbols
  test_ver_tuple_basic() [function:9], test_ver_tuple_malformed() [function:18], test_detect_install_type_pipx_binary() [function:24], test_detect_install_type_pipx_env() [function:37], test_detect_install_type_script() [function:47], test_run_upgrade_pipx_prints_migrate_hint() [function:71], test_run_upgrade_pipx_local_path_reinstalls_release() [function:86], test_run_upgrade_script_prints_pipx_migration_hint() [function:119], test_run_upgrade_pipx_records_leg2_manifest() [function:137], test_get_pipx_source_local_path() [function:161], test_get_pipx_source_git_url() [function:174], test_get_pipx_source_missing() [function:187], test_warn_stale_script_install_no_shim() [function:194], test_warn_stale_script_install_with_shim_and_pipx() [function:209], test_install_script_dispatches_to_pipx() [function:234], test_upgrade_dry_run_makes_no_subprocess_calls() [function:244], test_upgrade_installs_vizor_daemon_on_success() [function:265], test_upgrade_dry_run_skips_daemon_install() [function:284]

`tests/test_upgrade_uninstall.py` · 2 symbols
  test_execute_upgrade_refreshes_instructions_and_db() [function:9], test_execute_uninstall_cleans_runtime() [function:16]

`tests/test_ux_journey_map.py` · 1 symbols
  test_ux_10_phase_2_journey_map_simulator() [function:4]

`tests/test_ux_nudges.py` · 4 symbols
  _insert_running_jobs() [function:1], test_pending_ux_tip_suggests_tui_when_never_used() [function:16], test_pending_ux_tip_none_when_no_active_jobs() [function:27], test_pending_ux_tip_respects_dismissed_ids() [function:33]

`tests/test_uxcore_reads.py` · 7 symbols
  test_local_actor_default_role_is_owner() [function:9], test_default_actor_singleton_is_local_owner() [function:14], test_get_costs_returns_typed_dataclass() [function:18], test_get_gantt_data_returns_dreams_with_stages() [function:28], test_get_jobs_reads_telemetry() [function:39], test_get_jobs_missing_telemetry_returns_empty() [function:52], test_get_fleet_state_counts_agent_runs() [function:57]

`tests/test_uxcore_writes.py` · 19 symbols
  test_review_mode_uses_comment_checklist_only_for_same_identity() [function:9], test_feature_flags_missing_key_is_disabled() [function:15], test_feature_flags_enabled_for_tier() [function:23], test_list_capabilities_owner_gets_everything() [function:32], test_execute_write_appends_event() [function:41], test_execute_write_denies_when_capability_missing() [function:58], test_dispatch_calls_dispatch_agent_and_wraps_result() [function:70], test_dispatch_denied_for_viewer() [function:78], test_approve_pr_runs_gh_commands() [function:87], test_approve_pr_does_not_merge_when_behind_rebase_fails() [function:99], test_approve_pr_does_not_reach_gh_merge_when_role_is_unauthorized() [function:112], test_approve_pr_marks_story_done_after_merge() [function:124], test_approve_pr_propagates_non_self_approval_failure() [function:137], test_approve_pr_uses_comment_fallback_only_for_self_approval_failure() [function:154], test_kill_job_sends_sigterm_to_tracked_pid() [function:176], test_kill_job_unknown_id_returns_not_ok() [function:188], test_subscribe_yields_existing_events_filtered_by_type() [function:197], test_subscribe_no_filter_returns_all() [function:214], test_subscribe_missing_file_yields_nothing() [function:226]

`tests/test_v0_20_0_milestone_spec.py` · 5 symbols
  SPEC_PATH [constant:5], REQUIRED_HEADINGS [constant:13], REQUIRED_PHRASES [constant:23], test_v0_20_0_spec_exists() [function:44], test_v0_20_0_spec_covers_required_sections() [function:48]

`tests/test_viz.py` · 16 symbols
  test_cmd_viz_opens_browser_to_workspace_url() [function:6], test_cmd_viz_prints_hint_when_daemon_not_running() [function:21], test_ftue_prompts_non_tty_uses_defaults_without_input() [function:34], test_synlynk_viz_ftue_crashes_with_filenotfou_when_synlynk_directory_missing() [function:58], make_test_db() [function:73], test_generate_viz_data_costs_and_dreams_match_uxcore() [function:107], test_load_workspace_repos_missing_returns_empty() [function:125], test_load_workspace_repos_reads_default_workspace() [function:131], test_load_workspace_repos_honors_explicit_workspace_name() [function:145], test_load_workspace_map_missing_returns_empty_shape() [function:159], test_load_workspace_map_reads_file() [function:166], test_generate_viz_data_structure() [function:180], test_generate_viz_data_includes_file_tree() [function:206], test_dreams_populated() [function:234], test_generate_viz_data_splits_cost_source_by_agent() [function:257], test_generate_viz_data_null_cost_source_counts_as_estimated() [function:283]

`tests/test_viz_banner.py` · 3 symbols
  test_underused_banner_for_12_jobs_without_approve_or_kill() [function:4], test_underused_banner_is_hidden_after_approve_or_kill() [function:13], test_underused_banner_is_hidden_for_fewer_than_10_jobs() [function:19]

`tests/test_viz_bs6.py` · 5 symbols
  test_generate_product_html() [function:12], test_generate_logical_html() [function:20], test_generate_infra_html() [function:28], test_generate_world_html() [function:36], test_index_navigation_includes_bs6_views() [function:44]

`tests/test_viz_goals.py` · 1 symbols
  test_viz_data_includes_goals_key() [function:4]

`tests/test_viz_graphify.py` · 6 symbols
  test_extract_logical_nodes_enriches_from_graphify_when_present() [function:10], test_extract_logical_nodes_records_community_and_centrality() [function:37], test_extract_logical_nodes_flags_stale_when_head_advanced() [function:65], test_generate_logical_html_renders_amber_staleness_banner() [function:92], test_extract_logical_nodes_malformed_graph_json_falls_back() [function:114], test_generate_logical_html_string_community() [function:131]

`tests/test_viz_nav_restructure.py` · 6 symbols
  sample_viz_data() [function:14], test_generate_overview_html() [function:84], test_generate_overview_html_clean_alerts() [function:118], test_generate_activity_stream_html() [function:124], test_generate_index_html_two_tier_accordion_and_categories() [function:142], test_write_cache_includes_overview_and_activity() [function:180]

`tests/test_viz_onboarding.py` · 8 symbols
  test_get_role_manifest_payload() [function:15], test_reviewer_role_from_login() [function:43], test_generate_roles_onboarding_html() [function:52], test_generate_roles_onboarding_html_org_and_identity_slug() [function:66], test_generate_roles_onboarding_html_personal_repo() [function:85], test_handle_github_app_conversion_mock() [function:99], test_viz_auth_sync_handler() [function:131], test_generate_onboarding_html_renders_three_views() [function:176]

`tests/test_viz_regression.py` · 3 symbols
  test_muse_harness_registered() [function:5], test_index_contains_muse_css_variables() [function:8], test_sentinel_alerts_have_severity_parsing() [function:14]

`tests/test_viz_roles.py` · 4 symbols
  _roles_data() [function:4], test_generate_roles_html_renders_active_agents() [function:18], test_generate_roles_html_has_provision_drawer() [function:26], test_handler_handle_role_create() [function:34]

`tests/test_viz_serve.py` · 15 symbols
  _DummyVizorHandler [class:12], _make_handler() [function:29], test_post_note_creates_file() [function:49], test_post_note_merges_existing() [function:69], test_post_invalid_json_returns_400() [function:85], test_post_note_without_token_returns_401() [function:95], test_post_note_wrong_token_returns_401() [function:107], test_post_note_cross_origin_is_forbidden() [function:124], test_post_dispatch_without_token_does_not_dispatch() [function:136], test_vizor_write_routes_require_token() [function:149], test_post_json_ok_does_not_set_wildcard_cors() [function:157], test_handle_dispatch_routes_through_uxcore() [function:170], test_handle_approve_routes_through_uxcore() [function:182], test_handle_approve_passes_story_id_to_merge_path() [function:193], test_handle_kill_routes_through_uxcore() [function:204]

`tests/test_viz_views.py` · 6 symbols
  test_init_workspace_view_tables() [function:13], test_extract_product_nodes_with_journeys() [function:20], test_extract_logical_nodes_structure() [function:33], test_extract_infra_nodes_daemon() [function:44], test_extract_world_nodes_egress() [function:51], test_build_workspace_views_snapshot() [function:64]

`tests/test_viz_worktrees.py` · 2 symbols
  test_observatory_renders_worktree_lifecycle_section() [function:4], test_handler_handle_worktree_clean() [function:17]

`tests/test_vizor_daemon.py` · 22 symbols
  test_poll_interval_default() [function:10], test_poll_interval_override() [function:15], test_poll_interval_invalid_falls_back() [function:20], test_workspace_render_context_chdirs_and_restores() [function:25], test_workspace_render_context_restores_get_db_on_exception() [function:40], _seed_registry() [function:56], test_poll_once_writes_cache_per_workspace() [function:74], test_poll_once_isolates_failures() [function:108], test_resolve_slug_from_path_valid() [function:162], test_resolve_slug_from_path_unknown_slug() [function:179], test_resolve_slug_from_path_non_workspace_path() [function:188], test_rewrite_workspace_app_route_for_known_slug() [function:197], test_rewrite_workspace_app_route_rejects_unknown_slug() [function:204], test_workspace_index_lists_registered_slugs() [function:210], test_workspace_index_empty() [function:218], test_write_and_read_pidfile() [function:226], test_read_pid_missing_returns_none() [function:239], test_launchd_plist_path() [function:246], test_systemd_unit_path() [function:254], test_install_writes_unit_and_starts() [function:262], test_status_reports_not_installed() [function:277], test_install_uninstall_use_home_relative_paths() [function:290]

`tests/test_vizor_efficiency.py` · 8 symbols
  make_test_db() [function:8], test_generate_efficiency_html_basic_keywords() [function:43], test_capacity_table_renders_all_agents() [function:61], test_cycle_matrix_renders_all_cycles() [function:89], test_fleet_header_shows_dispatch_mode() [function:110], test_empty_ecosystem_renders_placeholder_without_crashing() [function:128], test_generate_viz_data_result_includes_ecosystem() [function:142], test_generate_viz_data_real_graceful_fallback() [function:170]

`tests/test_vizor_goals_panel.py` · 2 symbols
  test_gantt_html_renders_goal_count_id() [function:3], test_gantt_html_empty_goals_shows_empty_state() [function:19]

`tests/test_wave2_state_policy.py` · 4 symbols
  _repo() [function:8], test_product_db_schema_has_repo_and_type_columns() [function:15], test_product_policy_wins_and_resolves_canonical_qa() [function:29], test_unknown_merge_type_keeps_legacy_string_matching() [function:52]

`tests/test_wave4_runtime_surfaces.py` · 3 symbols
  test_doctor_identity_slug_warns_when_missing() [function:6], test_dispatch_allows_config_without_identity_slug() [function:15], test_dispatch_resolves_product_type_when_registry_exists() [function:23]

`tests/test_wave6.py` · 4 symbols
  test_membership_requires_explicit_invite_and_writes_no_pem() [function:15], test_connector_dispatch_requires_explicit_grant() [function:26], test_graph_read_fails_closed_without_minter() [function:43], test_hosted_vizor_is_named_placeholder() [function:49]

`tests/test_wizard.py` · 21 symbols
  test_wiz_header_step_1() [function:11], test_wiz_header_sub_active() [function:17], test_wiz_read_key_from_stdin() [function:27], test_wiz_screen_landing_enters_on_any_key() [function:35], test_wiz_screen_harness_selects_first() [function:43], test_wiz_screen_harness_preselects_home() [function:56], test_implement_plan_b_tasks_b1_and_b2_from_docs_superpowers_plans_2026_07_01_bs17_scan_wizard() [function:72], test_wiz_screen_topology_single() [function:89], test_wiz_screen_topology_multi() [function:99], test_wiz_screen_workspace_name_pick_returns_dict() [function:110], test_wiz_screen_workspace_confirm_enter_returns_true() [function:127], test_wiz_screen_workspace_confirm_e_returns_false() [function:134], test_wiz_screen_skills_enter_continues() [function:143], test_wiz_screen_skills_no_skills() [function:152], test_wiz_screen_agents_enter_continues() [function:160], test_wiz_screen_roles_returns_dict() [function:171], test_wiz_screen_launch_prints_commands() [function:187], test_wizard_init_completes_without_write_on_ctrl_c() [function:196], test_wizard_single_repo_full_flow() [function:221], test_wizard_ctrl_c_leaves_no_state() [function:251], test_wizard_multi_repo_flow() [function:278]

`tests/test_workspace_add_repo.py` · 3 symbols
  _repo() [function:9], test_add_repo_updates_canonical_apps_and_product_ledger() [function:15], test_add_repo_requires_explicit_identity_slug() [function:38]

`tests/test_workspace_agent.py` · 3 symbols
  test_nudges_on_goal_fully_closed() [function:7], test_no_nudge_when_goal_still_has_open_stories() [function:22], test_nudges_use_agent_specific_checkpoint_no_repeat() [function:38]

`tests/test_workspace_scan.py` · 22 symbols
  test_write_workspace_config_creates_dir() [function:10], test_generate_structured_context_has_sections() [function:32], test_cmd_scan_no_flags_runs_workspace_scan() [function:57], test_cmd_scan_dry_run_no_writes() [function:69], test_cmd_scan_add_appends_repo() [function:80], test_synlynk_scan_dry_run_cli() [function:100], test_scan_add_then_remove_roundtrip() [function:122], test_scan_dry_run_writes_nothing() [function:149], test_structured_context_written_after_scan() [function:163], test_fingerprint_stack_ci_cd() [function:179], test_fingerprint_stack_sql() [function:187], test_deep_scan_returns_stage_keys() [function:194], test_deep_false_stage_keys_are_none() [function:206], test_workspace_name_single_repo_uses_repo_name() [function:216], test_workspace_name_explicit_overrides() [function:225], test_scan_stage_stack_python_pyproject() [function:233], test_scan_stage_stack_ci_detected() [function:244], test_scan_stage_stack_dep_count() [function:254], test_scan_stage_stack_lockfile_fresh() [function:261], test_scan_stage_stack_schema_keys() [function:273], test_scan_stage_source_basic() [function:281], test_scan_stage_source_sorted_by_lines() [function:298]

`tests/test_worktree.py` · 24 symbols
  test_parse_worktree_porcelain_basic() [function:17], test_worktree_entry_and_verdict_are_dataclasses_with_defaults() [function:39], test_build_worktree_entries_excludes_main_and_cwd() [function:46], test_build_worktree_entries_computes_nesting() [function:57], test_nesting_floor_nested_under_safe_parent_stays_safe() [function:69], test_nesting_floor_raises_child_to_parent_verdict() [function:80], _entry() [function:101], test_classify_ancestor_true_is_safe() [function:105], test_classify_pr_merged_is_safe() [function:114], test_classify_pr_closed_net_zero_or_negative_is_safe() [function:124], test_classify_pr_closed_net_positive_is_needs_review() [function:134], test_classify_pr_open_is_unsafe() [function:144], test_classify_no_pr_found_is_needs_review() [function:154], test_classify_dirty_overrides_everything() [function:164], test_classify_gh_unavailable_falls_back_to_needs_review() [function:174], test_classify_missing_worktree_directory_is_safe() [function:184], _run() [function:193], _init_repo_with_worktree() [function:199], _make_stub_gh() [function:223], test_cmd_worktree_audit_reports_safe_ancestor() [function:241], test_cmd_worktree_audit_json_output_shape() [function:252], test_cmd_worktree_audit_no_worktrees_prints_one_liner() [function:270], test_cmd_worktree_clean_dry_run_does_not_mutate() [function:286], test_cmd_worktree_clean_apply_removes_safe_items() [function:298]

`tests/test_worktree_lineage.py` · 4 symbols
  _setup_db() [function:14], test_record_job_superseded_updates_schema_and_status() [function:44], test_superseded_jobs_excluded_from_zombies() [function:69], test_get_job_lineage_traverses_chain() [function:94]

`tests/test_worktree_prune.py` · 6 symbols
  _setup_prune_repo() [function:12], test_detects_patch_equivalent_squashed_branches() [function:26], test_preserves_unmerged_or_dirty_branches() [function:53], test_prune_removes_worktree_and_branch() [function:75], test_reap_merged_worktree_sweeps_nested_job_worktrees() [function:103], test_reap_merged_worktree_preserves_dirty_tree() [function:128]

`tests/test_worktree_sparse.py` · 5 symbols
  _setup_fixture_repo() [function:12], test_create_sparse_cone_worktree_includes_mandatory_dirs() [function:44], test_ensure_path_in_sparse_cone_expands_set() [function:68], test_is_sparse_worktree_returns_false_on_full_repo() [function:87], test_dispatch_create_job_worktree_honors_sparse_config() [function:92]

`tests/test_worktree_timestamp.py` · 4 symbols
  _setup_repo_with_commit() [function:8], test_get_worktree_epoch_reads_commit_timestamp() [function:25], test_source_date_epoch_injected_into_subprocess_env() [function:31], test_get_worktree_epoch_fallback_on_non_git_dir() [function:44]

## website/  [javascript · 1]
`website/.eleventy.js` · 0 symbols

## website/scripts/  [javascript · 1]
`website/scripts/extract-heroes.js` · 0 symbols

## website/src/assets/js/  [javascript · 3]
`website/src/assets/js/carousel.js` · 0 symbols

`website/src/assets/js/main.js` · 0 symbols

`website/src/assets/js/motherboard.js` · 0 symbols
