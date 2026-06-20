I will list the available permissions to see if there's an existing project workspace or database.
I will check the scratch directory to see if there is any active workspace or files matching synlynk.
I will list the contents of the `synlynk` directory in the scratch folder to see what is already there.
I will list the contents of the `project-docs` directory to see if the synlynk status/roadmap files exist.
I will inspect the existing `todo.md` and `devlog.md` files to see what the recorded tasks are.
I will view the devlog to get more detail on the last action.
I will check `roadmap.md` and `memory.md` to ensure our documentation remains synchronized.
I will view `memory.md` to see if there are any project conventions.
I will search the repository for mentions of `capability_scores` to inspect how the view is defined.
I will update the `devlog.md` file in the project documentation directory to record the code review session.
I will inspect the contents of `costs.md` to see how token usage is tracked.
I will log today's code review session in `costs.md`.
Last completed task: Write Autopilot initiative gap analysis ([docs/proposals/autopilot-gap-analysis-agy.md](file:///Users/nikhilsoman/.gemini/antigravity-cli/scratch/synlynk/docs/proposals/autopilot-gap-analysis-agy.md))
Next task from [todo.md](file:///Users/nikhilsoman/.gemini/antigravity-cli/scratch/synlynk/project-docs/todo.md): Refine decision flow templates for agents

***

# Technical Code Review: PR #50 (Capability Ledger Seeding & Routing)

### **Overall Verdict: Approve with Suggestions**
The PR successfully implements Phase A of the capability dogfooding plan by enabling history backfill and score attestation. The added `--force-agent` flag is a necessary routing escape hatch, and the status ledger integration is fully verified by unit tests. The PR is solid and ready to merge once the minor suggestions below are addressed.

### **PR Quality Score**: `8.5 / 10`

---

## Findings per Focus Area

### 1. **DB_PATH Duplication**
* **Severity**: Suggestion (Non-blocking cleanup)
* **Risk**: High risk of future divergence. If `synlynk.py` modifies database path resolution (e.g., adding custom config directories or environment variables like `SYNLYNK_DB_PATH`), the auxiliary scripts `attest_capability.py` and `backfill_capability.py` will read/write from the wrong SQLite database file or crash.
* **Concrete Fix**:
  Since both helper scripts live in the `bin/` directory alongside `synlynk.py`, import `synlynk` directly to reuse its `DB_PATH` or `_get_db()` helper. Add the following header imports to both `bin/attest_capability.py` and `bin/backfill_capability.py`:
  ```python
  import sys
  import os

  # Append bin directory to system path
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

  try:
      import synlynk
      DB_PATH = synlynk.DB_PATH
  except ImportError:
      # Optional fallback or raise error
      raise ImportError("Could not import synlynk from bin directory")
  ```

---

### 2. **prompt_via_arg Shell Safety**
* **Severity**: Suggestion / Minor Issue
* **Risk**: 
  - **No Direct Injection**: Wrapping `$PROMPT` in double quotes (`"$PROMPT"`) prevents recursive word splitting and command substitution on the parameter value during expansion, which mitigates direct injection of backticks or nested commands.
  - **Trailing Newlines Stripped**: The shell command substitution `$(cat ...)` naturally strips all trailing newlines. If a prompt's formatting depends on trailing newlines (e.g., trailing whitespace or formatting blocks), they will be lost.
  - **Argument Limits**: Passing the prompt as an argument (`agy -p "$PROMPT"`) makes it subject to the system's `ARG_MAX` limit. Extremely large prompt files will fail with `Argument list too long` (E2BIG).
* **Concrete Fix**:
  Rather than reading the file inside the shell command using `cat` and variable assignment, read it in Python and escape the content directly via `shlex.quote()`. This preserves trailing newlines and removes the external `cat` dependency:
  ```python
  if prompt_via_arg:
      # Read the prompt file in Python to preserve newlines and avoid 'cat'
      with open(prompt_file, "r", encoding="utf-8") as f:
          prompt_content = f.read()
      cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_content])
      shell_cmd = (
          f"{cmd_str} > {_shlex.quote(log_file)} 2>&1; "
          f"echo $? > {_shlex.quote(log_file)}.exit"
      )
  ```

---

### 3. **force_agent Gate**
* **Severity**: Approve
* **Analysis**: The override routing condition `if story_id and not force_agent` works correctly. Capability routing relies entirely on `story_id` mapping. If no `story_id` is provided, routing is already naturally bypassed because the system lacks the context to select a better agent. Therefore, `force_agent=True` has no effect when `story_id` is absent, which is correct and expected behavior.

---

### 4. **CAPABILITY LEDGER Query**
* **Severity**: Suggestion
* **Risk**: The query lacks filters to exclude unrated capabilities (`weighted_score IS NULL` or `sample_count = 0`). In SQLite, `NULL` values sort as lowest, so they won't dominate the results unless the ledger contains fewer than 3 rated capability combinations. However, displaying entries with no samples or blank scores (` — `) in the "Top 3" list of status output is noisy.
* **Concrete Fix**:
  Refine the database query in `cmd_status()` to filter out entries that have never been rated:
  ```python
  _cl_rows = _cl_conn.execute(
      "SELECT agent, model_version, engg_domain, phase, weighted_score, sample_count "
      "FROM capability_scores "
      "WHERE sample_count > 0 AND weighted_score IS NOT NULL "
      "ORDER BY weighted_score DESC LIMIT 3"
  ).fetchall()
  ```

---

### 5. **One-shot Script Hygiene**
* **Severity**: UX Suggestion (Clarity improvement)
* **Risk**: In `attest_capability.py`, the query is restricted to `signal_source='backfill'`. If a row is already successfully attested (which updates its source to `'human'`), the query returns nothing, and the script prints `[skip] {story_id} — no backfill row found`. This is confusing because a developer running it multiple times might assume the backfill itself failed rather than recognizing that the story has already been attested.
* **Concrete Fix**:
  Fetch by `story_id` first, and print an informative log based on the source state:
  ```python
  for story_id, data in ATTESTATIONS.items():
      row = conn.execute(
          "SELECT id, quality, signal_source FROM capability_ratings WHERE story_id=?",
          (story_id,)
      ).fetchone()

      if not row:
          print(f"  [skip] {story_id} — story not found in database")
          skipped += 1
          continue

      db_id, db_quality, db_source = row
      if db_source != 'backfill':
          print(f"  [skip] {story_id} — already attested (source: '{db_source}', current quality: {db_quality})")
          skipped += 1
          continue

      # Otherwise, update the row...
  ```

---

## Additional Review Findings (Bonus)

1. **Safety with missing `mergedAt` in `backfill_capability.py`**:
   The code does `merged_at = pr.get("mergedAt", "")[:19]`. If `mergedAt` is present in the JSON payload but set to `null` (None in Python), calling `[:19]` will raise a `TypeError: 'NoneType' object is not subscriptable` and crash the script.
   *Fix*: Change to `(pr.get("mergedAt") or "")[:19].replace("T", " ")`.

2. **Missing `gh` installation checks in `backfill_capability.py`**:
   If the host machine does not have the GitHub CLI (`gh`) installed, `subprocess.run` raises `FileNotFoundError`.
   *Fix*: Wrap the subprocess call in a `try...except FileNotFoundError` block and output a clean error:
   ```python
   try:
       r = subprocess.run(cmd, capture_output=True, text=True)
   except FileNotFoundError:
       print("  ERROR: 'gh' CLI tool not found. Please install the GitHub CLI and authenticate via 'gh auth login'.")
       sys.exit(1)
   ```
