"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { describe, it } = require("node:test");
const {
  runSynlynk,
  parseCliJson,
  checkCliCompatibility
} = require("../../src/cli");
const { formatError } = require("../../src/util/errorBoundary");

function createFakeCli(source) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "synlynk-cli-"));
  const executable = path.join(directory, "fake-cli.js");
  fs.writeFileSync(executable, `#!/usr/bin/env node\n${source}`, "utf8");
  fs.chmodSync(executable, 0o755);
  return { directory, executable };
}

describe("Host RPC Bridge & Version Handshake", () => {
  it("parses valid CLI JSON", () => {
    const parsed = parseCliJson(
      '{"status":"ok","fleet":["claude","codex"]}',
      "status"
    );

    assert.equal(parsed.status, "ok");
    assert.equal(parsed.fleet.length, 2);
  });

  it("rejects malformed CLI JSON with its subcommand", () => {
    assert.throws(
      () => parseCliJson("Not JSON output: traceback error", "status"),
      /Malformed JSON output from synlynk status/
    );
  });

  it("classifies offline network failures", () => {
    const formatted = formatError(
      new Error("getaddrinfo ENOTFOUND generativelanguage.googleapis.com")
    );

    assert.equal(formatted.type, "NETWORK_OFFLINE");
    assert.match(formatted.message, /Offline or unreachable API endpoint/);
  });

  it("classifies missing CLI binaries", () => {
    const formatted = formatError(new Error("spawn synlynk ENOENT"));

    assert.equal(formatted.type, "CLI_MISSING");
    assert.match(formatted.message, /not found on system PATH/);
  });

  it("preserves malformed output errors", () => {
    const formatted = formatError(new Error("Malformed JSON output from synlynk status"));

    assert.equal(formatted.type, "MALFORMED_OUTPUT");
  });

  it("uses safe fallback error messages", () => {
    assert.deepEqual(formatError(), {
      type: "UNKNOWN",
      message: "Unknown error occurred"
    });
    assert.deepEqual(formatError("unexpected failure"), {
      type: "EXECUTION_ERROR",
      message: "unexpected failure"
    });
  });

  it("accepts compatible CLI versions", async () => {
    const result = await checkCliCompatibility(async () => ({ version: "0.23.0" }));

    assert.deepEqual(result, { compatible: true, version: "0.23.0" });
  });

  it("reports an upgrade for incompatible CLI versions", async () => {
    const result = await checkCliCompatibility(async () => ({ version: "0.19.2" }));

    assert.equal(result.compatible, false);
    assert.match(result.error, /Upgrade required/);
  });

  it("exports the RPC bridge", () => {
    assert.equal(typeof runSynlynk, "function");
  });

  it("runs a CLI command with JSON output", async () => {
    const fixture = createFakeCli(
      'if (process.argv[2] === "status") process.stdout.write("{\\"status\\":\\"ok\\"}");',
    );

    try {
      const result = await runSynlynk("status", [], { cliPath: fixture.executable });
      assert.deepEqual(result, { status: "ok" });
    } finally {
      fs.rmSync(fixture.directory, { recursive: true, force: true });
    }
  });

  it("formats malformed bridge output", async () => {
    const fixture = createFakeCli('process.stdout.write("not json");');

    try {
      await assert.rejects(
        () => runSynlynk("status", [], { cliPath: fixture.executable }),
        (error) => error.type === "MALFORMED_OUTPUT"
      );
    } finally {
      fs.rmSync(fixture.directory, { recursive: true, force: true });
    }
  });

  it("formats CLI execution failures", async () => {
    const fixture = createFakeCli('process.stderr.write("command failed"); process.exit(1);');

    try {
      await assert.rejects(
        () => runSynlynk("status", [], { cliPath: fixture.executable }),
        (error) => error.type === "EXECUTION_ERROR" && error.message === "command failed"
      );
    } finally {
      fs.rmSync(fixture.directory, { recursive: true, force: true });
    }
  });

  it("normalizes a CLI version response", async () => {
    const fixture = createFakeCli('process.stdout.write("synlynk 0.23.1\\n");');

    try {
      const result = await runSynlynk("--version", [], { cliPath: fixture.executable });
      assert.deepEqual(result, { version: "0.23.1" });
    } finally {
      fs.rmSync(fixture.directory, { recursive: true, force: true });
    }
  });

  it("rejects a lower minor version regardless of its patch", async () => {
    const result = await checkCliCompatibility(async () => ({ version: "0.22.999" }));

    assert.equal(result.compatible, false);
  });

  it("returns a usable error when version probing fails", async () => {
    const result = await checkCliCompatibility(async () => {
      throw new Error("synlynk unavailable");
    });

    assert.deepEqual(result, {
      compatible: false,
      version: "unknown",
      error: "synlynk unavailable"
    });
  });
});
