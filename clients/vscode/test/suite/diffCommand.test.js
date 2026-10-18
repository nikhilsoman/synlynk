"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  resolveDiffUris,
  registerDiffCommand,
} = require("../../src/commands/diff");
const { registerPrCheckCommand } = require("../../src/commands/prCheck");

function createVscode() {
  const state = {
    commandHandlers: new Map(),
    commandCalls: [],
    information: [],
    warnings: [],
    errors: [],
    progress: [],
  };

  return {
    state,
    ProgressLocation: { Notification: "notification" },
    Uri: { file: (fsPath) => ({ fsPath }) },
    commands: {
      registerCommand(name, handler) {
        state.commandHandlers.set(name, handler);
        return { dispose() {} };
      },
      async executeCommand(...args) {
        state.commandCalls.push(args);
        return "diff-opened";
      },
    },
    window: {
      showInformationMessage: (message) => state.information.push(message),
      showWarningMessage: (message) => state.warnings.push(message),
      showErrorMessage: (message) => state.errors.push(message),
      withProgress: async (options, callback) => {
        state.progress.push(options);
        return callback();
      },
    },
  };
}

describe("Worktree diff and policy commands", () => {
  it("resolves active-root and worktree paths for a relative file", () => {
    assert.deepEqual(
      resolveDiffUris("/Users/dev/repo", "/Users/dev/repo/worktrees/djob-8f2a", "synlynk/cli.py"),
      {
        basePath: "/Users/dev/repo/synlynk/cli.py",
        worktreePath: "/Users/dev/repo/worktrees/djob-8f2a/synlynk/cli.py",
        title: "cli.py (Active ↔ djob-8f2a)",
      },
    );
  });

  it("registers a diff command that opens VS Code's native side-by-side diff", async () => {
    const vscode = createVscode();
    registerDiffCommand(vscode, "/repo");

    const result = await vscode.state.commandHandlers.get("synlynk.diffReview")({
      worktreePath: "/repo/worktrees/djob-1",
      relativeFilePath: "src/main.js",
    });

    assert.equal(result, "diff-opened");
    assert.deepEqual(vscode.state.commandCalls, [[
      "vscode.diff",
      { fsPath: "/repo/src/main.js" },
      { fsPath: "/repo/worktrees/djob-1/src/main.js" },
      "main.js (Active ↔ djob-1)",
    ]]);
  });

  it("warns instead of attempting a diff when a job has no worktree", async () => {
    const vscode = createVscode();
    registerDiffCommand(vscode, "/repo");

    await vscode.state.commandHandlers.get("synlynk.diffReview")();

    assert.deepEqual(vscode.state.warnings, ["No worktree path available for this job."]);
    assert.deepEqual(vscode.state.commandCalls, []);
  });

  it("runs the policy check with the injected runner and reports success", async () => {
    const vscode = createVscode();
    const calls = [];
    registerPrCheckCommand(vscode, "/repo", {
      runner: async (...args) => {
        calls.push(args);
        return { passed: true };
      },
    });

    await vscode.state.commandHandlers.get("synlynk.prCheck")();

    assert.deepEqual(calls, [["pr", ["check"], { cwd: "/repo" }]]);
    assert.deepEqual(vscode.state.information, [
      "✓ Synlynk Policy Check Passed: Invariant 1 attested.",
    ]);
    assert.equal(vscode.state.progress[0].location, "notification");
  });

  it("reports failed and errored policy checks without throwing", async () => {
    const failedVscode = createVscode();
    registerPrCheckCommand(failedVscode, "/repo", {
      runner: async () => ({ passed: false, reason: "Approval missing" }),
    });
    await failedVscode.state.commandHandlers.get("synlynk.prCheck")();
    assert.deepEqual(failedVscode.state.warnings, ["Policy Check Failed: Approval missing"]);

    const errorVscode = createVscode();
    registerPrCheckCommand(errorVscode, "/repo", {
      runner: async () => { throw new Error("CLI unavailable"); },
    });
    await errorVscode.state.commandHandlers.get("synlynk.prCheck")();
    assert.deepEqual(errorVscode.state.errors, ["PR Check Error: CLI unavailable"]);
  });
});
