# Runbook: VS Code Extension Marketplace Publishing & Account Operations

- **Component:** [`clients/vscode`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode)
- **Extension Identifier:** `synlynk.synlynk-vscode`
- **Configured Publisher:** `synlynk` (in [`clients/vscode/package.json`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode/package.json))
- **Primary CI Workflow:** [`.github/workflows/release-vscode.yml`](file:///Users/nikhilsoman/dev/synlynk/.github/workflows/release-vscode.yml)
- **Target Registries:**
  1. [Visual Studio Marketplace](https://marketplace.visualstudio.com/) (Microsoft VS Code)
  2. [Open VSX Registry](https://open-vsx.org/) (VSCodium, Cursor, Gitpod, Eclipse Theia)

---

## 1. Overview & Architecture

Synlynk distributes a lightweight, zero-runtime-dependency VS Code extension (`clients/vscode`) that bridges host-local `synlynk` CLI daemons into developer IDEs. To ensure ubiquitous reach across both official Microsoft builds and open-source forks (e.g., Cursor, VSCodium), the extension is multi-homed on both the **Visual Studio Marketplace** and the **Open VSX Registry**.

This runbook documents the end-to-end setup, account registration, token provisioning, automated release execution, and operational troubleshooting.

---

## 2. Registry 1: Visual Studio Marketplace (Microsoft)

### 2.1 Azure DevOps Organization Setup
Microsoft uses Azure DevOps as the identity and authentication provider for Visual Studio Marketplace publishers.

1. Sign in to [Azure DevOps](https://dev.azure.com/) using the Microsoft account designated for Synlynk project management.
2. If you do not have an organization, create one (e.g., `https://dev.azure.com/synlynk-org`). The organization name does not need to match the extension publisher name, but creating a dedicated organization keeps tokens isolated.

### 2.2 Personal Access Token (PAT) Generation
The `@vscode/vsce` publishing CLI requires an Azure DevOps Personal Access Token with specific marketplace scopes.

1. In Azure DevOps, click the **User Settings** gear icon (top right, next to your profile picture) $\rightarrow$ select **Personal access tokens**.
2. Click **+ New Token**.
3. Configure the token parameters:
   - **Name:** `synlynk-vsce-publisher`
   - **Organization:** Select **All accessible organizations** (*CRITICAL:* selecting a single specific organization will cause marketplace authentication to fail).
   - **Expiration:** Choose **90 days** or custom (up to 1 year). Set a recurring reminder to rotate before expiration.
   - **Scopes:** Click **Show all scopes** at the bottom:
     - Scroll to **Marketplace**.
     - Check **Acquisition** (`vso.extension.acquisition`).
     - Check **Manage** (`vso.extension.manage`).
4. Click **Create**.
5. **Copy and securely store the PAT immediately** (Azure DevOps will never display it again).

### 2.3 Publisher Creation & Verification
1. Navigate to the [Visual Studio Marketplace Management Portal](https://marketplace.visualstudio.com/manage).
2. Sign in with the same Microsoft account.
3. Click **Create publisher** (or edit your existing publisher).
4. Fill in the publisher details:
   - **Name (ID):** `synlynk` (*CRITICAL:* Must be strictly lowercase `synlynk` to match `"publisher": "synlynk"` in [`clients/vscode/package.json`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode/package.json)).
   - **Display name:** `Synlynk`
   - **Contact email:** Your project administrative contact.
   - **Website / Description:** `https://github.com/nikhilsoman/synlynk`
5. Click **Save**.
6. *(Optional but Recommended)* Verified Publisher Domain: If you control `synlynk.org` or `synlynk.dev`, follow Microsoft's DNS TXT record verification wizard to obtain a verified badge on the marketplace.

---

## 3. Registry 2: Open VSX Registry (Eclipse Foundation)

The Open VSX Registry powers IDEs that cannot legally or technically use Microsoft's proprietary marketplace (Cursor, VSCodium, Gitpod, Theia).

### 3.1 Account Creation
1. Navigate to [open-vsx.org](https://open-vsx.org/).
2. Click **Log In** (top right) and authenticate via GitHub (using your `nikhilsoman` GitHub identity or project account).

### 3.2 Namespace Creation (`synlynk`)
In Open VSX, extensions are organized under namespaces matching the publisher ID.

1. Click your avatar icon (top right) $\rightarrow$ select **Settings**.
2. In the left navigation, click **Namespaces**.
3. Under **Create a Namespace**:
   - Enter **Name:** `synlynk` (strictly lowercase).
   - Provide description / URL (e.g. `https://github.com/nikhilsoman/synlynk`).
4. Click **Create**.
5. Once created, your user will be an owner of the `synlynk` namespace.

### 3.3 Access Token Generation
1. In the **Settings** menu, click **Access Tokens** in the left sidebar.
2. Enter a description: `synlynk-ovsx-ci`.
3. Click **Generate Token**.
4. **Copy and securely store the token immediately**.

---

## 4. GitHub Actions Secrets Configuration

The CI/CD pipeline reads both publishing tokens from GitHub repository secrets.

1. Navigate to the Synlynk GitHub repository: `https://github.com/nikhilsoman/synlynk/settings/secrets/actions`.
2. Under **Repository secrets**, ensure the following two secrets are set:

| Secret Name | Value Description | Provider |
| :--- | :--- | :--- |
| `VSCE_PAT` | The Azure DevOps Personal Access Token (Marketplace Manage scope) | Visual Studio Marketplace |
| `OVSX_PAT` | The Open VSX API Access Token | Eclipse Foundation Open VSX |

3. If updating or rotating tokens, click the pencil icon next to the secret name, paste the new token, and click **Update secret**.

---

## 5. Automated Release Pipeline

The publishing workflow is automated via GitHub Actions in [`.github/workflows/release-vscode.yml`](file:///Users/nikhilsoman/dev/synlynk/.github/workflows/release-vscode.yml).

### 5.1 Trigger 1: Semantic Git Version Tag (Standard Release)
Whenever a new extension release is ready:

1. Update the version number in [`clients/vscode/package.json`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode/package.json) (e.g. `"version": "0.1.1"`).
2. Commit and push the version bump to `main`:
   ```bash
   git commit -am "chore(vscode): bump extension version to 0.1.1"
   git push origin main
   ```
3. Tag the release commit with a `v` prefix and push:
   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```
4. The workflow will automatically launch, package the extension, publish to both marketplaces, and upload the `.vsix` file to GitHub run artifacts.

### 5.2 Trigger 2: Manual Workflow Dispatch (Ad-Hoc / Dry-Run)
To publish without pushing a git tag, or to retry a failed publication:

1. Go to `https://github.com/nikhilsoman/synlynk/actions/workflows/release-vscode.yml`.
2. Click **Run workflow** (top right dropdown).
3. Select branch `main`.
4. Click **Run workflow**.

---

## 6. Local Packaging & Side-Loading Verification

Before pushing releases to public marketplaces, test the extension bundle locally.

### 6.1 Package VSIX Locally
From the repository root:

```bash
cd clients/vscode

# 1. Install dev dependencies
npm ci

# 2. Run unit tests
node test/runTest.js

# 3. Package extension into .vsix (no runtime dependencies, skips license prompt)
npx @vscode/vsce package --no-dependencies --skip-license
```

This will produce a file named `synlynk-vscode-0.1.0.vsix` in `clients/vscode/`.

### 6.2 Side-Load in VS Code or Cursor
1. Open VS Code or Cursor.
2. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
3. Type: `Extensions: Install from VSIX...` and press Enter.
4. Select the generated `synlynk-vscode-*.vsix` file.
5. Verify:
   - Synlynk logo appears on the Activity Bar.
   - **Fleet Health & Quotas** TreeView renders active harnesses.
   - **Project Goals & Milestones** TreeView lists active GOVERNS goals.
   - **Dispatched Jobs** TreeView displays active daemon jobs.
   - Status bar item displays `Synlynk: <status>`.

### 6.3 Manual Emergency Publish via CLI
If GitHub Actions is unavailable, publish directly from a terminal with the credentials exported:

```bash
cd clients/vscode

# Publish to Visual Studio Marketplace
VSCE_PAT="<your-vsce-pat>" npx @vscode/vsce publish --skip-license

# Publish to Open VSX Registry
npx ovsx publish $(ls synlynk-vscode-*.vsix) -p "<your-ovsx-pat>"
```

---

## 7. Troubleshooting & Failure Modes

### 7.1 `401 Unauthorized` or `403 Forbidden` on VSCE Publish
- **Root Cause:** The Azure DevOps PAT expired or was created with an organization scope restricted to a single project rather than "All accessible organizations".
- **Fix:** Regenerate the token in Azure DevOps ensuring **All accessible organizations** is checked and both **Acquisition** and **Manage** are selected under Marketplace. Update `VSCE_PAT` in GitHub secrets.

### 7.2 `Publisher 'synlynk' does not exist`
- **Root Cause:** The publisher ID in [`clients/vscode/package.json`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode/package.json) does not match the publisher registered on `marketplace.visualstudio.com/manage`.
- **Fix:** Check the exact casing of the publisher ID. Publisher IDs are immutable and case-sensitive. It must be lowercase `synlynk`.

### 7.3 `Namespace 'synlynk' does not belong to user` (Open VSX)
- **Root Cause:** The GitHub account that generated `OVSX_PAT` is not listed as an owner/member of namespace `synlynk` on `open-vsx.org`.
- **Fix:** Log in to `open-vsx.org`, go to **Settings** $\rightarrow$ **Namespaces**, and create or add the user to the `synlynk` namespace.

### 7.4 `Version 0.1.0 already exists`
- **Root Cause:** Marketplaces reject re-publishing an existing version number.
- **Fix:** Increment `"version"` in [`clients/vscode/package.json`](file:///Users/nikhilsoman/dev/synlynk/clients/vscode/package.json) (following Semantic Versioning: `PATCH` for fixes, `MINOR` for features).

### 7.5 `Production dependencies must be 0, found N`
- **Root Cause:** A npm package was installed under `"dependencies"` instead of `"devDependencies"`.
- **Architecture Mandate:** The Synlynk VS Code client is strictly zero-dependency; it delegates to the host-local CLI via JSON IPC. Move any runtime dependencies to devDependencies or vendor them.

---

## 8. Annual Maintenance & Token Rotation Schedule

| Item | Interval | Procedure |
| :--- | :--- | :--- |
| **`VSCE_PAT` Rotation** | Every 90–180 days | Generate new token in Azure DevOps $\rightarrow$ Update GitHub Secret `VSCE_PAT`. |
| **`OVSX_PAT` Rotation** | Annual | Generate new token in `open-vsx.org/user-settings/tokens` $\rightarrow$ Update `OVSX_PAT`. |
| **VS Code Engine Compatibility** | Bi-annual | Verify minimum supported VS Code engine (`engines.vscode`) against current VS Code LTS. |
