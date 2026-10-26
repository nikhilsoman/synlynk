"""Story Home Claims interface (gh:#2511, #2528).

Provides claim acquisition, state transitions, renewal, and release helpers.
"""

from typing import Optional
from synlynk.db import cmd_story_update
from synlynk.jobs import (
    acquire_task_lease,
    cmd_story_claim,
    get_active_lease,
    reclaim_stranded_stories,
    release_task_lease,
    renew_task_lease,
)

__all__ = [
    "acquire_task_lease",
    "cmd_story_claim",
    "cmd_story_update",
    "get_active_lease",
    "reclaim_stranded_stories",
    "release_task_lease",
    "renew_task_lease",
]
