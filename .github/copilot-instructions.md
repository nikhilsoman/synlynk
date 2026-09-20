<!-- synlynk:start version="0.21.0-dev" tool="copilot" -->
## synlynk Session Protocol

### Session Start
1. Run `git config user.name` — this is your @username
2. Read `.synlynk/context.md` — full project state snapshot
3. Check `.synlynk/sentinel.md` for active alerts

### During Session
- Do NOT hand-edit `todo.md` directly — update task status in `state.db` via `synlynk story done <id>` (or `synlynk story create/update`).
- Append decisions to `project-docs/memory.md` with `[@username]` attribution
- Run `synlynk checkpoint` at every task boundary
- Never commit directly to `main`/`master` — create a worktree or branch first

### At Session End
- Append a summary entry to `project-docs/devlogs/<username>.md`
- Run `synlynk checkpoint` one final time

<!-- synlynk:end -->
