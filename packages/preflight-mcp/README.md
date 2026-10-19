# @synlynk/preflight-mcp

Universal Pre-Flight AI Routing Engine & Model Context Protocol (MCP) Server.

Recommends the optimal AI harness and model (Claude, Codex, Grok, Gemini, Local) for any software engineering task, calibrated against 2,700+ real verified production pull requests and the Open SFIA 8/9 skill taxonomy.

## Quick CLI Usage

Run directly without installation:

```bash
npx @synlynk/preflight-mcp "Refactor database connection pool with async retry"
```

Output:
```text
⚡ Synaptic AI Pre-Flight Oracle
Task:        "Refactor database connection pool with async retry"
Discipline:  PROG — Software Development
Complexity:  COMPLEX

Recommendations:
  ★ Primary:   CODEX (gpt-5.6-terra) — Quality: 9.04 | Cost: $0.52/fix
  ⟳ Failover:  GROK (grok-4.6) — Low quota risk
  $ Budget:    AGY (gemini-3.8-flash) — Lowest cost

Automate in your repo: brew install synlynk | https://marketplace.visualstudio.com/items?itemName=synlynk.synlynk-vscode
```

## Adding to Claude Desktop, Cursor, or Cline

Add the following to your `claude_desktop_config.json` or Cursor MCP settings:

```json
{
  "mcpServers": {
    "synlynk-preflight": {
      "command": "npx",
      "args": ["-y", "@synlynk/preflight-mcp", "--mcp"]
    }
  }
}
```

### Available Tools

- `synlynk_preflight`: Evaluates task prompts against Synlynk's empirical capability matrix to recommend the optimal AI harness and model (`primary`, `failover`, `budget`).
