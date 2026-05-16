# synlynk Memory

## Decisions
- **Naming:** Finalized project name as **synlynk** (replacing Project Pulse). [@nikhilsoman]
- **Structure:** Uses `/project-docs` for core records and `/project-docs/devlogs` for attribution. [@nikhilsoman]
- **Collaborative Logic:** Team Mode is a first-class citizen, requiring attribution tags `[@username]`. [@nikhilsoman]
- **Delivery:** Single-command bootstrap via `install.sh`. [@nikhilsoman]

## Conventions
- **Attribution:** All `memory.md` entries in Team Mode MUST have `[@username]`.
- **Session Protocol:** 3-row start (Last Task, Next Task, Collaborator Status).
- **Automation:** The AI maintains these docs without user prompting.

## Best Practices
- **Conflict Avoidance:** Always `git pull` before updating documentation.
- **Incremental Progress:** Use devlogs to reconstruct context if a session is interrupted.
