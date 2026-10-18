"use strict";

const { runSynlynk } = require("../cli");

function registerPrCheckCommand(vscode, workspaceRoot, options = {}) {
  const runner = options.runner || runSynlynk;

  return vscode.commands.registerCommand("synlynk.prCheck", () =>
    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Synlynk: Running Policy Verification",
        cancellable: false,
      },
      async () => {
        try {
          const result = await runner("pr", ["check"], { cwd: workspaceRoot });
          if (result.passed !== false) {
            vscode.window.showInformationMessage(
              "✓ Synlynk Policy Check Passed: Invariant 1 attested.",
            );
          } else {
            vscode.window.showWarningMessage(
              `Policy Check Failed: ${result.reason || "Review policy blocked"}`,
            );
          }
          return result;
        } catch (error) {
          vscode.window.showErrorMessage(`PR Check Error: ${error.message}`);
          return undefined;
        }
      },
    ),
  );
}

module.exports = { registerPrCheckCommand };
