"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { activate, deactivate } = require("../../extension");

function createMockVscode({ isTrusted }) {
  const registeredCommands = [];
  const registeredProviders = [];
  const warnings = [];
  const statusBar = {
    showCalled: false,
    dispose() {},
    show() {
      this.showCalled = true;
    },
  };

  return {
    registeredCommands,
    registeredProviders,
    warnings,
    statusBar,
    workspace: {
      isTrusted,
      workspaceFolders: [{ uri: { fsPath: "/tmp/synlynk-vscode-test" } }],
    },
    window: {
      createStatusBarItem: () => statusBar,
      showWarningMessage: (message) => warnings.push(message),
      registerTreeDataProvider: (id, provider) => {
        registeredProviders.push({ id, provider });
        return { dispose() {} };
      },
      showErrorMessage() {},
      showInformationMessage() {},
      showInputBox: async () => undefined,
      showQuickPick: async () => undefined,
      withProgress: async (_, task) => task({ report() {} }),
      createOutputChannel: () => ({ appendLine() {}, show() {} }),
    },
    commands: {
      registerCommand: (id, callback) => {
        registeredCommands.push({ id, callback });
        return { dispose() {} };
      },
      executeCommand() {},
    },
    ProgressLocation: { Notification: 15 },
    Uri: { file: (filePath) => ({ fsPath: filePath }) },
  };
}

test("exports activate and deactivate functions", () => {
  assert.equal(typeof activate, "function");
  assert.equal(typeof deactivate, "function");
});

test("warns and stops setup for an untrusted workspace", () => {
  const context = { subscriptions: [] };
  const vscode = createMockVscode({ isTrusted: false });

  assert.doesNotThrow(() => activate(context, vscode));
  assert.equal(vscode.warnings.length, 1);
  assert.equal(vscode.registeredProviders.length, 0);
  assert.equal(vscode.registeredCommands.length, 0);
  assert.equal(context.subscriptions.length, 1);
  assert.equal(vscode.statusBar.showCalled, true);
});

test("wires providers, event watching, and extension commands for a trusted workspace", () => {
  const context = { subscriptions: [] };
  const vscode = createMockVscode({ isTrusted: true });

  activate(context, vscode);

  assert.deepEqual(
    vscode.registeredProviders.map(({ id }) => id),
    ["synlynk-fleet", "synlynk-goals", "synlynk-jobs"],
  );
  assert.deepEqual(
    vscode.registeredCommands.map(({ id }) => id),
    [
      "synlynk.dispatch",
      "synlynk.diffReview",
      "synlynk.prCheck",
      "synlynk.doctor",
      "synlynk.refreshAll",
    ],
  );
  assert.equal(context.subscriptions.length, 10);

  deactivate();
});
