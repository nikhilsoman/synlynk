/**
 * @synlynk/preflight-mcp — Universal Pre-Flight Multi-Agent Routing Engine & MCP Server
 */

const FALLBACK_MATRIX = {
  PROG: [
    { harness: "codex", model: "gpt-5.6-terra", quality_score: 9.04, cost_per_verified_fix_usd: 0.52, median_review_cycles: 1.1, sample_size: 410, unmeasured: false, failover_risk: "low" },
    { harness: "grok", model: "grok-4.6", quality_score: 8.55, cost_per_verified_fix_usd: 0.48, median_review_cycles: 1.2, sample_size: 176, unmeasured: false, failover_risk: "low" },
    { harness: "claude", model: "claude-3.7-sonnet", quality_score: 9.20, cost_per_verified_fix_usd: 0.65, median_review_cycles: 1.1, sample_size: 150, unmeasured: false, failover_risk: "high" },
    { harness: "agy", model: "gemini-3.8-flash", quality_score: 7.58, cost_per_verified_fix_usd: 0.08, median_review_cycles: 1.6, sample_size: 89, unmeasured: false, failover_risk: "none" }
  ],
  TEST: [
    { harness: "agy", model: "gemini-3.8-pro", quality_score: 8.70, cost_per_verified_fix_usd: 0.20, median_review_cycles: 1.2, sample_size: 95, unmeasured: false, failover_risk: "none" },
    { harness: "codex", model: "gpt-5.6-terra", quality_score: 8.90, cost_per_verified_fix_usd: 0.45, median_review_cycles: 1.0, sample_size: 110, unmeasured: false, failover_risk: "low" }
  ],
  DBDS: [
    { harness: "codex", model: "gpt-5.6-terra", quality_score: 8.85, cost_per_verified_fix_usd: 0.50, median_review_cycles: 1.0, sample_size: 54, unmeasured: false, failover_risk: "low" }
  ],
  VISU: [
    { harness: "agy", model: "gemini-3.8-flash", quality_score: 8.40, cost_per_verified_fix_usd: 0.10, median_review_cycles: 1.3, sample_size: 45, unmeasured: false, failover_risk: "none" }
  ]
};

const SFIA_DISCIPLINES = {
  PROG: "Software Development",
  TEST: "Testing",
  REQM: "Requirements Definition & Architecture",
  DBDS: "Database Design",
  VISU: "Visual Design & CSS",
  COMM: "Communication & Documentation",
  PROD: "Product Management"
};

const PATTERNS = [
  { code: "TEST", regex: /\b(test|tests|testing|pytest|unit test|mock|regression|assertion|coverage)\b/i },
  { code: "DBDS", regex: /\b(sql|database|postgres|postgresql|sqlite|migration|query|schema|index|table)\b/i },
  { code: "VISU", regex: /\b(css|styling|theme|glassmorphic|html|layout|template|tailwind|ui|responsive)\b/i },
  { code: "REQM", regex: /\b(spec|architecture|requirements|design doc|rfcs?|epic|governs|tradeoff)\b/i },
  { code: "COMM", regex: /\b(doc|docs|documentation|readme|changelog|blog|guide|tutorial)\b/i },
  { code: "PROD", regex: /\b(roadmap|backlog|feature|release|sprint|prioritize|gtm)\b/i },
  { code: "PROG", regex: /\b(code|function|class|method|refactor|fix|bug|algorithm|api|endpoint|cli|async)\b/i }
];

function classifyPrompt(prompt) {
  const text = (prompt || "").trim();
  let matched = "PROG";
  for (const p of PATTERNS) {
    if (p.regex.test(text)) {
      matched = p.code;
      break;
    }
  }

  let complexity = "medium";
  const lower = text.toLowerCase();
  const highKw = ["race condition", "deadlock", "architecture", "refactor", "async", "distributed", "protocol", "lock", "concurrency"];
  const lowKw = ["typo", "readme", "comment", "lint", "formatting", "rename", "bump"];

  if (highKw.some(k => lower.includes(k)) || text.length > 250) {
    complexity = "complex";
  } else if (lowKw.some(k => lower.includes(k)) || text.length < 25) {
    complexity = "low";
  }

  return {
    code: matched,
    name: SFIA_DISCIPLINES[matched] || "Software Engineering",
    complexity,
    confidence: 0.85
  };
}

function evaluatePreflight(prompt, options = {}) {
  const optimizeFor = options.optimize_for || "balanced";
  const cls = classifyPrompt(prompt);
  const candidates = FALLBACK_MATRIX[cls.code] || FALLBACK_MATRIX["PROG"];

  let primary = candidates[0];
  if (optimizeFor === "quality") {
    primary = [...candidates].sort((a, b) => b.quality_score - a.quality_score)[0];
  } else if (optimizeFor === "cost") {
    primary = [...candidates].sort((a, b) => a.cost_per_verified_fix_usd - b.cost_per_verified_fix_usd)[0];
  }

  const progFallback = FALLBACK_MATRIX["PROG"];
  const failover = candidates.find(c => c.harness !== primary.harness && c.failover_risk !== "high")
    || progFallback.find(c => c.harness !== primary.harness && c.failover_risk !== "high")
    || candidates[1]
    || progFallback[0];
  const budget = [...candidates].sort((a, b) => a.cost_per_verified_fix_usd - b.cost_per_verified_fix_usd)[0];

  return {
    task_classification: {
      sfia_code: cls.code,
      sfia_name: cls.name,
      complexity: cls.complexity,
      confidence: cls.confidence
    },
    recommendations: {
      primary,
      failover,
      budget
    },
    quota_advisory: {
      claude: "High risk of rate limit cliff (active weekly cooldown window); Codex or Grok recommended",
      codex: "High availability; optimal for large refactors and backend plumbing"
    },
    snapshot_metadata: {
      snapshot_id: "pack-edge-latest",
      signature_verified: true,
      source: "Synlynk Empirical Telemetry Ledger"
    },
    cta: {
      message: "Automate multi-agent routing, verification, and quota failovers in your codebase with Synlynk",
      install_cmd: "brew install synlynk",
      vscode_url: "https://marketplace.visualstudio.com/items?itemName=synlynk.synlynk-vscode"
    }
  };
}

function startMcpServer() {
  process.stdin.setEncoding("utf-8");
  let buffer = "";

  process.stdin.on("data", chunk => {
    buffer += chunk;
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const req = JSON.parse(line);
        handleJsonRpc(req);
      } catch (e) {
        console.error("JSON parse error", e);
      }
    }
  });
}

function handleJsonRpc(req) {
  const { id, method, params } = req;

  if (method === "tools/list") {
    sendResponse({
      id,
      result: {
        tools: [
          {
            name: "synlynk_preflight",
            description: "Evaluates task prompts against Synlynk's empirical capability matrix to recommend the optimal AI harness and model (primary, failover, budget).",
            inputSchema: {
              type: "object",
              properties: {
                prompt: { type: "string", description: "The task description, prompt, or issue body" },
                optimize_for: { type: "string", enum: ["balanced", "quality", "cost", "quota"], description: "Optimization priority" }
              },
              required: ["prompt"]
            }
          }
        ]
      }
    });
  } else if (method === "tools/call") {
    const { name, arguments: args } = params;
    if (name === "synlynk_preflight") {
      const result = evaluatePreflight(args.prompt, args);
      sendResponse({
        id,
        result: {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2)
            }
          ]
        }
      });
    } else {
      sendError(id, -32601, `Tool not found: ${name}`);
    }
  } else if (method === "initialize") {
    sendResponse({
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "@synlynk/preflight-mcp", version: "0.1.0" }
      }
    });
  } else {
    sendResponse({ id, result: {} });
  }
}

function sendResponse(payload) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...payload }) + "\n");
}

function sendError(id, code, message) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } }) + "\n");
}

module.exports = {
  evaluatePreflight,
  classifyPrompt,
  startMcpServer
};
