"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  FleetTreeDataProvider,
  formatFleetItems,
} = require("../../src/providers/fleetProvider");

describe("Fleet Health TreeDataProvider", () => {
  it("formats harnesses, routing microcopy, and the spend summary", () => {
    const items = formatFleetItems({
      harnesses: [
        { name: "claude", status: "ready", role: "architect" },
        { name: "grok", status: "recharge_needed", quota_reset: "2026-10-18T12:00:00Z" },
      ],
      spend: { session_dollars: 4.12, fleet_total_dollars: 18.47, tokens_total: 142000 },
    });

    assert.equal(items.length, 3);
    assert.equal(items[0].label, "Claude Sonnet — Ready");
    assert.equal(items[0].statusText, "Ready");
    assert.match(items[0].tooltip, /\*Synlynk Capability Routing: Model A authors, Model B audits\.\*/);

    const spend = items.find((item) => item.id === "fleet-spend");
    assert.ok(spend);
    assert.match(spend.label, /\$18\.47/);
    assert.match(spend.tooltip, /Dual-Ledger Accounting/);
    assert.match(spend.tooltip, /142,000/);
  });

  it("uses the agents mapping when harnesses are absent", () => {
    const items = formatFleetItems({
      agents: {
        codex: { status: "active", role: "implementer" },
        local: "ready",
      },
    });

    assert.equal(items[0].label, "OpenAI Codex — Active (Driving)");
    assert.equal(items[1].label, "Local Inference (oMLX/Aider) — Ready");
  });

  it("retrieves root items once, refreshes its cache, and returns tree items unchanged", async () => {
    const calls = [];
    const provider = new FleetTreeDataProvider("/workspace", {
      runner: async (...args) => {
        calls.push(args);
        return { harnesses: [{ name: "codex", status: "ready" }] };
      },
    });
    let refreshCount = 0;
    provider._onDidChangeTreeData = { fire: () => { refreshCount += 1; } };

    const first = await provider.getChildren();
    const second = await provider.getChildren();
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ["status", [], { cwd: "/workspace" }]);
    assert.equal(provider.getTreeItem(first[0]), first[0]);
    assert.deepEqual(await provider.getChildren(first[0]), []);

    provider.refresh();
    await provider.getChildren();
    assert.equal(refreshCount, 1);
    assert.equal(calls.length, 2);
    assert.equal(second[0].id, "harness-codex");
  });

  it("returns doctor advice when the CLI status call fails", async () => {
    const provider = new FleetTreeDataProvider("/workspace", {
      runner: async () => { throw new Error("synlynk unavailable"); },
    });

    const items = await provider.getChildren();
    assert.equal(items[0].id, "fleet-error");
    assert.match(items[0].label, /Fleet Status Offline: synlynk unavailable/);
    assert.match(items[0].tooltip, /synlynk doctor/);
  });
});
