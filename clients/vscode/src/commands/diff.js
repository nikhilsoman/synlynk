"use strict";

const path = require("node:path");

function resolveDiffUris(activeRoot, worktreePath, relativeFilePath) {
  const file = relativeFilePath || "";
  const basename = path.basename(file) || "Worktree Diff";
  const worktreeId = path.basename(worktreePath);

  return {
    basePath: path.join(activeRoot, file),
    worktreePath: path.join(worktreePath, file),
    title: `${basename} (Active ↔ ${worktreeId})`,
  };
}

function registerDiffCommand(vscode, workspaceRoot) {
  return vscode.commands.registerCommand("synlynk.diffReview", async (jobItem) => {
    if (!jobItem || !jobItem.worktreePath) {
      vscode.window.showWarningMessage("No worktree path available for this job.");
      return undefined;
    }

    const { basePath, worktreePath, title } = resolveDiffUris(
      workspaceRoot,
      jobItem.worktreePath,
      jobItem.relativeFilePath,
    );

    return vscode.commands.executeCommand(
      "vscode.diff",
      vscode.Uri.file(basePath),
      vscode.Uri.file(worktreePath),
      title,
    );
  });
}

module.exports = {
  resolveDiffUris,
  registerDiffCommand,
};
