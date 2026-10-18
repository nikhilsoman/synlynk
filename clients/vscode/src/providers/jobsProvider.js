"use strict";

const { runSynlynk } = require("../cli");

function formatJobItems(jobsData) {
  const jobs = Array.isArray(jobsData) ? jobsData : jobsData?.jobs || [];

  return jobs.map((job) => {
    let icon = "🟢";
    let contextValue = "job-complete";

    if (job.status === "RUNNING") {
      icon = "🟡";
      contextValue = "job-running";
    } else if (job.status === "FAILED") {
      icon = "🔴";
      contextValue = "job-failed";
    } else if (job.status === "CIRCUIT_BREAKER") {
      icon = "⚡";
      contextValue = "job-tripped";
    }

    return {
      id: job.id,
      jobId: job.id,
      label: `${icon} ${job.id}: ${job.task}`,
      tooltip: `**Job ID:** ${job.id}\n` +
        `**Task:** ${job.task}\n` +
        `**Status:** ${job.status}\n` +
        `**Author:** ${job.author || "Unknown"}\n` +
        `**Verifier:** ${job.verifier || "None"}\n` +
        `**Worktree:** ${job.worktree_path || "N/A"}\n\n` +
        "*Leased Git Worktree: Your open files and cursor position are never modified during execution.*",
      contextValue,
      worktreePath: job.worktree_path,
      branch: job.branch,
      status: job.status,
    };
  });
}

class JobsTreeDataProvider {
  constructor(workspaceRoot, options = {}) {
    this.workspaceRoot = workspaceRoot;
    this.runner = options.runner || runSynlynk;
    this._onDidChangeTreeData = null;
    this.cachedData = null;
  }

  refresh() {
    this.cachedData = null;
    if (this._onDidChangeTreeData) {
      this._onDidChangeTreeData.fire();
    }
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren(element) {
    if (element) {
      return [];
    }

    try {
      if (!this.cachedData) {
        this.cachedData = await this.runner("jobs", ["--limit", "15"], {
          cwd: this.workspaceRoot,
        });
      }
      return formatJobItems(this.cachedData);
    } catch (_) {
      return [{
        id: "jobs-empty",
        label: "No Recent Dispatches",
        tooltip: "Press Cmd+Shift+P and run 'Synlynk: Dispatch Task' to start a job in a leased worktree.",
      }];
    }
  }
}

module.exports = { JobsTreeDataProvider, formatJobItems };
