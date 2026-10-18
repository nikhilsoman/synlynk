"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const {
  formatDoctorSummary,
  registerDoctorCommand,
} = require("../../src/commands/doctor");

function createVscode() {
  const state = {
    command: null,
    outputChannels: [],
    errors: [],
    terminals: [],
  };

  return {
    state,
    commands: {
      registerCommand(name, handler) {
        assert.equal(name, "synlynk.doctor");
        state.command = handler;
        return { dispose() {} };
      },
    },
    window: {
      createOutputChannel(name) {
        const channel = {
          name,
          lines: [],
          shown: 0,
          appendLine(line) { this.lines.push(line); },
          show() { this.shown += 1; },
        };
        state.outputChannels.push(channel);
        return channel;
      },
      showErrorMessage: async (message, ...choices) => {
        state.errors.push({ message, choices });
        return state.errorChoice;
      },
      createTerminal(name) {
        const terminal = {
          name,
          shown: 0,
          texts: [],
          show() { this.shown += 1; },
          sendText(text) { this.texts.push(text); },
        };
        state.terminals.push(terminal);
        return terminal;
      },
    },
  };
}

describe("Doctor diagnostics command", () => {
  it("formats doctor checks into a Markdown summary", () => {
    const summary = formatDoctorSummary({
      checks: [
        { name: "python_runtime", passed: true, message: "Python 3.11 detected" },
        { name: "harness_grok", passed: false, message: "xAI API key not configured" },
      ],
    });

    assert.match(summary, /# Synlynk Doctor Diagnostics/);
    assert.match(summary, /✓ python_runtime: Python 3.11 detected/);
    assert.match(summary, /✗ harness_grok: xAI API key not configured/);
  });

  it("runs diagnostics through the injected runner and writes the summary", async () => {
    const vscode = createVscode();
    const calls = [];
    registerDoctorCommand(vscode, "/workspace", {
      runner: async (...args) => {
        calls.push(args);
        return { checks: [{ name: "python_runtime", passed: true, message: "Python detected" }] };
      },
    });

    await vscode.state.command();

    assert.deepEqual(calls, [["doctor", [], { cwd: "/workspace" }]]);
    assert.equal(vscode.state.outputChannels.length, 1);
    assert.deepEqual(vscode.state.outputChannels[0].lines, [
      "Running environment diagnostics...",
      "# Synlynk Doctor Diagnostics\n\n- ✓ python_runtime: Python detected",
    ]);
  });

  it("offers pipx bootstrap guidance when the CLI is missing", async () => {
    const vscode = createVscode();
    vscode.state.errorChoice = "Install via pipx";
    registerDoctorCommand(vscode, "/workspace", {
      runner: async () => {
        const error = new Error("synlynk not found");
        error.type = "CLI_MISSING";
        throw error;
      },
    });

    await vscode.state.command();

    assert.deepEqual(vscode.state.errors, [{
      message: "Synlynk CLI not found. Install via pipx?",
      choices: ["Install via pipx", "Dismiss"],
    }]);
    assert.deepEqual(vscode.state.terminals[0].texts, ["pipx install synlynk"]);
    assert.equal(vscode.state.terminals[0].shown, 1);
  });
});
