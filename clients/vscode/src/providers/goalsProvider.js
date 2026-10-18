"use strict";

const { runSynlynk } = require("../cli");

function formatGoalItems(goalsData) {
  const goals = Array.isArray(goalsData) ? goalsData : goalsData?.goals || [];

  return goals.map((goal) => ({
    id: goal.id,
    label: `🎯 ${goal.title} (${goal.progress_pct || 0}%)`,
    tooltip: `Project Goal (GOVERNS): ${goal.title}\n` +
      `Target Date: ${goal.target_date || "Ongoing"}\n` +
      `Status: ${goal.status}`,
    children: (goal.stories || []).map((story) => {
      const icon = story.status === "completed"
        ? "✓"
        : story.status === "in_progress"
          ? "🚧"
          : "○";

      return {
        id: story.id,
        label: `${icon} ${story.title}`,
        tooltip: `Story: ${story.title}\nID: ${story.id}\nStatus: ${story.status}`,
        isStory: true,
      };
    }),
  }));
}

class GoalsTreeDataProvider {
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
      return element.children || [];
    }

    try {
      if (!this.cachedData) {
        this.cachedData = await this.runner("goal", ["list"], {
          cwd: this.workspaceRoot,
        });
      }
      return formatGoalItems(this.cachedData);
    } catch (_) {
      return [{
        id: "goals-empty",
        label: "No Goals Configured",
        tooltip: "Use synlynk goal add or the Command Palette to establish a project milestone",
      }];
    }
  }
}

module.exports = { GoalsTreeDataProvider, formatGoalItems };
