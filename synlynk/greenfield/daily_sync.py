"""Multi-channel daily sync engine for morning briefings (v0.28.5)."""
from __future__ import annotations

import datetime
import os
import sqlite3
import subprocess
from typing import Any, Dict, List, Optional


def generate_daily_sync(workspace_dir: str = ".") -> Dict[str, Any]:
    """Gather yesterday's changes, token metrics, and top unblocked tasks."""
    today_str = datetime.date.today().strftime("%b %d, %Y")

    # 1. Inspect recent git commits
    recent_commits: List[str] = []
    try:
        proc = subprocess.run(
            ["git", "log", "-n", "3", "--pretty=format:%s"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            recent_commits = [c.strip() for c in proc.stdout.splitlines() if c.strip()]
    except Exception:
        recent_commits = ["Initial project genesis and governance baseline setup"]

    yesterday_summary = recent_commits[0] if recent_commits else "Project initialization"

    # 2. Inspect state.db if available
    db_path = os.path.join(workspace_dir, ".synlynk", "state.db")
    cost_usd = 0.24
    unblocked_task = "Task 1: Set up core engine scaffolding and verify tests"
    active_branch = "main"

    try:
        proc_br = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_br.returncode == 0 and proc_br.stdout.strip():
            active_branch = proc_br.stdout.strip()
    except Exception:
        pass

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
            cur = conn.cursor()
            # Check latest story ready
            cur.execute("SELECT story_id, title FROM stories WHERE readiness = 'ready' ORDER BY priority ASC LIMIT 1")
            row = cur.fetchone()
            if row:
                unblocked_task = f"{row[0]}: {row[1]}"
            # Check yesterday's burn
            cur.execute("SELECT SUM(cost_usd) FROM cost_entries")
            cost_row = cur.fetchone()
            if cost_row and cost_row[0] is not None:
                cost_usd = float(cost_row[0])
            conn.close()
        except Exception:
            pass

    return {
        "date": today_str,
        "active_branch": active_branch,
        "yesterday_summary": yesterday_summary,
        "burn_cost_usd": cost_usd,
        "up_next_task": unblocked_task,
        "suggested_action": "Run 'synlynk dispatch' to execute today's top unblocked task.",
    }


def format_cli_greeting(sync_data: Dict[str, Any]) -> str:
    """Format the ambient terminal greeting on first command of the day."""
    lines = [
        f"☕ Good morning! Synlynk Daily Sync — {sync_data['date']}",
        "─" * 68,
        f"• Yesterday: {sync_data['yesterday_summary'][:50]} (Burn: ${sync_data['burn_cost_usd']:.2f})",
        f"• Up Next:   {sync_data['up_next_task'][:55]}",
        f"• Action:    {sync_data['suggested_action']}",
    ]
    return "\n".join(lines)


def format_vizor_payload(sync_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format the morning digest payload for http://localhost:33333/overview."""
    return {
        "type": "daily_sync_digest",
        "date": sync_data["date"],
        "hero_card": {
            "title": f"Daily Briefing ({sync_data['date']})",
            "yesterday": sync_data["yesterday_summary"],
            "burn_rate_usd": sync_data["burn_cost_usd"],
            "next_dispatch": sync_data["up_next_task"],
            "action_button": {
                "label": "Dispatch Next Task",
                "action": "synlynk dispatch",
            },
        },
    }


def format_discord_embed(sync_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format the Companion Discord/Slack rich embed."""
    return {
        "title": f"☕ Synlynk Daily Standup — {sync_data['date']}",
        "color": 0x4A90E2,
        "fields": [
            {
                "name": "Yesterday's Deliveries",
                "value": f"{sync_data['yesterday_summary']} (Spend: ${sync_data['burn_cost_usd']:.2f})",
                "inline": False,
            },
            {
                "name": "Ready for Dispatch Today",
                "value": sync_data["up_next_task"],
                "inline": False,
            },
        ],
        "footer": {"text": "Run 'synlynk dispatch' or open localhost:33333 to start"},
    }
