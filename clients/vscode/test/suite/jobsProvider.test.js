"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  JobsTreeDataProvider,
  formatJobItems,
} = require("../../src/providers/jobsProvider");

describe("Dispatched Jobs TreeDataProvider", () => {
  it("formats status variants with review context and worktree safety copy", () => {
    const items = formatJobItems([
      {
        id: "djob-complete",
        task: "ship extension",
        status: "VERIFIED",
        author: "agy",
        verifier: "codex",
        worktree_path: "/worktrees/djob-complete",
        branch: "dispatch/agy/djob-complete",
      },
      { id: "djob-running", task: "run tests", status: "RUNNING" },
      { id: "djob-failed", task: "build package", status: "FAILED" },
      { id: "djob-tripped", task: "retry job", status: "CIRCUIT_BREAKER" },
    ]);

    assert.deepEqual(
      items.map(({ label, contextValue }) => ({ label, contextValue })),
      [
        { label: "🟢 djob-complete: ship extension", contextValue: "job-complete" },
        { label: "🟡 djob-running: run tests", contextValue: "job-running" },
        { label: "🔴 djob-failed: build package", contextValue: "job-failed" },
        { label: "⚡ djob-tripped: retry job", contextValue: "job-tripped" },
      ]
    );
    assert.equal(items[0].jobId, "djob-complete");
    assert.equal(items[0].worktreePath, "/worktrees/djob-complete");
    assert.equal(items[0].branch, "dispatch/agy/djob-complete");
    assert.match(items[0].tooltip, /Leased Git Worktree: Your open files and cursor position are never modified during execution\./);
    assert.match(items[1].tooltip, /\*\*Author:\*\* Unknown/);
    assert.match(items[1].tooltip, /\*\*Verifier:\*\* None/);
  });

  it("accepts jobs wrapped in a response object", () => {
    const [item] = formatJobItems({
      jobs: [{ id: "djob-wrapped", task: "wrapped job", status: "RUNNING" }],
    });

    assert.equal(item.id, "djob-wrapped");
    assert.equal(item.contextValue, "job-running");
  });

  it("retrieves root items once, refreshes its cache, and returns tree items unchanged", async () => {
    const calls = [];
    const provider = new JobsTreeDataProvider("/workspace", {
      runner: async (...args) => {
        calls.push(args);
        return { jobs: [{ id: "djob-1", task: "test", status: "VERIFIED" }] };
      },
    });
    let refreshCount = 0;
    provider._onDidChangeTreeData = { fire: () => { refreshCount += 1; } };

    const first = await provider.getChildren();
    const second = await provider.getChildren();
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ["jobs", ["--limit", "15"], { cwd: "/workspace" }]);
    assert.equal(provider.getTreeItem(first[0]), first[0]);
    assert.deepEqual(await provider.getChildren(first[0]), []);

    provider.refresh();
    await provider.getChildren();
    assert.equal(refreshCount, 1);
    assert.equal(calls.length, 2);
    assert.equal(second[0].id, "djob-1");
  });

  it("returns the empty-dispatch fallback when the CLI call fails", async () => {
    const provider = new JobsTreeDataProvider("/workspace", {
      runner: async () => { throw new Error("synlynk unavailable"); },
    });

    const items = await provider.getChildren();
    assert.deepEqual(items, [{
      id: "jobs-empty",
      label: "No Recent Dispatches",
      tooltip: "Press Cmd+Shift+P and run 'Synlynk: Dispatch Task' to start a job in a leased worktree.",
    }]);
  });
});
