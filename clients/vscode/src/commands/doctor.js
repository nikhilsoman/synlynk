"use strict";

const { runSynlynk } = require("../cli");

function formatDoctorSummary(doctorData) {
  const checks = Array.isArray(doctorData?.checks) ? doctorData.checks : [];
  const lines = ["# Synlynk Doctor Diagnostics\n"];

  for (const check of checks) {
    const symbol = check.passed ? "✓" : "✗";
    lines.push(`- ${symbol} ${check.name}: ${check.message}`);
  }

  return lines.join("\n");
}

function registerDoctorCommand(vscode, workspaceRoot, options = {}) {
  const runner = options.runner || runSynlynk;
  let outputChannel = null;

  return vscode.commands.registerCommand("synlynk.doctor", async () => {
    if (!outputChannel) {
      outputChannel = vscode.window.createOutputChannel("Synlynk Doctor");
    }

    outputChannel.show();
    outputChannel.appendLine("Running environment diagnostics...");

    try {
      const doctorData = await runner("doctor", [], { cwd: workspaceRoot });
      outputChannel.appendLine(formatDoctorSummary(doctorData));
      return doctorData;
    } catch (error) {
      outputChannel.appendLine(`Doctor failed: ${error.message}`);

      if (error.type === "CLI_MISSING") {
        const choice = await vscode.window.showErrorMessage(
          "Synlynk CLI not found. Install via pipx?",
          "Install via pipx",
          "Dismiss",
        );

        if (choice === "Install via pipx") {
          const terminal = vscode.window.createTerminal("Synlynk Install");
          terminal.show();
          terminal.sendText("pipx install synlynk");
        }
      }

      return undefined;
    }
  });
}

module.exports = {
  formatDoctorSummary,
  registerDoctorCommand,
};
