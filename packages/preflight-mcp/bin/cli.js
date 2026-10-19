#!/usr/bin/env node

const { evaluatePreflight, startMcpServer } = require("../index.js");

const args = process.argv.slice(2);

if (args.length === 0 || args.includes("--mcp")) {
  // Stdio MCP mode
  startMcpServer();
} else {
  // Interactive CLI mode
  const asJson = args.includes("--json");
  const prompt = args.filter(a => !a.startsWith("--")).join(" ");

  if (!prompt) {
    console.log("Usage: synlynk-preflight <prompt> [--json] [--optimize-for <priority>]");
    process.exit(1);
  }

  const result = evaluatePreflight(prompt);
  if (asJson) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const cls = result.task_classification;
    const recs = result.recommendations;

    console.log("\n⚡ Synaptic AI Pre-Flight Oracle");
    console.log(`Task:        "${prompt}"`);
    console.log(`Discipline:  ${cls.sfia_code} — ${cls.sfia_name}`);
    console.log(`Complexity:  ${cls.complexity.toUpperCase()}\n`);
    console.log("Recommendations:");
    if (recs.primary) {
      console.log(`  ★ Primary:   ${recs.primary.harness.toUpperCase()} (${recs.primary.model}) — Quality: ${recs.primary.quality_score} | Cost: $${recs.primary.cost_per_verified_fix_usd}/fix`);
    }
    if (recs.failover) {
      console.log(`  ⟳ Failover:  ${recs.failover.harness.toUpperCase()} (${recs.failover.model}) — Low quota risk`);
    }
    if (recs.budget) {
      console.log(`  $ Budget:    ${recs.budget.harness.toUpperCase()} (${recs.budget.model}) — Lowest cost\n`);
    }
    console.log(`Automate in your repo: ${result.cta.install_cmd} | ${result.cta.vscode_url}\n`);
  }
}
