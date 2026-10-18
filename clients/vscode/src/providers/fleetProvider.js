"use strict";

const { runSynlynk } = require("../cli");

const HARNESS_DISPLAY = {
  claude: "Claude Sonnet",
  codex: "OpenAI Codex",
  agy: "Google Agy (Gemini)",
  grok: "xAI Grok",
  local: "Local Inference (oMLX/Aider)",
};

function getStatusText(status) {
  if (status === "ready") {
    return "Ready";
  }
  if (status === "active") {
    return "Active (Driving)";
  }
  if (status === "recharge_needed") {
    return "Recharge Needed";
  }
  return status ? String(status) : "Unknown";
}

function getHarnesses(statusData) {
  if (Array.isArray(statusData?.harnesses)) {
    return statusData.harnesses;
  }

  if (statusData?.agents && typeof statusData.agents === "object") {
    return Object.entries(statusData.agents).map(([name, value]) => {
      if (value && typeof value === "object") {
        return { name, ...value };
      }
      return { name, status: value };
    });
  }

  return [];
}

function asAmount(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount : 0;
}

function formatFleetItems(statusData) {
  const items = getHarnesses(statusData).map((harness) => {
    const name = harness.name || "unknown";
    const displayName = HARNESS_DISPLAY[name] || name;
    const statusText = getStatusText(harness.status);

    return {
      id: `harness-${name}`,
      label: `${displayName} — ${statusText}`,
      status: harness.status,
      statusText,
      tooltip: `**Harness:** ${displayName}\n` +
        `**Assigned Role:** ${harness.role || "general"}\n` +
        `**Status:** ${statusText}\n` +
        `**Quota Reset:** ${harness.quota_reset || "Unlimited"}\n\n` +
        "*Synlynk Capability Routing: Model A authors, Model B audits.*",
    };
  });

  const spend = statusData?.spend || {};
  const sessionDollars = asAmount(spend.session_dollars);
  const fleetTotalDollars = asAmount(spend.fleet_total_dollars);
  const tokensTotal = asAmount(spend.tokens_total);
  items.push({
    id: "fleet-spend",
    label: `Spend (Session): $${sessionDollars.toFixed(2)} | Fleet: $${fleetTotalDollars.toFixed(2)}`,
    tooltip: "**Dual-Ledger Accounting:**\n" +
      "Tracks real subscription-amortized expenditure alongside raw frontier API value.\n" +
      `Tokens: ${tokensTotal.toLocaleString()}`,
  });

  return items;
}

class FleetTreeDataProvider {
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
        this.cachedData = await this.runner("status", [], { cwd: this.workspaceRoot });
      }
      return formatFleetItems(this.cachedData);
    } catch (error) {
      const message = error?.message || String(error);
      return [{
        id: "fleet-error",
        label: `Fleet Status Offline: ${message}`,
        tooltip: "Run 'synlynk doctor' to inspect CLI status.",
      }];
    }
  }
}

module.exports = { FleetTreeDataProvider, formatFleetItems };
