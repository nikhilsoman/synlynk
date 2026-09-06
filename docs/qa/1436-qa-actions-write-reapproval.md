# Operator Runbook: Re-approving `actions: write` for the `qa` GitHub App (#1436)

## Context & Background

During autonomous operations and identity routing (#1436), the `qa` role failed when attempting to retrigger failed workflow runs (`gh run rerun --failed`):

```text
Resource not accessible by integration
```

The installed `synlynk-synlynk-qa` GitHub App possessed only `actions: read` permissions.

In PR #1458, `_build_app_manifest_url` in `synlynk/team.py` was updated so that new repository initializations (`synlynk init`) request both `administration: write` and `actions: write` for roles designated with merge authority (`can_merge: ["qa"]`).

However, updating the manifest definition in code **does not automatically update or re-provision already-installed GitHub Apps**. GitHub's security model dictates that whenever a GitHub App requests additional permissions, the installation owner (Nikhil) must manually approve the permission update in the GitHub UI. Autonomous agents cannot self-escalate permissions.

> [!IMPORTANT]
> **No Secrets or Credentials:** Never paste PEM private keys, App tokens, client secrets, or numerical installation IDs into this or any other documentation file.

---

## Installer Steps (Manual Action for Nikhil)

To grant and activate `actions: write` on the installed `synlynk-synlynk-qa` App:

1. **Navigate to GitHub App Settings:**
   - In your browser, open GitHub: **Settings** → **Developer Settings** → **GitHub Apps** (or directly under the owner account's GitHub Apps).
2. **Select the QA App:**
   - Click `synlynk-synlynk-qa` (or the synlynk qa App).
3. **Update Permissions:**
   - In the left sidebar navigation, click **Permissions & events**.
   - Under **Repository permissions**, locate **Actions**.
   - Change the dropdown from *Read-only* to **Read and write**.
   - Scroll down to the bottom of the page and click **Save changes**.
4. **Accept Installation Permission Update:**
   - Accept the installation confirmation email or web prompt:
     - Either click through the email notification prompt from GitHub, or
     - In the left sidebar of the App settings, click **Install App**, select the settings/gear next to `nikhilsoman`, and click **Review and accept permissions** (or **Accept**).

---

## How to Verify

Once the re-approval is confirmed, verify the updated permissions via the CLI:

### 1. What NOT to Run
GitHub App installation tokens are not user tokens and cannot query the `/user` endpoint. Running:
```bash
synlynk gh --role qa -- api user
```
will always 403 (`Resource not accessible by integration`). This is normal GitHub App behavior and does not indicate an issue with repository permissions.

### 2. Verification Commands
Instead, verify repository Actions permissions using the GitHub API or a dry `gh run` command:

- **Check Actions runs via GitHub API:**
  ```bash
  synlynk gh --role qa -- api repos/nikhilsoman/synlynk/actions/runs --jq '.[0].id'
  ```
  *Expected:* Returns the ID of the latest workflow run (or empty if no runs exist) with HTTP 200 without a 403 error.

- **Dry run listing:**
  ```bash
  synlynk gh --role qa -- run list
  ```
  *Expected:* Lists recent workflow runs without 403 Forbidden errors.

- **Rerun failed workflows (when applicable):**
  ```bash
  synlynk gh --role qa -- run rerun <run-id> --failed
  ```
  *Expected:* Successfully triggers the rerun without `Resource not accessible by integration`.
