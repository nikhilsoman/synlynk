"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  buildDispatchArgs,
  registerDispatchCommand,
} = require("../../src/commands/dispatch");

function createVscode({ isTrusted = true, input, quickPick } = {}) {
  const state = {
    command: null,
    errors: [],
    information: [],
    progressOptions: null,
    progressReports: [],
  };

  return {
    state,
    workspace: { isTrusted },
    ProgressLocation: { Notification: "notification" },
    commands: {
      registerCommand: (name, handler) => {
        state.command = handler;
        return { dispose() {} };
      },
    },
    window: {
      showInputBox: async () => input,
      showQuickPick: async () => quickPick,
      showErrorMessage: (message) => state.errors.push(message),
      showInformationMessage: (message) => state.information.push(message),
      withProgress: async (options, callback) => {
        state.progressOptions = options;
        return callback({ report: (value) => state.progressReports.push(value) });
      },
    },
  };
}

describe("Goal-linked dispatch command", () => {
  it("builds CLI arguments with an associated goal and selected harness", () => {
    assert.deepEqual(
      buildDispatchArgs("Fix null pointer in auth.py", "goal-1", { forceHarness: "codex" }),
      ["--task", "Fix null pointer in auth.py", "--goal-id", "goal-1", "--force-agent", "codex"],
    );
  });

  it("supports ad-hoc dispatches without a goal association", () => {
    assert.deepEqual(buildDispatchArgs("Inspect README typography", null), [
      "--task",
      "Inspect README typography",
    ]);
  });

  it("blocks dispatch before prompting in untrusted workspaces", async () => {
    const vscode = createVscode({ isTrusted: false });
    const runnerCalls = [];
    registerDispatchCommand(vscode, "/workspace", {
      runner: async (...args) => runnerCalls.push(args),
    });

    await vscode.state.command();

    assert.deepEqual(runnerCalls, []);
    assert.deepEqual(vscode.state.errors, [
      "Synlynk dispatch is disabled in untrusted workspaces.",
    ]);
  });

  it("lists goals, dispatches the selection in progress, and reports the job", async () => {
    const vscode = createVscode({
      input: "Implement the command",
      quickPick: { id: "goal-1", label: "Goal one" },
    });
    const runnerCalls = [];
    registerDispatchCommand(vscode, "/workspace", {
      runner: async (...args) => {
        runnerCalls.push(args);
        if (args[0] === "goal") {
          return { goals: [{ id: "goal-1", title: "Goal one", target_date: "2026-10-31" }] };
        }
        return { job_id: "djob-123" };
      },
    });

    await vscode.state.command();

    assert.deepEqual(runnerCalls, [
      ["goal", ["list"], { cwd: "/workspace" }],
      ["dispatch", ["--task", "Implement the command", "--goal-id", "goal-1"], { cwd: "/workspace" }],
    ]);
    assert.equal(vscode.state.progressOptions.location, "notification");
    assert.deepEqual(vscode.state.progressReports, [{ message: "Spawning background agent..." }]);
    assert.deepEqual(vscode.state.information, [
      "Synlynk dispatch complete! Job: djob-123. Review changes via sidebar.",
    ]);
  });
});
