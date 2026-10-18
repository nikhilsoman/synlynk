# Synlynk VS Code Client (`synlynk-vscode`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and package the official, zero-dependency Synlynk VS Code extension (`clients/vscode/`, `synlynk-vscode-0.1.0.vsix`) providing non-disruptive multi-agent orchestration, leased worktree diff review, fleet monitoring, and goal-linked dispatch inside VS Code, Cursor, and Windsurf.

**Architecture:** Pure zero-npm-dependency thin client in Node.js delegating to the `synlynk` CLI via JSON RPC for discrete user actions and reactive event-tailing over `.synlynk/events.jsonl` (emitted by `uxcore.py`) for live TreeView and Status Bar updates. Dispatches run in background leased git worktrees, leaving the developer's open file buffers completely untouched, with completions reviewed via native side-by-side `vscode.diff`.

**Tech Stack:** JavaScript (Node.js 18+), VS Code Extensibility API (1.85.0+), `@vscode/vsce`, Mocha/assert test harness, GitHub Actions CI.

**Spec:** [`docs/superpowers/specs/2026-10-18-vscode-extension-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-10-18-vscode-extension-design.md) (approved consensus decision `dec-7dabb36d`).

## Global Constraints

- Zero npm runtime dependencies (`dependencies: {}` in `package.json`). All runtime code must use standard Node.js built-ins (`fs`, `path`, `child_process`, `events`) and the `vscode` API.
- Never mutate the developer's active working tree during agent dispatch; all dispatches execute in leased git worktrees (`/worktrees/djob-*`).
- 1-click in-editor merge is held back from v0.1; merging remains guarded by non-author review policy and `synlynk pr check`.
- Event tailing over `.synlynk/events.jsonl` must be debounced (200ms) to prevent SQLite WAL contention on `state.db`.
- Full compliance with VS Code Workspace Trust (`vscode.workspace.isTrusted`); untrusted workspaces must disable dispatch, worktree operations, and CLI mutations.
- Extension packaging (`vsce package`) must produce a `.vsix` bundle under 2MB with cold-start activation under 50ms.
- Every commit must include the trailer: `Co-Authored-By: AGY <noreply@antigravity.dev>`.

---

### Task 1: Extension Scaffolding, Manifest & Zero-Dependency Validation

**Files:**
- Create: `clients/vscode/package.json`
- Create: `clients/vscode/.vscodeignore`
- Create: `clients/vscode/media/synlynk-icon.svg`
- Create: `clients/vscode/test/runTest.js`
- Create: `clients/vscode/test/suite/index.js`
- Test: `clients/vscode/test/suite/scaffolding.test.js`

**Interfaces:**
- Produces: Base extension directory structure, npm scripts (`test`, `package`), extension manifest contributing container `synlynk-sidebar` and views `synlynk-fleet`, `synlynk-goals`, `synlynk-jobs`.

- [ ] **Step 1: Write the failing test for manifest validation**

```javascript
// clients/vscode/test/suite/scaffolding.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");

describe("Scaffolding & Manifest Validation", () => {
  const pkgPath = path.resolve(__dirname, "../../package.json");

  it("package.json exists and has valid metadata", () => {
    assert.ok(fs.existsSync(pkgPath), "package.json must exist");
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
    assert.strictEqual(pkg.name, "synlynk-vscode");
    assert.strictEqual(pkg.publisher, "synlynk");
    assert.strictEqual(pkg.version, "0.1.0");
    assert.strictEqual(pkg.main, "./extension.js");
  });

  it("enforces ZERO runtime dependencies", () => {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
    const deps = pkg.dependencies || {};
    assert.strictEqual(
      Object.keys(deps).length,
      0,
      `Runtime dependencies must be empty, found: ${JSON.stringify(deps)}`
    );
  });

  it("declares required views containers and views", () => {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
    const contributes = pkg.contributes || {};
    assert.ok(contributes.viewsContainers, "Must declare viewsContainers");
    assert.ok(contributes.viewsContainers.activitybar, "Must declare activitybar container");
    assert.ok(contributes.views["synlynk-sidebar"], "Must contribute views to synlynk-sidebar");
    
    const viewIds = contributes.views["synlynk-sidebar"].map((v) => v.id);
    assert.ok(viewIds.includes("synlynk-fleet"), "Must include synlynk-fleet view");
    assert.ok(viewIds.includes("synlynk-goals"), "Must include synlynk-goals view");
    assert.ok(viewIds.includes("synlynk-jobs"), "Must include synlynk-jobs view");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "require('./clients/vscode/test/suite/scaffolding.test.js')"`
Expected: FAIL with "Cannot find module" or "package.json must exist"

- [ ] **Step 3: Implement package.json, .vscodeignore, and synlynk-icon.svg**

```json
// clients/vscode/package.json
{
  "name": "synlynk-vscode",
  "displayName": "Synlynk Multi-Agent Engineering",
  "description": "Multi-agent orchestration, leased worktree isolation, adversarial verification, and goal tracking for Synlynk.",
  "version": "0.1.0",
  "publisher": "synlynk",
  "repository": {
    "type": "git",
    "url": "https://github.com/nikhilsoman/synlynk"
  },
  "engines": {
    "vscode": "^1.85.0"
  },
  "categories": [
    "Programming Languages",
    "Machine Learning",
    "Testing",
    "Other"
  ],
  "keywords": [
    "synlynk",
    "multi-agent",
    "codex",
    "claude",
    "grok",
    "gemini",
    "worktree"
  ],
  "main": "./extension.js",
  "activationEvents": [
    "onStartupFinished"
  ],
  "capabilities": {
    "untrustedWorkspaces": {
      "supported": "limited",
      "description": "Read-only fleet and goal inspection is supported in untrusted workspaces. Dispatches and worktree modifications require a trusted workspace."
    }
  },
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "synlynk-sidebar",
          "title": "Synlynk",
          "icon": "media/synlynk-icon.svg"
        }
      ]
    },
    "views": {
      "synlynk-sidebar": [
        {
          "id": "synlynk-fleet",
          "name": "Fleet Health & Quotas",
          "contextualTitle": "Synlynk Fleet"
        },
        {
          "id": "synlynk-goals",
          "name": "Project Goals & Milestones",
          "contextualTitle": "Synlynk Goals"
        },
        {
          "id": "synlynk-jobs",
          "name": "Dispatched Jobs & Reviews",
          "contextualTitle": "Synlynk Jobs"
        }
      ]
    },
    "commands": [
      {
        "command": "synlynk.dispatch",
        "title": "Synlynk: Dispatch Task",
        "category": "Synlynk"
      },
      {
        "command": "synlynk.doctor",
        "title": "Synlynk: Run Doctor Diagnostics",
        "category": "Synlynk"
      },
      {
        "command": "synlynk.diffReview",
        "title": "Synlynk: Review Worktree Diff",
        "category": "Synlynk"
      },
      {
        "command": "synlynk.prCheck",
        "title": "Synlynk: Check PR & Merge Policy",
        "category": "Synlynk"
      },
      {
        "command": "synlynk.refreshAll",
        "title": "Synlynk: Refresh Status",
        "category": "Synlynk",
        "icon": "$(refresh)"
      },
      {
        "command": "synlynk.viewJobLog",
        "title": "Synlynk: View Job Log",
        "category": "Synlynk"
      }
    ],
    "menus": {
      "view/title": [
        {
          "command": "synlynk.refreshAll",
          "when": "view == synlynk-fleet || view == synlynk-goals || view == synlynk-jobs",
          "group": "navigation"
        }
      ],
      "view/item/context": [
        {
          "command": "synlynk.diffReview",
          "when": "view == synlynk-jobs && viewItem == job-complete",
          "group": "inline@1"
        },
        {
          "command": "synlynk.prCheck",
          "when": "view == synlynk-jobs && viewItem == job-complete",
          "group": "inline@2"
        },
        {
          "command": "synlynk.viewJobLog",
          "when": "view == synlynk-jobs",
          "group": "inline@3"
        }
      ]
    }
  },
  "dependencies": {},
  "devDependencies": {
    "@types/mocha": "^10.0.6",
    "@types/node": "^18.19.0",
    "@types/vscode": "^1.85.0",
    "mocha": "^10.3.0"
  },
  "scripts": {
    "test": "node ./test/runTest.js"
  }
}
```

```
// clients/vscode/.vscodeignore
.vscode/**
.gitignore
test/**
node_modules/**
*.vsix
.DS_Store
```

```xml
<!-- clients/vscode/media/synlynk-icon.svg -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="3"></circle>
  <path d="M12 2v4m0 12v4M2 12h4m12 0h4"></path>
  <path d="m4.93 4.93 2.83 2.83m8.48 8.48 2.83 2.83M4.93 19.07l2.83-2.83m8.48-8.48 2.83-2.83"></path>
</svg>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/scaffolding.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/package.json clients/vscode/.vscodeignore clients/vscode/media/synlynk-icon.svg clients/vscode/test/suite/scaffolding.test.js
git commit -m "feat(vscode): scaffold extension manifest and zero-dependency configuration

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 2: Host RPC Bridge, Version Handshake & Error Boundaries

**Files:**
- Create: `clients/vscode/src/cli.js`
- Create: `clients/vscode/src/util/errorBoundary.js`
- Test: `clients/vscode/test/suite/cli.test.js`

**Interfaces:**
- Consumes: Host environment PATH, Node.js `child_process.execFile`.
- Produces: `runSynlynk(subcommand, args, options)` returning Promise<Object>, `checkCliCompatibility()` returning Promise<{ compatible: boolean, version: string, error?: string }>.

- [ ] **Step 1: Write the failing test for RPC bridge and version check**

```javascript
// clients/vscode/test/suite/cli.test.js
const assert = require("assert");
const { runSynlynk, checkCliCompatibility, parseCliJson } = require("../../src/cli");
const { formatError } = require("../../src/util/errorBoundary");

describe("Host RPC Bridge & Version Handshake", () => {
  it("parseCliJson correctly parses valid JSON", () => {
    const raw = '{"status": "ok", "fleet": ["claude", "codex"]}';
    const parsed = parseCliJson(raw, "status");
    assert.strictEqual(parsed.status, "ok");
    assert.strictEqual(parsed.fleet.length, 2);
  });

  it("parseCliJson throws descriptive error on malformed JSON", () => {
    assert.throws(
      () => parseCliJson("Not JSON output: traceback error", "status"),
      /Malformed JSON output from synlynk status/
    );
  });

  it("formatError distinguishes offline and network failures", () => {
    const netErr = new Error("getaddrinfo ENOTFOUND generativelanguage.googleapis.com");
    const formatted = formatError(netErr);
    assert.strictEqual(formatted.type, "NETWORK_OFFLINE");
    assert.ok(formatted.message.includes("Offline or unreachable API endpoint"));
  });

  it("checkCliCompatibility verifies semver requirement", async () => {
    // Mock run function to simulate synlynk --version
    const mockRunner = async () => ({ version: "0.23.0" });
    const result = await checkCliCompatibility(mockRunner);
    assert.strictEqual(result.compatible, true);
    assert.strictEqual(result.version, "0.23.0");

    const mockOldRunner = async () => ({ version: "0.19.2" });
    const oldResult = await checkCliCompatibility(mockOldRunner);
    assert.strictEqual(oldResult.compatible, false);
    assert.ok(oldResult.error.includes("Upgrade required"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/cli.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/cli'"

- [ ] **Step 3: Implement src/util/errorBoundary.js and src/cli.js**

```javascript
// clients/vscode/src/util/errorBoundary.js
function formatError(err) {
  if (!err) return { type: "UNKNOWN", message: "Unknown error occurred" };
  const msg = err.message || String(err);

  if (msg.includes("ENOTFOUND") || msg.includes("ECONNREFUSED") || msg.includes("fetch failed")) {
    return {
      type: "NETWORK_OFFLINE",
      message: `Offline or unreachable API endpoint: ${msg}`
    };
  }

  if (msg.includes("ENOENT") && msg.includes("synlynk")) {
    return {
      type: "CLI_MISSING",
      message: "Synlynk CLI binary not found on system PATH. Please run 'pipx install synlynk' or configure synlynk.cliPath."
    };
  }

  if (msg.includes("Malformed JSON output")) {
    return {
      type: "MALFORMED_OUTPUT",
      message: msg
    };
  }

  return {
    type: "EXECUTION_ERROR",
    message: msg
  };
}

module.exports = { formatError };
```

```javascript
// clients/vscode/src/cli.js
const { execFile } = require("child_process");
const { formatError } = require("./util/errorBoundary");

function parseCliJson(stdout, subcommand) {
  try {
    return JSON.parse(stdout);
  } catch (err) {
    throw new Error(`Malformed JSON output from synlynk ${subcommand}: ${stdout}`);
  }
}

function runSynlynk(subcommand, args = [], options = {}) {
  const binary = options.cliPath || "synlynk";
  const cmdArgs = [subcommand, ...args, "--json"];

  return new Promise((resolve, reject) => {
    execFile(
      binary,
      cmdArgs,
      {
        cwd: options.cwd || process.cwd(),
        timeout: options.timeout || 30000,
        maxBuffer: 10 * 1024 * 1024,
        ...options.execOptions
      },
      (err, stdout, stderr) => {
        if (err) {
          const formatted = formatError(new Error(stderr || err.message));
          return reject(formatted);
        }
        try {
          const parsed = parseCliJson(stdout, subcommand);
          resolve(parsed);
        } catch (parseErr) {
          reject(formatError(parseErr));
        }
      }
    );
  });
}

function parseSemver(versionStr) {
  const match = (versionStr || "").match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return [0, 0, 0];
  return [parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10)];
}

async function checkCliCompatibility(runner = runSynlynk, options = {}) {
  try {
    const data = await runner("--version", [], options);
    const verStr = typeof data === "string" ? data : (data.version || "0.0.0");
    const [maj, min] = parseSemver(verStr);

    // Require >= 0.23.0
    if (maj > 0 || (maj === 0 && min >= 23)) {
      return { compatible: true, version: verStr };
    }

    return {
      compatible: false,
      version: verStr,
      error: `Upgrade required: detected synlynk v${verStr}, but >= v0.23.0 is required.`
    };
  } catch (err) {
    return {
      compatible: false,
      version: "unknown",
      error: err.message
    };
  }
}

module.exports = {
  runSynlynk,
  parseCliJson,
  checkCliCompatibility
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/cli.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/util/errorBoundary.js clients/vscode/src/cli.js clients/vscode/test/suite/cli.test.js
git commit -m "feat(vscode): implement host RPC bridge, CLI version handshake and error boundary

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 3: Reactive Event-Tailing Substrate

**Files:**
- Create: `clients/vscode/src/eventWatcher.js`
- Test: `clients/vscode/test/suite/eventWatcher.test.js`

**Interfaces:**
- Consumes: `.synlynk/events.jsonl` in workspace root.
- Produces: `watchEvents(workspaceRoot, onEvent, options)` returning `{ dispose: () => void }`. Emits parsed JSON events with 200ms debounced notifications to prevent SQLite WAL churn.

- [ ] **Step 1: Write the failing test for eventWatcher**

```javascript
// clients/vscode/test/suite/eventWatcher.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { watchEvents } = require("../../src/eventWatcher");

describe("Reactive Event-Tailing Substrate", () => {
  let tmpDir;
  let synlynkDir;
  let eventsFile;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "synlynk-event-test-"));
    synlynkDir = path.join(tmpDir, ".synlynk");
    fs.mkdirSync(synlynkDir, { recursive: true });
    eventsFile = path.join(synlynkDir, "events.jsonl");
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("handles missing events.jsonl gracefully", () => {
    const watcher = watchEvents(tmpDir, () => {});
    assert.strictEqual(typeof watcher.dispose, "function");
    watcher.dispose();
  });

  it("tails and parses newly appended JSON lines", (done) => {
    fs.writeFileSync(eventsFile, '{"event": "init", "data": "initial"}\n');

    const received = [];
    const watcher = watchEvents(
      tmpDir,
      (ev) => {
        received.push(ev);
        if (received.length === 2) {
          assert.strictEqual(received[0].event, "job_started");
          assert.strictEqual(received[1].event, "job_finished");
          watcher.dispose();
          done();
        }
      },
      { debounceMs: 20 }
    );

    setTimeout(() => {
      fs.appendFileSync(eventsFile, '{"event": "job_started", "job_id": "djob-1"}\n');
      fs.appendFileSync(eventsFile, '{"event": "job_finished", "job_id": "djob-1", "status": "VERIFIED"}\n');
    }, 50);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/eventWatcher.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/eventWatcher'"

- [ ] **Step 3: Implement src/eventWatcher.js**

```javascript
// clients/vscode/src/eventWatcher.js
const fs = require("fs");
const path = require("path");

function watchEvents(workspaceRoot, onEvent, options = {}) {
  const eventsFile = path.join(workspaceRoot, ".synlynk", "events.jsonl");
  const debounceMs = options.debounceMs || 200;

  if (!fs.existsSync(eventsFile)) {
    return { dispose: () => {} };
  }

  let fileSize = 0;
  try {
    fileSize = fs.statSync(eventsFile).size;
  } catch (_) {
    return { dispose: () => {} };
  }

  let debounceTimer = null;
  let isClosed = false;

  function processNewLines() {
    if (isClosed) return;
    let newSize = 0;
    try {
      newSize = fs.statSync(eventsFile).size;
    } catch (_) {
      return;
    }

    if (newSize <= fileSize) return;

    const stream = fs.createReadStream(eventsFile, {
      start: fileSize,
      end: newSize,
      encoding: "utf8"
    });

    let chunkBuffer = "";
    stream.on("data", (chunk) => {
      chunkBuffer += chunk;
    });

    stream.on("end", () => {
      fileSize = newSize;
      const lines = chunkBuffer.split("\n").filter((l) => l.trim().length > 0);
      for (const line of lines) {
        try {
          const ev = JSON.parse(line);
          onEvent(ev);
        } catch (_) {
          // Ignore partial or malformed line
        }
      }
    });
  }

  let fsWatcher = null;
  try {
    fsWatcher = fs.watch(eventsFile, (eventType) => {
      if (eventType === "change") {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(processNewLines, debounceMs);
      }
    });
  } catch (_) {
    return { dispose: () => {} };
  }

  return {
    dispose: () => {
      isClosed = true;
      if (debounceTimer) clearTimeout(debounceTimer);
      if (fsWatcher) fsWatcher.close();
    }
  };
}

module.exports = { watchEvents };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/eventWatcher.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/eventWatcher.js clients/vscode/test/suite/eventWatcher.test.js
git commit -m "feat(vscode): implement reactive event tailing for events.jsonl

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 4: Fleet Health TreeDataProvider

**Files:**
- Create: `clients/vscode/src/providers/fleetProvider.js`
- Test: `clients/vscode/test/suite/fleetProvider.test.js`

**Interfaces:**
- Consumes: `runSynlynk("status", ...)` and event stream.
- Produces: `FleetTreeDataProvider` implementing `vscode.TreeDataProvider`.

- [ ] **Step 1: Write the failing test for fleetProvider**

```javascript
// clients/vscode/test/suite/fleetProvider.test.js
const assert = require("assert");
const { FleetTreeDataProvider, formatFleetItems } = require("../../src/providers/fleetProvider");

describe("Fleet Health TreeDataProvider", () => {
  it("formats fleet status items into TreeItems with tooltip microcopy", () => {
    const rawStatus = {
      harnesses: [
        { name: "claude", status: "ready", quota_reset: "2026-10-19T00:00:00Z", role: "architect" },
        { name: "codex", status: "ready", quota_reset: "2026-10-22T00:00:00Z", role: "implementer" },
        { name: "agy", status: "active", quota_reset: null, role: "implementer" },
        { name: "grok", status: "recharge_needed", quota_reset: "2026-10-18T12:00:00Z", role: "verifier" }
      ],
      spend: {
        session_dollars: 4.12,
        fleet_total_dollars: 18.47,
        tokens_total: 142000
      }
    };

    const items = formatFleetItems(rawStatus);
    assert.strictEqual(items.length, 5); // 4 harnesses + 1 spend summary item
    
    // Harness item assertions
    const claudeItem = items.find((i) => i.label.includes("Claude"));
    assert.ok(claudeItem, "Claude item must exist");
    assert.ok(claudeItem.tooltip.includes("Model A authors, Model B audits"), "Tooltip must include microcopy");

    // Spend item assertions
    const spendItem = items.find((i) => i.id === "fleet-spend");
    assert.ok(spendItem, "Spend item must exist");
    assert.ok(spendItem.label.includes("$18.47"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/fleetProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/providers/fleetProvider'"

- [ ] **Step 3: Implement src/providers/fleetProvider.js**

```javascript
// clients/vscode/src/providers/fleetProvider.js
const { runSynlynk } = require("../cli");

const HARNESS_DISPLAY = {
  claude: { name: "Claude Sonnet", icon: "●" },
  codex: { name: "OpenAI Codex", icon: "●" },
  agy: { name: "Google Agy (Gemini)", icon: "●" },
  grok: { name: "xAI Grok", icon: "●" },
  local: { name: "Local Inference (oMLX/Aider)", icon: "●" }
};

function formatFleetItems(statusData) {
  const items = [];
  const harnesses = (statusData && statusData.harnesses) || [];

  for (const h of harnesses) {
    const meta = HARNESS_DISPLAY[h.name] || { name: h.name, icon: "●" };
    const statusText = h.status === "ready" ? "Ready" : h.status === "active" ? "Active (Driving)" : "Recharge Needed";
    const label = `${meta.name} — ${statusText}`;

    const tooltip = `**Harness:** ${meta.name}\n` +
      `**Assigned Role:** ${h.role || "general"}\n` +
      `**Status:** ${statusText}\n` +
      `**Quota Reset:** ${h.quota_reset || "Unlimited"}\n\n` +
      `*Synlynk Capability Routing: Model A authors, Model B audits.*`;

    items.push({
      id: `harness-${h.name}`,
      label,
      tooltip,
      status: h.status
    });
  }

  const spend = (statusData && statusData.spend) || { session_dollars: 0, fleet_total_dollars: 0, tokens_total: 0 };
  items.push({
    id: "fleet-spend",
    label: `Spend (Session): $${spend.session_dollars.toFixed(2)} | Fleet: $${spend.fleet_total_dollars.toFixed(2)}`,
    tooltip: `**Dual-Ledger Accounting:**\nTracks real subscription-amortized expenditure alongside raw frontier API value.\nTokens: ${spend.tokens_total.toLocaleString()}`
  });

  return items;
}

class FleetTreeDataProvider {
  constructor(workspaceRoot) {
    this.workspaceRoot = workspaceRoot;
    this._onDidChangeTreeData = null; // Set in VS Code extension host
    this.cachedData = null;
  }

  refresh() {
    this.cachedData = null;
    if (this._onDidChangeTreeData) {
      this._onDidChangeTreeData.fire();
    }
  }

  async getChildren(element) {
    if (element) return [];
    try {
      if (!this.cachedData) {
        this.cachedData = await runSynlynk("status", [], { cwd: this.workspaceRoot });
      }
      return formatFleetItems(this.cachedData);
    } catch (err) {
      return [{
        id: "fleet-error",
        label: `Fleet Status Offline: ${err.message}`,
        tooltip: "Run 'synlynk doctor' to inspect CLI status."
      }];
    }
  }
}

module.exports = {
  FleetTreeDataProvider,
  formatFleetItems
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/fleetProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/providers/fleetProvider.js clients/vscode/test/suite/fleetProvider.test.js
git commit -m "feat(vscode): implement Fleet Health TreeDataProvider with progressive disclosure tooltips

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 5: Goals & Milestones (GOVERNS) TreeDataProvider

**Files:**
- Create: `clients/vscode/src/providers/goalsProvider.js`
- Test: `clients/vscode/test/suite/goalsProvider.test.js`

**Interfaces:**
- Consumes: `runSynlynk("goal", ["list"])` and event stream.
- Produces: `GoalsTreeDataProvider` implementing `vscode.TreeDataProvider`.

- [ ] **Step 1: Write the failing test for goalsProvider**

```javascript
// clients/vscode/test/suite/goalsProvider.test.js
const assert = require("assert");
const { GoalsTreeDataProvider, formatGoalItems } = require("../../src/providers/goalsProvider");

describe("Goals & Milestones (GOVERNS) TreeDataProvider", () => {
  it("formats goals and child stories into TreeItems with progress indicators", () => {
    const rawGoals = [
      {
        id: "goal-1",
        title: "v1.0.0 Developer Preview",
        target_date: "2026-10-31",
        status: "active",
        progress_pct: 75,
        stories: [
          { id: "story-1", title: "Hardening & GenericAPIAdapter", status: "completed" },
          { id: "story-2", title: "VS Code Extension Packaging", status: "in_progress" }
        ]
      }
    ];

    const roots = formatGoalItems(rawGoals);
    assert.strictEqual(roots.length, 1);
    assert.strictEqual(roots[0].label, "🎯 v1.0.0 Developer Preview (75%)");
    assert.strictEqual(roots[0].children.length, 2);
    assert.strictEqual(roots[0].children[0].label, "✓ Hardening & GenericAPIAdapter");
    assert.strictEqual(roots[0].children[1].label, "🚧 VS Code Extension Packaging");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/goalsProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/providers/goalsProvider'"

- [ ] **Step 3: Implement src/providers/goalsProvider.js**

```javascript
// clients/vscode/src/providers/goalsProvider.js
const { runSynlynk } = require("../cli");

function formatGoalItems(goalsData) {
  const goals = Array.isArray(goalsData) ? goalsData : (goalsData && goalsData.goals) || [];
  return goals.map((g) => {
    const stories = (g.stories || []).map((s) => {
      const icon = s.status === "completed" ? "✓" : s.status === "in_progress" ? "🚧" : "○";
      return {
        id: s.id,
        label: `${icon} ${s.title}`,
        tooltip: `**Story:** ${s.title}\nID: ${s.id}\nStatus: ${s.status}`,
        isStory: true
      };
    });

    return {
      id: g.id,
      label: `🎯 ${g.title} (${g.progress_pct || 0}%)`,
      tooltip: `**Project Goal (GOVERNS):** ${g.title}\nTarget Date: ${g.target_date || "Ongoing"}\nStatus: ${g.status}`,
      children: stories
    };
  });
}

class GoalsTreeDataProvider {
  constructor(workspaceRoot) {
    this.workspaceRoot = workspaceRoot;
    this._onDidChangeTreeData = null;
    this.cachedData = null;
  }

  refresh() {
    this.cachedData = null;
    if (this._onDidChangeTreeData) {
      this._onDidChangeTreeData.fire();
    }
  }

  async getChildren(element) {
    if (element) {
      return element.children || [];
    }
    try {
      if (!this.cachedData) {
        this.cachedData = await runSynlynk("goal", ["list"], { cwd: this.workspaceRoot });
      }
      return formatGoalItems(this.cachedData);
    } catch (err) {
      return [{
        id: "goals-empty",
        label: "No Goals Configured",
        tooltip: "Use 'synlynk goal add' or the Command Palette to establish a project milestone."
      }];
    }
  }
}

module.exports = {
  GoalsTreeDataProvider,
  formatGoalItems
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/goalsProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/providers/goalsProvider.js clients/vscode/test/suite/goalsProvider.test.js
git commit -m "feat(vscode): implement Project Goals & Milestones TreeDataProvider

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 6: Dispatched Jobs TreeDataProvider & Context Actions

**Files:**
- Create: `clients/vscode/src/providers/jobsProvider.js`
- Test: `clients/vscode/test/suite/jobsProvider.test.js`

**Interfaces:**
- Consumes: `runSynlynk("jobs", ...)` and event stream.
- Produces: `JobsTreeDataProvider` returning TreeItems with context values enabling `[Review Diff]`, `[Check Policy]`, and `[View Log]`.

- [ ] **Step 1: Write the failing test for jobsProvider**

```javascript
// clients/vscode/test/suite/jobsProvider.test.js
const assert = require("assert");
const { JobsTreeDataProvider, formatJobItems } = require("../../src/providers/jobsProvider");

describe("Dispatched Jobs TreeDataProvider", () => {
  it("formats jobs into TreeItems with verified status and inline action context", () => {
    const rawJobs = [
      {
        id: "djob-8f2a",
        task: "implement extension.js",
        status: "VERIFIED",
        author: "agy",
        verifier: "codex",
        worktree_path: "/worktrees/djob-8f2a",
        branch: "dispatch/agy/djob-8f2a"
      },
      {
        id: "djob-9b1c",
        task: "fix sqlite row lock",
        status: "RUNNING",
        author: "codex",
        verifier: null,
        elapsed_seconds: 35
      }
    ];

    const items = formatJobItems(rawJobs);
    assert.strictEqual(items.length, 2);

    // Complete job
    const job1 = items[0];
    assert.strictEqual(job1.contextValue, "job-complete");
    assert.ok(job1.label.includes("djob-8f2a"));
    assert.strictEqual(job1.worktreePath, "/worktrees/djob-8f2a");

    // In-flight job
    const job2 = items[1];
    assert.strictEqual(job2.contextValue, "job-running");
    assert.ok(job2.label.includes("RUNNING"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/jobsProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/providers/jobsProvider'"

- [ ] **Step 3: Implement src/providers/jobsProvider.js**

```javascript
// clients/vscode/src/providers/jobsProvider.js
const { runSynlynk } = require("../cli");

function formatJobItems(jobsData) {
  const jobs = Array.isArray(jobsData) ? jobsData : (jobsData && jobsData.jobs) || [];
  return jobs.map((j) => {
    let icon = "🟢";
    let contextValue = "job-complete";

    if (j.status === "RUNNING") {
      icon = "🟡";
      contextValue = "job-running";
    } else if (j.status === "FAILED") {
      icon = "🔴";
      contextValue = "job-failed";
    } else if (j.status === "CIRCUIT_BREAKER") {
      icon = "⚡";
      contextValue = "job-tripped";
    }

    const label = `${icon} ${j.id}: ${j.task}`;
    const tooltip = `**Job ID:** ${j.id}\n` +
      `**Task:** ${j.task}\n` +
      `**Status:** ${j.status}\n` +
      `**Author:** ${j.author || "Unknown"}\n` +
      `**Verifier:** ${j.verifier || "None"}\n` +
      `**Worktree:** ${j.worktree_path || "N/A"}\n\n` +
      `*Leased Git Worktree: Your open files and cursor position are never modified during execution.*`;

    return {
      id: j.id,
      label,
      tooltip,
      contextValue,
      jobId: j.id,
      worktreePath: j.worktree_path,
      branch: j.branch,
      status: j.status
    };
  });
}

class JobsTreeDataProvider {
  constructor(workspaceRoot) {
    this.workspaceRoot = workspaceRoot;
    this._onDidChangeTreeData = null;
    this.cachedData = null;
  }

  refresh() {
    this.cachedData = null;
    if (this._onDidChangeTreeData) {
      this._onDidChangeTreeData.fire();
    }
  }

  async getChildren(element) {
    if (element) return [];
    try {
      if (!this.cachedData) {
        this.cachedData = await runSynlynk("jobs", ["--limit", "15"], { cwd: this.workspaceRoot });
      }
      return formatJobItems(this.cachedData);
    } catch (err) {
      return [{
        id: "jobs-empty",
        label: "No Recent Dispatches",
        tooltip: "Press Cmd+Shift+P and run 'Synlynk: Dispatch Task' to start a job in a leased worktree."
      }];
    }
  }
}

module.exports = {
  JobsTreeDataProvider,
  formatJobItems
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/jobsProvider.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/providers/jobsProvider.js clients/vscode/test/suite/jobsProvider.test.js
git commit -m "feat(vscode): implement Dispatched Jobs TreeDataProvider with worktree review actions

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 7: Status Bar Controller

**Files:**
- Create: `clients/vscode/src/ui/statusBar.js`
- Test: `clients/vscode/test/suite/statusBar.test.js`

**Interfaces:**
- Produces: `StatusBarController` updating status text, icons, and click actions.

- [ ] **Step 1: Write the failing test for statusBar**

```javascript
// clients/vscode/test/suite/statusBar.test.js
const assert = require("assert");
const { formatStatusText } = require("../../src/ui/statusBar");

describe("Status Bar Controller", () => {
  it("formats idle state with spend metric", () => {
    const text = formatStatusText({ state: "idle", spend: 18.47 });
    assert.strictEqual(text, "$(circuit-board) Synlynk: Ready ($18.47)");
  });

  it("formats active running dispatch state", () => {
    const text = formatStatusText({
      state: "running",
      jobId: "djob-8f2a",
      harness: "Codex",
      elapsedSeconds: 32
    });
    assert.strictEqual(text, "$(sync~spin) Synlynk: [djob-8f2a] Codex running (32s)");
  });

  it("formats verification stage state", () => {
    const text = formatStatusText({
      state: "verifying",
      jobId: "djob-8f2a",
      harness: "Grok"
    });
    assert.strictEqual(text, "$(shield) Synlynk: [djob-8f2a] Grok verifying...");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/statusBar.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/ui/statusBar'"

- [ ] **Step 3: Implement src/ui/statusBar.js**

```javascript
// clients/vscode/src/ui/statusBar.js
function formatStatusText(data) {
  if (data.state === "running") {
    return `$(sync~spin) Synlynk: [${data.jobId}] ${data.harness} running (${data.elapsedSeconds || 0}s)`;
  }
  if (data.state === "verifying") {
    return `$(shield) Synlynk: [${data.jobId}] ${data.harness} verifying...`;
  }
  const spend = typeof data.spend === "number" ? `$${data.spend.toFixed(2)}` : "Ready";
  return `$(circuit-board) Synlynk: Ready (${spend})`;
}

class StatusBarController {
  constructor(vscodeStatusBarItem) {
    this.item = vscodeStatusBarItem;
  }

  update(data) {
    if (!this.item) return;
    this.item.text = formatStatusText(data);
    this.item.show();
  }

  dispose() {
    if (this.item) this.item.dispose();
  }
}

module.exports = {
  formatStatusText,
  StatusBarController
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/statusBar.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/ui/statusBar.js clients/vscode/test/suite/statusBar.test.js
git commit -m "feat(vscode): implement animated Status Bar controller

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 8: Commands — Goal-Linked Dispatch

**Files:**
- Create: `clients/vscode/src/commands/dispatch.js`
- Test: `clients/vscode/test/suite/dispatchCommand.test.js`

**Interfaces:**
- Consumes: `vscode.window.showInputBox`, `vscode.window.showQuickPick`, `runSynlynk("dispatch", ...)`.
- Produces: `executeDispatch(inputTask, selectedGoal, runner)` executing non-disruptive leased worktree dispatch.

- [ ] **Step 1: Write the failing test for dispatch command**

```javascript
// clients/vscode/test/suite/dispatchCommand.test.js
const assert = require("assert");
const { buildDispatchArgs } = require("../../src/commands/dispatch");

describe("Dispatch Command Logic", () => {
  it("builds CLI arguments correctly with goal association", () => {
    const args = buildDispatchArgs("Fix null pointer in auth.py", "goal-1", { forceHarness: "codex" });
    assert.deepStrictEqual(args, [
      "--task",
      "Fix null pointer in auth.py",
      "--goal-id",
      "goal-1",
      "--force-agent",
      "codex"
    ]);
  });

  it("supports ad-hoc dispatches without goal association", () => {
    const args = buildDispatchArgs("Inspect README typography", null);
    assert.deepStrictEqual(args, [
      "--task",
      "Inspect README typography"
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/dispatchCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/commands/dispatch'"

- [ ] **Step 3: Implement src/commands/dispatch.js**

```javascript
// clients/vscode/src/commands/dispatch.js
const { runSynlynk } = require("../cli");

function buildDispatchArgs(task, goalId, options = {}) {
  const args = ["--task", task];
  if (goalId) {
    args.push("--goal-id", goalId);
  }
  if (options.forceHarness) {
    args.push("--force-agent", options.forceHarness);
  }
  return args;
}

async function registerDispatchCommand(vscode, workspaceRoot) {
  return vscode.commands.registerCommand("synlynk.dispatch", async () => {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showErrorMessage("Synlynk dispatch is disabled in untrusted workspaces.");
      return;
    }

    const task = await vscode.window.showInputBox({
      title: "Synlynk: Dispatch Task",
      prompt: "Describe the task, bug fix, or feature to implement in an isolated worktree:",
      placeHolder: "e.g. Implement edge-case test suite for token parser"
    });

    if (!task) return;

    // Fetch active goals for association picker
    let goalChoices = [{ label: "⏩ Skip (Ad-hoc exploratory task)", id: null }];
    try {
      const goalsData = await runSynlynk("goal", ["list"], { cwd: workspaceRoot });
      const goals = Array.isArray(goalsData) ? goalsData : (goalsData && goalsData.goals) || [];
      const formatted = goals.map((g) => ({
        label: `🎯 ${g.title}`,
        description: `Target: ${g.target_date || "Ongoing"}`,
        id: g.id
      }));
      goalChoices = [...formatted, ...goalChoices];
    } catch (_) {}

    const selectedGoal = await vscode.window.showQuickPick(goalChoices, {
      title: "Link to Project Goal / Milestone (GOVERNS)",
      placeHolder: "Select a goal to bound this task"
    });

    const goalId = selectedGoal ? selectedGoal.id : null;
    const args = buildDispatchArgs(task, goalId);

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Synlynk: Dispatched to Leased Worktree",
        cancellable: false
      },
      async (progress) => {
        progress.report({ message: "Spawning background agent..." });
        try {
          const res = await runSynlynk("dispatch", args, { cwd: workspaceRoot });
          vscode.window.showInformationMessage(
            `Synlynk dispatch complete! Job: ${res.job_id || "djob"}. Review changes via sidebar.`
          );
        } catch (err) {
          vscode.window.showErrorMessage(`Dispatch failed: ${err.message}`);
        }
      }
    );
  });
}

module.exports = {
  buildDispatchArgs,
  registerDispatchCommand
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/dispatchCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/commands/dispatch.js clients/vscode/test/suite/dispatchCommand.test.js
git commit -m "feat(vscode): implement goal-linked dispatch command and QuickPick workflow

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 9: Commands — Native Worktree Diff Review & PR Policy Check

**Files:**
- Create: `clients/vscode/src/commands/diff.js`
- Create: `clients/vscode/src/commands/prCheck.js`
- Test: `clients/vscode/test/suite/diffCommand.test.js`

**Interfaces:**
- Consumes: `vscode.commands.executeCommand("vscode.diff", ...)`, `runSynlynk("pr", ["check"])`.
- Produces: `registerDiffCommand`, `registerPrCheckCommand`.

- [ ] **Step 1: Write the failing test for diff logic**

```javascript
// clients/vscode/test/suite/diffCommand.test.js
const assert = require("assert");
const { resolveDiffUris } = require("../../src/commands/diff");

describe("Worktree Diff Review Logic", () => {
  it("resolves active root and worktree path to URI representations", () => {
    const root = "/Users/dev/repo";
    const worktree = "/Users/dev/repo/worktrees/djob-8f2a";
    const file = "synlynk/cli.py";

    const uris = resolveDiffUris(root, worktree, file);
    assert.strictEqual(uris.basePath, "/Users/dev/repo/synlynk/cli.py");
    assert.strictEqual(uris.worktreePath, "/Users/dev/repo/worktrees/djob-8f2a/synlynk/cli.py");
    assert.strictEqual(uris.title, "cli.py (Active ↔ djob-8f2a)");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/diffCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/commands/diff'"

- [ ] **Step 3: Implement src/commands/diff.js and src/commands/prCheck.js**

```javascript
// clients/vscode/src/commands/diff.js
const path = require("path");

function resolveDiffUris(activeRoot, worktreePath, relativeFilePath) {
  const file = relativeFilePath || "";
  const basename = path.basename(file) || "Worktree Diff";
  const worktreeId = path.basename(worktreePath);

  return {
    basePath: path.join(activeRoot, file),
    worktreePath: path.join(worktreePath, file),
    title: `${basename} (Active ↔ ${worktreeId})`
  };
}

function registerDiffCommand(vscode, workspaceRoot) {
  return vscode.commands.registerCommand("synlynk.diffReview", async (jobItem) => {
    if (!jobItem || !jobItem.worktreePath) {
      vscode.window.showWarningMessage("No worktree path available for this job.");
      return;
    }

    const { basePath, worktreePath, title } = resolveDiffUris(
      workspaceRoot,
      jobItem.worktreePath,
      ""
    );

    const baseUri = vscode.Uri.file(basePath);
    const worktreeUri = vscode.Uri.file(worktreePath);

    await vscode.commands.executeCommand("vscode.diff", baseUri, worktreeUri, title);
  });
}

module.exports = {
  resolveDiffUris,
  registerDiffCommand
};
```

```javascript
// clients/vscode/src/commands/prCheck.js
const { runSynlynk } = require("../cli");

function registerPrCheckCommand(vscode, workspaceRoot) {
  return vscode.commands.registerCommand("synlynk.prCheck", async () => {
    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Synlynk: Running Policy Verification",
        cancellable: false
      },
      async () => {
        try {
          const res = await runSynlynk("pr", ["check"], { cwd: workspaceRoot });
          const passed = res.passed !== false;
          if (passed) {
            vscode.window.showInformationMessage("✓ Synlynk Policy Check Passed: Invariant 1 attested.");
          } else {
            vscode.window.showWarningMessage(`Policy Check Failed: ${res.reason || "Review policy blocked"}`);
          }
        } catch (err) {
          vscode.window.showErrorMessage(`PR Check Error: ${err.message}`);
        }
      }
    );
  });
}

module.exports = { registerPrCheckCommand };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/diffCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/commands/diff.js clients/vscode/src/commands/prCheck.js clients/vscode/test/suite/diffCommand.test.js
git commit -m "feat(vscode): implement native worktree diff review and policy verification commands

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 10: Commands — Doctor Diagnostics & Bootstrap Guidance

**Files:**
- Create: `clients/vscode/src/commands/doctor.js`
- Test: `clients/vscode/test/suite/doctorCommand.test.js`

**Interfaces:**
- Consumes: `runSynlynk("doctor", ...)`.
- Produces: `formatDoctorSummary(doctorOutput)`, `registerDoctorCommand`.

- [ ] **Step 1: Write the failing test for doctorCommand**

```javascript
// clients/vscode/test/suite/doctorCommand.test.js
const assert = require("assert");
const { formatDoctorSummary } = require("../../src/commands/doctor");

describe("Doctor Diagnostics Formatter", () => {
  it("formats check results into Markdown summary", () => {
    const rawDoctor = {
      checks: [
        { name: "python_runtime", passed: true, message: "Python 3.11 detected" },
        { name: "harness_claude", passed: true, message: "Claude Code CLI detected" },
        { name: "harness_codex", passed: true, message: "Codex CLI detected" },
        { name: "harness_grok", passed: false, message: "xAI API key not configured" }
      ]
    };

    const summary = formatDoctorSummary(rawDoctor);
    assert.ok(summary.includes("✓ python_runtime: Python 3.11 detected"));
    assert.ok(summary.includes("✗ harness_grok: xAI API key not configured"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/doctorCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../src/commands/doctor'"

- [ ] **Step 3: Implement src/commands/doctor.js**

```javascript
// clients/vscode/src/commands/doctor.js
const { runSynlynk } = require("../cli");

function formatDoctorSummary(doctorData) {
  const checks = (doctorData && doctorData.checks) || [];
  const lines = ["# Synlynk Doctor Diagnostics\n"];
  for (const c of checks) {
    const sym = c.passed ? "✓" : "✗";
    lines.push(`- ${sym} ${c.name}: ${c.message}`);
  }
  return lines.join("\n");
}

function registerDoctorCommand(vscode, workspaceRoot) {
  let outputChannel = null;

  return vscode.commands.registerCommand("synlynk.doctor", async () => {
    if (!outputChannel) {
      outputChannel = vscode.window.createOutputChannel("Synlynk Doctor");
    }
    outputChannel.show();
    outputChannel.appendLine("Running environment diagnostics...");

    try {
      const data = await runSynlynk("doctor", [], { cwd: workspaceRoot });
      const summary = formatDoctorSummary(data);
      outputChannel.appendLine(summary);
    } catch (err) {
      outputChannel.appendLine(`Doctor failed: ${err.message}`);
      if (err.type === "CLI_MISSING") {
        const choice = await vscode.window.showErrorMessage(
          "Synlynk CLI not found. Install via pipx?",
          "Install via pipx",
          "Dismiss"
        );
        if (choice === "Install via pipx") {
          const terminal = vscode.window.createTerminal("Synlynk Install");
          terminal.show();
          terminal.sendText("pipx install synlynk");
        }
      }
    }
  });
}

module.exports = {
  formatDoctorSummary,
  registerDoctorCommand
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/doctorCommand.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/src/commands/doctor.js clients/vscode/test/suite/doctorCommand.test.js
git commit -m "feat(vscode): implement Doctor diagnostics command and bootstrap guidance

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 11: Main Extension Activation, Workspace Trust & Walkthrough Wiring

**Files:**
- Create: `clients/vscode/extension.js`
- Test: `clients/vscode/test/suite/extension.test.js`

**Interfaces:**
- Produces: `activate(context)` and `deactivate()`.

- [ ] **Step 1: Write the failing test for extension activation**

```javascript
// clients/vscode/test/suite/extension.test.js
const assert = require("assert");
const { activate, deactivate } = require("../../extension");

describe("Extension Activation & Lifecycle", () => {
  it("exports activate and deactivate functions", () => {
    assert.strictEqual(typeof activate, "function");
    assert.strictEqual(typeof deactivate, "function");
  });

  it("handles untrusted workspace safely without throwing", () => {
    const mockContext = {
      subscriptions: [],
      workspaceState: { get: () => null, update: () => {} }
    };
    const mockVscode = {
      workspace: { isTrusted: false, workspaceFolders: [{ uri: { fsPath: "/tmp" } }] },
      window: {
        createStatusBarItem: () => ({ show: () => {}, dispose: () => {} }),
        showWarningMessage: () => {}
      },
      commands: { registerCommand: () => ({ dispose: () => {} }) }
    };

    assert.doesNotThrow(() => {
      activate(mockContext, mockVscode);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/extension.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: FAIL with "Cannot find module '../../extension'"

- [ ] **Step 3: Implement clients/vscode/extension.js**

```javascript
// clients/vscode/extension.js
const { FleetTreeDataProvider } = require("./src/providers/fleetProvider");
const { GoalsTreeDataProvider } = require("./src/providers/goalsProvider");
const { JobsTreeDataProvider } = require("./src/providers/jobsProvider");
const { StatusBarController } = require("./src/ui/statusBar");
const { watchEvents } = require("./src/eventWatcher");
const { registerDispatchCommand } = require("./src/commands/dispatch");
const { registerDiffCommand } = require("./src/commands/diff");
const { registerPrCheckCommand } = require("./src/commands/prCheck");
const { registerDoctorCommand } = require("./src/commands/doctor");

let eventWatcher = null;

function activate(context, injectedVscode) {
  const vscode = injectedVscode || require("vscode");
  const folders = vscode.workspace.workspaceFolders;
  const workspaceRoot = folders && folders.length > 0 ? folders[0].uri.fsPath : process.cwd();

  // 1. Status Bar Setup
  const rawStatusBar = vscode.window.createStatusBarItem(1, 100);
  const statusBar = new StatusBarController(rawStatusBar);
  statusBar.update({ state: "idle", spend: 0 });
  context.subscriptions.push(rawStatusBar);

  // 2. Workspace Trust Handling
  if (!vscode.workspace.isTrusted) {
    vscode.window.showWarningMessage(
      "Synlynk: Running in Untrusted Workspace. Execution and worktree dispatches are disabled."
    );
    return;
  }

  // 3. TreeView Data Providers
  const fleetProvider = new FleetTreeDataProvider(workspaceRoot);
  const goalsProvider = new GoalsTreeDataProvider(workspaceRoot);
  const jobsProvider = new JobsTreeDataProvider(workspaceRoot);

  if (vscode.window.registerTreeDataProvider) {
    context.subscriptions.push(
      vscode.window.registerTreeDataProvider("synlynk-fleet", fleetProvider),
      vscode.window.registerTreeDataProvider("synlynk-goals", goalsProvider),
      vscode.window.registerTreeDataProvider("synlynk-jobs", jobsProvider)
    );
  }

  // 4. Reactive Event Tailing
  eventWatcher = watchEvents(workspaceRoot, (event) => {
    fleetProvider.refresh();
    goalsProvider.refresh();
    jobsProvider.refresh();

    if (event.event === "job_started") {
      statusBar.update({
        state: "running",
        jobId: event.job_id || "djob",
        harness: event.harness || "Agent",
        elapsedSeconds: 0
      });
    } else if (event.event === "job_finished") {
      statusBar.update({ state: "idle" });
    }
  });

  if (eventWatcher && eventWatcher.dispose) {
    context.subscriptions.push({ dispose: () => eventWatcher.dispose() });
  }

  // 5. Register Commands
  if (vscode.commands && vscode.commands.registerCommand) {
    context.subscriptions.push(
      registerDispatchCommand(vscode, workspaceRoot),
      registerDiffCommand(vscode, workspaceRoot),
      registerPrCheckCommand(vscode, workspaceRoot),
      registerDoctorCommand(vscode, workspaceRoot),
      vscode.commands.registerCommand("synlynk.refreshAll", () => {
        fleetProvider.refresh();
        goalsProvider.refresh();
        jobsProvider.refresh();
      })
    );
  }
}

function deactivate() {
  if (eventWatcher) {
    eventWatcher.dispose();
    eventWatcher = null;
  }
}

module.exports = {
  activate,
  deactivate
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node -e "const Mocha = require('mocha'); const mocha = new Mocha(); mocha.addFile('./clients/vscode/test/suite/extension.test.js'); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit**

```bash
git add clients/vscode/extension.js clients/vscode/test/suite/extension.test.js
git commit -m "feat(vscode): implement main extension activation, Workspace Trust handling and event wiring

Co-Authored-By: AGY <noreply@antigravity.dev>"
```

---

### Task 12: Automated VSIX Packaging & CI Verification Workflow

**Files:**
- Create: `.github/workflows/vscode-package.yml`
- Create: `clients/vscode/README.md`
- Test: Full mocha test suite execution + dry-run package verification

**Interfaces:**
- Produces: GitHub Actions CI workflow packaging `synlynk-vscode-0.1.0.vsix` with zero dependencies and bundle size check (< 2MB).

- [ ] **Step 1: Write test runner and marketplace README**

```markdown
<!-- clients/vscode/README.md -->
# Synlynk for Visual Studio Code

Autonomous Multi-Agent Engineering inside VS Code, Cursor, and Windsurf.

## Key Capabilities
- **Non-Disruptive Leased Worktrees:** Dispatches run in isolated git worktrees. Your open file buffers and editor state remain 100% untouched.
- **Adversarial Non-Author Review:** One model family writes (e.g. Codex), while an independent model family audits (e.g. Grok or Claude).
- **Invariant 1 Verification:** Requires a real git diff, passing test oracle, and AST change before any task is considered complete.
- **Goal-Linked Dispatch (GOVERNS):** Connect dispatches directly to project milestones and tracked spend.

## Quickstart
1. Install Synlynk CLI: `pipx install synlynk`
2. Open the Synlynk sidebar from the Activity Bar.
3. Run `Synlynk: Run Doctor Diagnostics` to verify installed agents.
4. Press `Cmd+Shift+P` -> `Synlynk: Dispatch Task` to run your first worktree task.
```

- [ ] **Step 2: Create .github/workflows/vscode-package.yml**

```yaml
# .github/workflows/vscode-package.yml
name: VS Code Extension Package & Verification

on:
  push:
    branches: [main]
    paths:
      - "clients/vscode/**"
      - ".github/workflows/vscode-package.yml"
  pull_request:
    paths:
      - "clients/vscode/**"
      - ".github/workflows/vscode-package.yml"

jobs:
  package:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: clients/vscode

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js 18
        uses: actions/setup-node@v4
        with:
          node-version: 18

      - name: Install Dev Dependencies
        run: npm ci || npm install

      - name: Run Test Suite
        run: |
          node -e "
            const Mocha = require('mocha');
            const fs = require('fs');
            const path = require('path');
            const mocha = new Mocha();
            const testDir = path.join(__dirname, 'test/suite');
            fs.readdirSync(testDir).filter(f => f.endsWith('.test.js')).forEach(f => {
              mocha.addFile(path.join(testDir, f));
            });
            mocha.run(failures => process.exitCode = failures ? 1 : 0);
          "

      - name: Verify Zero Production Dependencies
        run: |
          DEPS=$(node -e "const p = require('./package.json'); console.log(Object.keys(p.dependencies || {}).length)")
          if [ "$DEPS" -ne 0 ]; then
            echo "ERROR: Production dependencies must be 0, found $DEPS"
            exit 1
          fi

      - name: Package VSIX Bundle
        run: npx @vscode/vsce package --no-dependencies

      - name: Verify Package Size (< 2MB)
        run: |
          SIZE=$(stat -c%s synlynk-vscode-*.vsix 2>/dev/null || stat -f%z synlynk-vscode-*.vsix)
          echo "Package size: $SIZE bytes"
          if [ "$SIZE" -gt 2097152 ]; then
            echo "ERROR: Package size exceeds 2MB limit"
            exit 1
          fi

      - name: Upload VSIX Artifact
        uses: actions/upload-artifact@v4
        with:
          name: synlynk-vscode-vsix
          path: clients/vscode/*.vsix
```

- [ ] **Step 3: Run full local test suite across all 6 test files**

Run: `node -e "const Mocha = require('mocha'); const fs = require('fs'); const path = require('path'); const mocha = new Mocha(); const testDir = './clients/vscode/test/suite'; fs.readdirSync(testDir).filter(f => f.endsWith('.test.js')).forEach(f => mocha.addFile(path.join(testDir, f))); mocha.run(failures => process.exitCode = failures ? 1 : 0);"`
Expected: PASS with all tests passing across scaffolding, cli, eventWatcher, fleetProvider, goalsProvider, jobsProvider, statusBar, dispatch, diff, doctor, extension.

- [ ] **Step 4: Commit and tag packaging workflow**

```bash
git add .github/workflows/vscode-package.yml clients/vscode/README.md
git commit -m "ci(vscode): add automated VSIX packaging and zero-dependency verification workflow

Co-Authored-By: AGY <noreply@antigravity.dev>"
```
