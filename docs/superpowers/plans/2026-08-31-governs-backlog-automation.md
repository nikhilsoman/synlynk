# GOVERNS Backlog Automation Implementation Plan

**Spec:** `docs/superpowers/specs/2026-08-31-governs-backlog-automation-design.md`  
**Issue:** #1203 (Parent Tracking: #1198 — Autonomous Operations Activation)  
**Story ID:** `story-governs-backlog-auto`  

---

## 1. Database Schema & Migration (Stage 1)
- In `synlynk/db.py`:
  - Check/add `fingerprint TEXT UNIQUE`, `source_type TEXT`, `source_ref TEXT`, `governs_stage TEXT DEFAULT 'open'` to `stories` table.
  - Create index `idx_stories_fingerprint` on `stories(fingerprint)`.
  - Bump migration version / ensure idempotent column addition.

## 2. Core Backlog & Deduplication Module (Stage 2)
- In `synlynk/backlog.py`:
  - `compute_fingerprint(title: str, source_ref: str = "") -> str`
  - `check_duplicate(title: str, fingerprint: str = None, db_conn=None) -> bool`
  - `stage_discovered_work(title: str, description: str = "", role: str = "dev", stage: str = "open", source_type: str = "manual", source_ref: str = "", db_conn=None) -> dict`
  - `list_staged_backlog(db_conn=None, stage: str = None, unfiled_only: bool = True) -> list[dict]`
  - `sync_backlog_to_github(db_conn=None, dry_run: bool = False, parent_issue: int = None) -> list[dict]`

## 3. Signal Extraction & Parser (Stage 3)
- In `synlynk/backlog_extractor.py`:
  - `extract_from_devlog_content(text: str) -> list[dict]`
  - `extract_from_job_summary(summary: str, touched_files: list = None) -> list[dict]`
  - `extract_from_doctor_failures(failures: list[dict]) -> list[dict]`

## 4. CLI Commands & Session Integration (Stage 4)
- In `synlynk/cli.py`:
  - Expose `synlynk backlog capture`, `synlynk backlog list`, `synlynk backlog sync`.
- In `synlynk/session.py`:
  - Integrate devlog extraction during session checkpoint/end.

## 5. Comprehensive Unit & Integration Tests (Stage 5)
- In `tests/test_backlog_automation.py`:
  - Test fingerprinting and collision rejection.
  - Test devlog, job summary, and doctor failure extraction.
  - Test staging and sync to GitHub mock.
  - Test CLI subcommands.
