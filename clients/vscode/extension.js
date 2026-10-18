"use strict";

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

function getVscode(injectedVscode) {
  // Keep the runtime dependency lazy so the Node test suite does not need VS Code.
  return injectedVscode || require("vscode");
}

function getWorkspaceRoot(vscode) {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length > 0 ? folders[0].uri.fsPath : process.cwd();
}

function activate(context, injectedVscode) {
  const vscode = getVscode(injectedVscode);
  const workspaceRoot = getWorkspaceRoot(vscode);
  const rawStatusBar = vscode.window.createStatusBarItem(1, 100);
  const statusBar = new StatusBarController(rawStatusBar);

  statusBar.update({ state: "idle", spend: 0 });
  context.subscriptions.push(rawStatusBar);

  if (!vscode.workspace.isTrusted) {
    vscode.window.showWarningMessage(
      "Synlynk: Running in Untrusted Workspace. Execution and worktree dispatches are disabled.",
    );
    return;
  }

  const fleetProvider = new FleetTreeDataProvider(workspaceRoot);
  const goalsProvider = new GoalsTreeDataProvider(workspaceRoot);
  const jobsProvider = new JobsTreeDataProvider(workspaceRoot);
  const refreshAll = () => {
    fleetProvider.refresh();
    goalsProvider.refresh();
    jobsProvider.refresh();
  };

  if (typeof vscode.window.registerTreeDataProvider === "function") {
    context.subscriptions.push(
      vscode.window.registerTreeDataProvider("synlynk-fleet", fleetProvider),
      vscode.window.registerTreeDataProvider("synlynk-goals", goalsProvider),
      vscode.window.registerTreeDataProvider("synlynk-jobs", jobsProvider),
    );
  }

  eventWatcher = watchEvents(workspaceRoot, (event) => {
    refreshAll();
    if (event.event === "job_started") {
      statusBar.update({
        state: "running",
        jobId: event.job_id || "djob",
        harness: event.harness || "Agent",
        elapsedSeconds: 0,
      });
    } else if (event.event === "job_finished") {
      statusBar.update({ state: "idle" });
    }
  });

  context.subscriptions.push({
    dispose: () => {
      if (eventWatcher) {
        eventWatcher.dispose();
        eventWatcher = null;
      }
    },
  });

  if (vscode.commands && typeof vscode.commands.registerCommand === "function") {
    context.subscriptions.push(
      registerDispatchCommand(vscode, workspaceRoot),
      registerDiffCommand(vscode, workspaceRoot),
      registerPrCheckCommand(vscode, workspaceRoot),
      registerDoctorCommand(vscode, workspaceRoot),
      vscode.commands.registerCommand("synlynk.refreshAll", refreshAll),
    );
  }
}

function deactivate() {
  if (eventWatcher) {
    eventWatcher.dispose();
    eventWatcher = null;
  }
}

module.exports = { activate, deactivate };
