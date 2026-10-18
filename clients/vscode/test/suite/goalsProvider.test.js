"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  GoalsTreeDataProvider,
  formatGoalItems,
} = require("../../src/providers/goalsProvider");

const goals = [{
  id: "goal-1",
  title: "v1.0.0 Developer Preview",
  target_date: "2026-10-31",
  status: "active",
  progress_pct: 75,
  stories: [
    { id: "story-1", title: "Hardening", status: "completed" },
    { id: "story-2", title: "Extension Packaging", status: "in_progress" },
    { id: "story-3", title: "Release Notes", status: "planned" },
  ],
}];

describe("Goals & Milestones (GOVERNS) TreeDataProvider", () => {
  it("formats root goals, progress, child stories, and status icons", () => {
    const roots = formatGoalItems({ goals });

    assert.equal(roots.length, 1);
    assert.equal(roots[0].label, "🎯 v1.0.0 Developer Preview (75%)");
    assert.match(roots[0].tooltip, /Project Goal \(GOVERNS\)/);
    assert.match(roots[0].tooltip, /2026-10-31/);
    assert.match(roots[0].tooltip, /active/);
    assert.equal(roots[0].children[0].label, "✓ Hardening");
    assert.equal(roots[0].children[1].label, "🚧 Extension Packaging");
    assert.equal(roots[0].children[2].label, "○ Release Notes");
    assert.equal(roots[0].children[0].isStory, true);
    assert.match(roots[0].children[0].tooltip, /story-1/);
  });

  it("retrieves roots once, returns children, caches results, and refreshes", async () => {
    const calls = [];
    const provider = new GoalsTreeDataProvider("/workspace", {
      runner: async (...args) => {
        calls.push(args);
        return goals;
      },
    });
    let refreshCount = 0;
    provider._onDidChangeTreeData = { fire: () => { refreshCount += 1; } };

    const first = await provider.getChildren();
    const second = await provider.getChildren();
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ["goal", ["list"], { cwd: "/workspace" }]);
    assert.deepEqual(await provider.getChildren(first[0]), first[0].children);
    assert.equal(provider.getTreeItem(first[0]), first[0]);
    assert.equal(second[0].id, "goal-1");

    provider.refresh();
    await provider.getChildren();
    assert.equal(refreshCount, 1);
    assert.equal(calls.length, 2);
  });

  it("returns the no-goals fallback when the CLI fails", async () => {
    const provider = new GoalsTreeDataProvider("/workspace", {
      runner: async () => { throw new Error("synlynk unavailable"); },
    });

    const items = await provider.getChildren();
    assert.deepEqual(items, [{
      id: "goals-empty",
      label: "No Goals Configured",
      tooltip: "Use synlynk goal add or the Command Palette to establish a project milestone",
    }]);
  });
});
