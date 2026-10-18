"use strict";

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

function formatGoalChoices(goalsData) {
  const goals = Array.isArray(goalsData) ? goalsData : goalsData?.goals || [];
  const skipChoice = { label: "⏩ Skip (Ad-hoc exploratory task)", id: null };

  return [
    ...goals.map((goal) => ({
      label: `🎯 ${goal.title}`,
      description: `Target: ${goal.target_date || "Ongoing"}`,
      id: goal.id,
    })),
    skipChoice,
  ];
}

function registerDispatchCommand(vscode, workspaceRoot, options = {}) {
  const runner = options.runner || runSynlynk;

  return vscode.commands.registerCommand("synlynk.dispatch", async () => {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showErrorMessage("Synlynk dispatch is disabled in untrusted workspaces.");
      return;
    }

    const task = await vscode.window.showInputBox({
      title: "Synlynk: Dispatch Task",
      prompt: "Describe the task, bug fix, or feature to implement in an isolated worktree:",
      placeHolder: "e.g. Implement edge-case test suite for token parser",
    });

    if (!task) {
      return;
    }

    let goalChoices = formatGoalChoices([]);
    try {
      const goalsData = await runner("goal", ["list"], { cwd: workspaceRoot });
      goalChoices = formatGoalChoices(goalsData);
    } catch (_) {
      // A dispatch can still be useful when the local goal registry is unavailable.
    }

    const selectedGoal = await vscode.window.showQuickPick(goalChoices, {
      title: "Link to Project Goal / Milestone (GOVERNS)",
      placeHolder: "Select a goal to bound this task",
    });
    const args = buildDispatchArgs(task, selectedGoal ? selectedGoal.id : null, options);

    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Synlynk: Dispatched to Leased Worktree",
        cancellable: false,
      },
      async (progress) => {
        progress.report({ message: "Spawning background agent..." });
        try {
          const result = await runner("dispatch", args, { cwd: workspaceRoot });
          vscode.window.showInformationMessage(
            `Synlynk dispatch complete! Job: ${result.job_id || "djob"}. Review changes via sidebar.`,
          );
          return result;
        } catch (error) {
          vscode.window.showErrorMessage(`Dispatch failed: ${error.message}`);
          return undefined;
        }
      },
    );
  });
}

module.exports = {
  buildDispatchArgs,
  registerDispatchCommand,
};
